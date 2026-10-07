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
    source       TEXT,                       -- 'yfinance' | 'eodhd' | 'alphavantage' | 'csv' | 'obligacje'
    category     TEXT,                       -- klasa aktywów: 'Akcje' | 'Obligacje' | ...
    active       INTEGER NOT NULL DEFAULT 1,
    needs_config INTEGER NOT NULL DEFAULT 1
);

-- Osobny symbol i waluta dla każdego providera. Kolumny ticker/source w instruments
-- pozostają aktywnym wyborem dla kompatybilności z resztą logiki wyceny.
CREATE TABLE IF NOT EXISTS instrument_provider_mappings (
    isin     TEXT NOT NULL REFERENCES instruments(isin) ON DELETE CASCADE,
    source   TEXT NOT NULL,
    ticker   TEXT NOT NULL,
    currency TEXT,
    PRIMARY KEY (isin, source)
);

-- Symbole z eksportów bez ISIN-u. Mapowania dodane w UI są trwałe i nie
-- wymagają zmiany kodu ani przebudowania obrazu aplikacji.
CREATE TABLE IF NOT EXISTS broker_instrument_aliases (
    broker   TEXT NOT NULL,
    symbol   TEXT NOT NULL,
    exchange TEXT NOT NULL,
    isin     TEXT NOT NULL REFERENCES instruments(isin),
    PRIMARY KEY (broker, symbol, exchange)
);
CREATE INDEX IF NOT EXISTS idx_broker_alias_isin ON broker_instrument_aliases(isin);

-- Konta inwestycyjne (np. IKE, zwykły rachunek). taxed=1 → szacujemy 19% podatku od zysków.
-- Konto 1 istnieje zawsze: do niego należą dane sprzed wprowadzenia kont.
CREATE TABLE IF NOT EXISTS accounts (
    id    INTEGER PRIMARY KEY,
    name  TEXT NOT NULL UNIQUE,
    taxed INTEGER NOT NULL DEFAULT 0
);
INSERT OR IGNORE INTO accounts (id, name, taxed) VALUES (1, 'IKE', 0);

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
    native_price   REAL,                    -- cena wykonania w walucie instrumentu
    native_currency TEXT,                  -- waluta ceny wykonania, np. EUR
    fx_rate        REAL,                    -- kurs waluty użyty przez brokera
    settlement_date TEXT,                  -- data rozliczenia YYYY-MM-DD
    market         TEXT,                    -- rynek/giełda, np. DEU-XETRA
    broker_order_id TEXT,                  -- numer zlecenia u brokera
    source_format  TEXT,                    -- format źródłowy importu
    note           TEXT,
    import_hash    TEXT NOT NULL UNIQUE,
    account_id     INTEGER NOT NULL DEFAULT 1 -- konto (accounts.id); musi być ostatnią kolumną
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

-- Tabele odsetkowe MF dla detalicznych obligacji skarbowych: narosłe odsetki (zł na 1 szt.)
-- na dany dzień dla zakupu w pierwszym dniu sprzedaży serii. MIN(date) = początek sprzedaży.
CREATE TABLE IF NOT EXISTS bond_interest (
    series   TEXT NOT NULL,                  -- np. 'EDO0334'
    date     TEXT NOT NULL,                  -- YYYY-MM-DD
    interest REAL NOT NULL,
    PRIMARY KEY (series, date)
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
    import_hash TEXT UNIQUE,
    account_id  INTEGER NOT NULL DEFAULT 1   -- konto (accounts.id); musi być ostatnią kolumną
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
    # Zachowaj aktualnie wybrany symbol ze starszych wersji. Nadpisane wcześniej
    # symbole innych providerów nie są możliwe do wiarygodnego odtworzenia.
    conn.execute(
        """
        INSERT OR IGNORE INTO instrument_provider_mappings (isin, source, ticker, currency)
        SELECT isin, source, ticker, currency FROM instruments
         WHERE source IS NOT NULL AND ticker IS NOT NULL AND TRIM(ticker) != ''
        """
    )
    tx_cols = {r["name"] for r in conn.execute("PRAGMA table_info(transactions)")}
    if "note" not in tx_cols:
        conn.execute("ALTER TABLE transactions ADD COLUMN note TEXT")
    transaction_columns = {
        "native_price": "REAL",
        "native_currency": "TEXT",
        "fx_rate": "REAL",
        "settlement_date": "TEXT",
        "market": "TEXT",
        "broker_order_id": "TEXT",
        "source_format": "TEXT",
    }
    for column, column_type in transaction_columns.items():
        if column not in tx_cols:
            conn.execute(f"ALTER TABLE transactions ADD COLUMN {column} {column_type}")
    # Konta: istniejące dane trafiają na konto 1. Kolumna dodawana jako ostatnia —
    # tak samo jak w SCHEMA, bo `scope_reads` składa UNION po `SELECT *`.
    for table in ("transactions", "cash_flows"):
        if "account_id" not in {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN account_id INTEGER NOT NULL DEFAULT 1")


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


def scope_reads(conn: sqlite3.Connection, account_id: int | None) -> None:
    """Zawęża ODCZYTY połączenia do konta albo do spójnego widoku całego portfela.

    Widoki TEMP przesłaniają tabele `transactions`/`cash_flows` (SQLite szuka nazw najpierw
    w schemacie temp), więc każda funkcja analityczna liczy na przefiltrowanych danych bez
    własnego WHERE — żadna nie może filtra pominąć. Zapisy idą zwykłym `db_session()`.

    Widok łączny (account_id=None): konto bez wpłat/wypłat nie prowadzi księgi gotówki, więc
    obok kont, które ją prowadzą, jego kupna wyglądałyby jak ujemne saldo. Dostaje więc
    syntetyczne wpłaty równe kupnom (i wypłaty równe sprzedażom; id ujemne): saldo zero,
    a wkładem kapitału jest koszt zakupów — jak w widoku samego konta.
    """
    if account_id is not None:
        account_id = int(account_id)  # widok nie przyjmuje parametrów — tylko liczba w SQL
        for table in ("transactions", "cash_flows"):
            conn.execute(
                f"CREATE TEMP VIEW {table} AS SELECT * FROM main.{table} WHERE account_id = {account_id}"
            )
        return
    conn.execute(
        """
        CREATE TEMP VIEW cash_flows AS
        SELECT * FROM main.cash_flows
        UNION ALL
        SELECT -id, ts, CASE kind WHEN 'buy' THEN 'deposit' ELSE 'withdrawal' END,
               -amount_pln, NULL, NULL, account_id
          FROM main.cash_flows
         WHERE kind IN ('buy', 'sell')
           AND account_id NOT IN (
               SELECT account_id FROM main.cash_flows WHERE kind IN ('deposit', 'withdrawal'))
           AND EXISTS (SELECT 1 FROM main.cash_flows WHERE kind IN ('deposit', 'withdrawal'))
        """
    )


@contextmanager
def read_session(account_id: int | None = None):
    """Sesja tylko do odczytu: jedno konto albo cały portfel (patrz `scope_reads`)."""
    conn = get_connection()
    try:
        scope_reads(conn, account_id)
        yield conn
        conn.commit()
    finally:
        conn.close()
