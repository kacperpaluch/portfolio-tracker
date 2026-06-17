"""Testy agregacji pozycji i wyceny (bez sieci — ceny/FX wstrzykiwane ręcznie)."""
from __future__ import annotations

import sqlite3

import pytest

from app.db import SCHEMA
from app.portfolio import compute_positions, value_positions


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def _add_instrument(conn, isin, name, currency, ticker="X", source="yfinance"):
    conn.execute(
        "INSERT INTO instruments (isin, name, ticker, currency, source, active, needs_config) "
        "VALUES (?, ?, ?, ?, ?, 1, 0)",
        (isin, name, ticker, currency, source),
    )


def _add_tx(conn, ts, isin, typ, qty, value_pln):
    price = value_pln / qty
    conn.execute(
        "INSERT INTO transactions (ts, isin, type, quantity, price_pln, value_pln, commission_pln, import_hash) "
        "VALUES (?, ?, ?, ?, ?, ?, 0, ?)",
        (ts, isin, typ, qty, price, value_pln, f"{ts}{isin}{typ}{qty}"),
    )


def test_average_cost_with_sell():
    conn = _db()
    _add_instrument(conn, "TEST1", "Test ETF", "EUR")
    # Kup 10 @ 100 PLN (1000), kup 10 @ 120 PLN (1200) -> avg 110, qty 20, cost 2200.
    _add_tx(conn, "2026-01-01T10:00:00", "TEST1", "BUY", 10, 1000)
    _add_tx(conn, "2026-02-01T10:00:00", "TEST1", "BUY", 10, 1200)
    # Sprzedaj 5 -> koszt spada o 5*110=550 -> qty 15, cost 1650.
    _add_tx(conn, "2026-03-01T10:00:00", "TEST1", "SELL", 5, 600)
    conn.commit()

    pos, realized = compute_positions(conn)
    assert len(pos) == 1
    p = pos[0]
    assert p["quantity"] == 15
    assert p["cost_pln"] == pytest.approx(1650.0)
    assert p["avg_cost_pln"] == pytest.approx(110.0)
    # Sprzedaż 5 @ 120 (600), średni koszt 110 -> zrealizowany zysk 5*(120-110)=50.
    assert realized == pytest.approx(50.0)


def test_fully_sold_position_excluded():
    conn = _db()
    _add_instrument(conn, "TEST2", "Gone ETF", "PLN", source="stooq")
    _add_tx(conn, "2026-01-01T10:00:00", "TEST2", "BUY", 5, 500)
    _add_tx(conn, "2026-02-01T10:00:00", "TEST2", "SELL", 5, 600)
    conn.commit()
    positions, realized = compute_positions(conn)
    assert positions == []
    # Cała pozycja sprzedana ze 100 zyskiem -> zrealizowany zysk 100.
    assert realized == pytest.approx(100.0)


def test_valuation_and_pl_with_fx():
    conn = _db()
    _add_instrument(conn, "EURETF", "Euro ETF", "EUR")
    # Kupione za 1000 PLN, 100 jednostek -> koszt 1000.
    _add_tx(conn, "2026-01-01T10:00:00", "EURETF", "BUY", 100, 1000)
    # Wstrzyknij cenę 3 EUR/szt i kurs 4,30 EUR/PLN.
    conn.execute("INSERT INTO prices (isin, date, price, source) VALUES ('EURETF','2026-06-16',3.0,'yfinance')")
    conn.execute("INSERT INTO fx_rates (date, currency, rate_to_pln) VALUES ('2026-06-16','EUR',4.30)")
    conn.commit()

    result = value_positions(conn, refresh=False)
    p = result["positions"][0]
    # wartość = 3 * 100 * 4.30 = 1290 PLN; P/L = 290; % = 29.
    assert p["value_pln"] == pytest.approx(1290.0)
    assert p["pl_pln"] == pytest.approx(290.0)
    assert p["pl_pct"] == pytest.approx(29.0)
    assert result["totals"]["fully_valued"] is True
    assert result["totals"]["value_pln"] == pytest.approx(1290.0)


def test_pln_position_no_fx():
    conn = _db()
    _add_instrument(conn, "PLNETF", "GPW ETF", "PLN", source="stooq")
    _add_tx(conn, "2026-01-01T10:00:00", "PLNETF", "BUY", 10, 1000)  # 100 PLN/szt
    conn.execute("INSERT INTO prices (isin, date, price, source) VALUES ('PLNETF','2026-06-16',105.0,'stooq')")
    conn.commit()
    result = value_positions(conn, refresh=False)
    p = result["positions"][0]
    # wartość = 105 * 10 * 1 = 1050; P/L = 50.
    assert p["fx_rate"] == 1.0
    assert p["value_pln"] == pytest.approx(1050.0)
    assert p["pl_pln"] == pytest.approx(50.0)


def test_unconfigured_instrument_partial_valuation():
    conn = _db()
    # Instrument bez ceny -> brak wyceny, ale koszt liczony; totals niekompletne.
    _add_instrument(conn, "NOPRICE", "No price ETF", "EUR")
    _add_tx(conn, "2026-01-01T10:00:00", "NOPRICE", "BUY", 10, 500)
    conn.commit()
    result = value_positions(conn, refresh=False)
    assert result["positions"][0]["value_pln"] is None
    assert result["totals"]["fully_valued"] is False
    assert result["totals"]["cost_pln"] == pytest.approx(500.0)
