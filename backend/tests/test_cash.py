"""Testy księgi gotówki i zysku całkowitego (zrealizowany + niezrealizowany)."""
from __future__ import annotations

import sqlite3

import pytest

from app import cash as cash_mod
from app.db import SCHEMA
from app.portfolio import value_positions


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def _inst(conn, isin, ccy, ticker="X", source="yfinance"):
    conn.execute(
        "INSERT INTO instruments (isin, name, ticker, currency, source, active, needs_config) "
        "VALUES (?, ?, ?, ?, ?, 1, 0)",
        (isin, isin, ticker, ccy, source),
    )


def _tx(conn, ts, isin, typ, qty, value_pln, h):
    conn.execute(
        "INSERT INTO transactions (ts, isin, type, quantity, price_pln, value_pln, commission_pln, import_hash) "
        "VALUES (?, ?, ?, ?, ?, ?, 0, ?)",
        (ts, isin, typ, qty, value_pln / qty, value_pln, h),
    )
    cash_mod.record_trade_cash(conn, ts, typ, value_pln, h)


def test_cash_balance_nets_deposits_and_trades():
    conn = _db()
    _inst(conn, "P", "PLN", source="stooq")
    cash_mod.add_flow(conn, "2026-01-01", "deposit", 1000)
    _tx(conn, "2026-01-02T10:00:00", "P", "BUY", 5, 500, "h1")   # gotówka -500
    _tx(conn, "2026-02-01T10:00:00", "P", "SELL", 2, 240, "h2")  # gotówka +240
    conn.commit()
    # 1000 - 500 + 240 = 740
    assert cash_mod.balance(conn) == pytest.approx(740.0)
    assert cash_mod.deposits_total(conn) == pytest.approx(1000.0)


def test_withdrawal_and_delete():
    conn = _db()
    cash_mod.add_flow(conn, "2026-01-01", "deposit", 1000)
    w = cash_mod.add_flow(conn, "2026-03-01", "withdrawal", 300)
    assert cash_mod.balance(conn) == pytest.approx(700.0)
    assert cash_mod.delete_flow(conn, w["id"]) is True
    assert cash_mod.balance(conn) == pytest.approx(1000.0)


def test_total_pl_includes_realized_and_cash():
    conn = _db()
    _inst(conn, "P", "PLN", source="stooq")
    cash_mod.add_flow(conn, "2026-01-01", "deposit", 2000)
    # Kup 10 @100 (1000), sprzedaj 4 @130 (520) -> zrealizowany 4*(130-100)=120.
    _tx(conn, "2026-01-02T10:00:00", "P", "BUY", 10, 1000, "h1")
    _tx(conn, "2026-02-01T10:00:00", "P", "SELL", 4, 520, "h2")
    # Bieżąca cena 150 -> pozostałe 6 szt warte 900, koszt 600 -> niezrealizowany 300.
    conn.execute("INSERT INTO prices (isin, date, price, source) VALUES ('P','2026-06-16',150.0,'stooq')")
    conn.commit()

    t = value_positions(conn, refresh=False)["totals"]
    assert t["realized_pl_pln"] == pytest.approx(120.0)
    assert t["unrealized_pl_pln"] == pytest.approx(300.0)
    assert t["total_pl_pln"] == pytest.approx(420.0)
    # Gotówka: 2000 -1000 +520 = 1520; wartość konta = 900 ETF + 1520 = 2420.
    assert t["cash_pln"] == pytest.approx(1520.0)
    assert t["portfolio_value_pln"] == pytest.approx(2420.0)
