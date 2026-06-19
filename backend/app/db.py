"""Warstwa dostępu do SQLite (stdlib sqlite3 — bez ORM, zero zależności)."""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

# Ścieżka do bazy — domyślnie ./data/portfolio.db, nadpisywalna przez env.
DB_PATH = Path(os.environ.get("DB_PATH", Path(__file__).resolve().parents[2] / "data" / "portfolio.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS instruments (
    isin          TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    imported_name TEXT,                        -- nazwa z importu (read-only, nie nadpisywana przez UI)
    ticker        TEXT,
    currency     TEXT,                       -- 'EUR' | 'PLN'
    source       TEXT,                       -- 'yfinance' | 'stooq'
    category     TEXT,                       -- klasa aktywów: 'Akcje' | 'Obligacje' | ...
    active       INTEGER NOT NULL DEFAULT 1,
    needs_config INTEGER NOT NULL DEFAULT 1
);

-- Model docelowy alokacji: kategoria -> docelowy udział %.
CREATE TABLE IF NOT EXISTS target_allocation (
    category   TEXT PRIMARY KEY,
    weight_pct REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS transactions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    ts             TEXT NOT NULL,            -- ISO 8601
    isin           TEXT NOT NULL REFERENCES instruments(isin),
    type           TEXT NOT NULL,           -- 'BUY' | 'SELL'
    quantity       REAL NOT NULL,
    price_pln      REAL NOT NULL,
    value_pln      REAL NOT NULL,
    commission_pln REAL NOT NULL DEFAULT 0,
    import_hash    TEXT NOT NULL UNIQUE
);
CREATE INDEX IF NOT EXISTS idx_tx_isin ON transactions(isin);

CREATE TABLE IF NOT EXISTS prices (
    isin   TEXT NOT NULL,
    date   TEXT NOT NULL,                    -- YYYY-MM-DD
    price  REAL NOT NULL,                    -- waluta natywna instrumentu
    source TEXT,
    PRIMARY KEY (isin, date)
);

CREATE TABLE IF NOT EXISTS fx_rates (
    date        TEXT NOT NULL,               -- YYYY-MM-DD
    currency    TEXT NOT NULL,               -- np. 'EUR'
    rate_to_pln REAL NOT NULL,
    PRIMARY KEY (date, currency)
);

-- Miesięczny indeks cen HICP (Eurostat, baza 2015=100) — pod benchmark „inflacja + X%".
CREATE TABLE IF NOT EXISTS cpi_index (
    month TEXT PRIMARY KEY,                  -- 'YYYY-MM-01' (pierwszy dzień miesiąca)
    idx   REAL NOT NULL                      -- indeks HICP, baza 2015=100
);

-- Księga gotówki. amount_pln = wpływ na saldo: wpłata +, wypłata −, kupno −, sprzedaż +.
-- Saldo gotówki = SUM(amount_pln). Kind 'deposit'/'withdrawal' to przepływy zewnętrzne
-- (do XIRR); 'buy'/'sell' to ruchy wewnętrzne (gotówka <-> ETF) tworzone przy imporcie.
CREATE TABLE IF NOT EXISTS cash_flows (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT NOT NULL,               -- ISO 8601
    kind        TEXT NOT NULL,               -- 'deposit' | 'withdrawal' | 'buy' | 'sell'
    amount_pln  REAL NOT NULL,
    note        TEXT,
    import_hash TEXT UNIQUE
);
"""


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    """Lekkie migracje dla istniejących baz (CREATE IF NOT EXISTS nie dodaje kolumn)."""
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(instruments)")}
    if "category" not in cols:
        conn.execute("ALTER TABLE instruments ADD COLUMN category TEXT")
    if "imported_name" not in cols:
        conn.execute("ALTER TABLE instruments ADD COLUMN imported_name TEXT")


def init_db(conn: sqlite3.Connection | None = None) -> None:
    own = conn is None
    conn = conn or get_connection()
    try:
        conn.executescript(SCHEMA)
        _migrate(conn)
        conn.commit()
    finally:
        if own:
            conn.close()


@contextmanager
def db_session():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
