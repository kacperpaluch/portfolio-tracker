"""Obsługa instrumentów: tworzenie z importu i edycja mapowań użytkownika."""
from __future__ import annotations

import re
import sqlite3

from .prices import SUPPORTED_SOURCES

ISIN_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")


def resolve_broker_instrument(
    broker: str,
    symbol: str,
    exchange: str,
    conn: sqlite3.Connection | None = None,
) -> str | None:
    """Zwraca ISIN dla identyfikatora używanego w eksporcie brokera."""
    key = (broker.strip().lower(), symbol.strip().upper(), exchange.strip().upper())
    if conn is not None:
        row = conn.execute(
            "SELECT isin FROM broker_instrument_aliases WHERE broker = ? AND symbol = ? AND exchange = ?",
            key,
        ).fetchone()
        if row is not None:
            return row["isin"]
    return None


def save_broker_instrument(
    conn: sqlite3.Connection,
    *,
    broker: str,
    symbol: str,
    exchange: str,
    isin: str,
    name: str,
    ticker: str | None,
    currency: str,
    source: str = "yfinance",
) -> dict:
    """Tworzy/aktualizuje instrument i zapisuje trwały alias używany przy imporcie."""
    broker = broker.strip().lower()
    symbol = symbol.strip().upper()
    exchange = exchange.strip().upper()
    isin = isin.strip().upper()
    name = name.strip()
    ticker = (ticker or "").strip() or None
    currency = currency.strip().upper()
    source = source.strip().lower()

    if not broker or not symbol or not exchange:
        raise ValueError("Broker, symbol i giełda są wymagane")
    if not ISIN_RE.fullmatch(isin):
        raise ValueError("ISIN musi mieć 12 znaków i poprawny format")
    if not name:
        raise ValueError("Nazwa instrumentu jest wymagana")
    if not re.fullmatch(r"[A-Z]{3}", currency):
        raise ValueError("Waluta musi być trzyznakowym kodem, np. EUR")
    if source not in SUPPORTED_SOURCES:
        raise ValueError("Nieobsługiwane źródło notowań")

    ensure_instrument(conn, isin, name)
    conn.execute(
        """
        UPDATE instruments
           SET name = ?, imported_name = COALESCE(imported_name, ?), ticker = ?,
               currency = ?, source = ?, needs_config = ?
         WHERE isin = ?
        """,
        (name, name, ticker, currency, source, 0 if ticker else 1, isin),
    )
    conn.execute(
        """
        INSERT INTO broker_instrument_aliases (broker, symbol, exchange, isin)
        VALUES (?, ?, ?, ?)
        ON CONFLICT (broker, symbol, exchange) DO UPDATE SET isin = excluded.isin
        """,
        (broker, symbol, exchange, isin),
    )
    return {
        "broker": broker,
        "symbol": symbol,
        "exchange": exchange,
        "isin": isin,
        "name": name,
        "ticker": ticker,
        "currency": currency,
        "source": source,
    }


def ensure_instrument(conn: sqlite3.Connection, isin: str, name: str) -> None:
    """Tworzy instrument przy pierwszym imporcie, jeśli jeszcze nie istnieje.

    Nie zgaduje tickera, waluty ani providera. Użytkownik wybiera je w UI.
    """
    row = conn.execute("SELECT isin FROM instruments WHERE isin = ?", (isin,)).fetchone()
    if row is not None:
        return
    conn.execute(
        """
        INSERT INTO instruments (isin, name, imported_name, ticker, currency, source, active, needs_config)
        VALUES (?, ?, ?, ?, ?, ?, 1, ?)
        """,
        (isin, name, name, None, None, None, 1),
    )


def list_instruments(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT * FROM instruments ORDER BY needs_config DESC, name").fetchall()
    return [dict(r) for r in rows]


def update_instrument(
    conn: sqlite3.Connection,
    isin: str,
    *,
    ticker: str | None,
    currency: str | None,
    source: str | None,
    category: str | None = None,
    active: bool | None = None,
    name: str | None = None,
) -> dict | None:
    """Aktualizuje mapowanie instrumentu. needs_config wyłączamy, gdy komplet danych."""
    existing = conn.execute("SELECT * FROM instruments WHERE isin = ?", (isin,)).fetchone()
    if existing is None:
        return None
    name_val = (name or "").strip() or existing["name"]
    ticker = (ticker or "").strip() or None
    currency = (currency or "").strip().upper() or None
    source = (source or "").strip().lower() or None
    if source and source not in SUPPORTED_SOURCES:
        raise ValueError("Nieobsługiwane źródło notowań")
    category = (category or "").strip() or None
    needs_config = 0 if (ticker and currency and source) else 1
    active_val = existing["active"] if active is None else int(active)
    conn.execute(
        """
        UPDATE instruments
           SET name = ?, ticker = ?, currency = ?, source = ?, category = ?, active = ?, needs_config = ?
         WHERE isin = ?
        """,
        (name_val, ticker, currency, source, category, active_val, needs_config, isin),
    )
    return dict(conn.execute("SELECT * FROM instruments WHERE isin = ?", (isin,)).fetchone())
