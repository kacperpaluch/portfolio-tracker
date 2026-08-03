from __future__ import annotations

import sqlite3
from datetime import date

from app import cash as cash_mod
from app.data_quality import inspect
from app.db import SCHEMA


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def test_quality_good_for_complete_pln_portfolio():
    conn = _db()
    conn.execute(
        "INSERT INTO instruments "
        "(isin, name, ticker, currency, source, category, active, needs_config) "
        "VALUES ('A', 'ETF A', 'A.WA', 'PLN', 'yfinance', 'Akcje', 1, 0)"
    )
    conn.execute(
        "INSERT INTO transactions "
        "(ts, isin, type, quantity, price_pln, value_pln, commission_pln, import_hash) "
        "VALUES ('2026-01-01T10:00:00', 'A', 'BUY', 10, 100, 1000, 0, 'h1')"
    )
    cash_mod.record_trade_cash(conn, "2026-01-01T10:00:00", "BUY", 1000, "h1")
    conn.execute(
        "INSERT INTO prices (isin, date, price, source) VALUES ('A', ?, 110, 'test')",
        (date.today().isoformat(),),
    )
    conn.execute("INSERT INTO target_allocation VALUES ('Akcje', 100)")
    conn.commit()

    result = inspect(conn)
    assert result["status"] == "good"
    assert result["summary"]["issues"] == 0
    assert result["stats"]["fully_valued"] is True


def test_quality_detects_missing_configuration_and_price():
    conn = _db()
    conn.execute(
        "INSERT INTO instruments (isin, name, active, needs_config) VALUES ('A', 'ETF A', 1, 1)"
    )
    conn.execute(
        "INSERT INTO transactions "
        "(ts, isin, type, quantity, price_pln, value_pln, commission_pln, import_hash) "
        "VALUES ('2026-01-01T10:00:00', 'A', 'BUY', 1, 100, 100, 0, 'h1')"
    )
    cash_mod.record_trade_cash(conn, "2026-01-01T10:00:00", "BUY", 100, "h1")
    conn.commit()

    result = inspect(conn)
    codes = {issue["code"] for issue in result["issues"]}
    assert result["status"] == "error"
    assert {"instrument_config", "missing_category", "missing_price"} <= codes


def test_quality_detects_missing_provider_key(monkeypatch):
    monkeypatch.delenv("EODHD_API_KEY", raising=False)
    conn = _db()
    conn.execute(
        "INSERT INTO instruments "
        "(isin, name, ticker, currency, source, category, active, needs_config) "
        "VALUES ('A', 'ETF A', 'A.XETRA', 'EUR', 'eodhd', 'Akcje', 1, 0)"
    )
    conn.execute(
        "INSERT INTO transactions "
        "(ts, isin, type, quantity, price_pln, value_pln, commission_pln, import_hash) "
        "VALUES ('2026-01-01T10:00:00', 'A', 'BUY', 1, 100, 100, 0, 'h1')"
    )
    cash_mod.record_trade_cash(conn, "2026-01-01T10:00:00", "BUY", 100, "h1")
    conn.commit()

    result = inspect(conn)

    assert "provider_config" in {issue["code"] for issue in result["issues"]}
