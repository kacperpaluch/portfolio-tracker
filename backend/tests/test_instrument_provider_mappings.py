"""Symbole notowań są przechowywane osobno dla każdego providera."""
from __future__ import annotations

import sqlite3

from app.db import SCHEMA, init_db
from app.instruments import list_instruments, update_instrument


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.execute(
        "INSERT INTO instruments "
        "(isin, name, ticker, currency, source, active, needs_config) "
        "VALUES ('IE0003XJA0J9', 'Test ETF', 'WEBN.DE', 'EUR', 'yfinance', 1, 0)"
    )
    init_db(conn)
    return conn


def test_migration_preserves_active_legacy_ticker():
    conn = _db()

    instrument = list_instruments(conn)[0]

    assert instrument["provider_mappings"] == {
        "yfinance": {"ticker": "WEBN.DE", "currency": "EUR"}
    }


def test_switching_provider_preserves_each_ticker():
    conn = _db()

    update_instrument(
        conn, "IE0003XJA0J9", ticker="WEBN.XETRA", currency="EUR", source="eodhd"
    )
    alpha = update_instrument(
        conn, "IE0003XJA0J9", ticker="WEBN.DEX", currency="EUR", source="alphavantage"
    )

    assert alpha["ticker"] == "WEBN.DEX"
    assert alpha["provider_mappings"] == {
        "alphavantage": {"ticker": "WEBN.DEX", "currency": "EUR"},
        "eodhd": {"ticker": "WEBN.XETRA", "currency": "EUR"},
        "yfinance": {"ticker": "WEBN.DE", "currency": "EUR"},
    }

    yahoo = update_instrument(
        conn, "IE0003XJA0J9", ticker=None, currency=None, source="yfinance"
    )
    assert yahoo["ticker"] == "WEBN.DE"
    assert yahoo["currency"] == "EUR"


def test_empty_ticker_removes_only_selected_provider_mapping():
    conn = _db()
    update_instrument(
        conn, "IE0003XJA0J9", ticker="WEBN.XETRA", currency="EUR", source="eodhd"
    )

    result = update_instrument(
        conn, "IE0003XJA0J9", ticker="", currency="EUR", source="eodhd"
    )

    assert result["ticker"] is None
    assert "eodhd" not in result["provider_mappings"]
    assert result["provider_mappings"]["yfinance"]["ticker"] == "WEBN.DE"
