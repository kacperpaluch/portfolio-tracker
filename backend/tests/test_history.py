"""Testy zwrotów w okresach (portfolio_returns) — ceny/FX wstrzykiwane ręcznie."""
from __future__ import annotations

import sqlite3

import pytest

from app.db import SCHEMA
from app.history import portfolio_returns


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def _setup(conn):
    # Instrument w PLN (kurs = 1.0, bez FX). Kup 10 szt. @ 100 PLN = 1000 PLN.
    conn.execute(
        "INSERT INTO instruments (isin, name, ticker, currency, source, active, needs_config) "
        "VALUES ('PL01', 'Test ETF', 'X.WA', 'PLN', 'yfinance', 1, 0)"
    )
    conn.execute(
        "INSERT INTO transactions (ts, isin, type, quantity, price_pln, value_pln, commission_pln, import_hash) "
        "VALUES ('2025-01-01T10:00:00', 'PL01', 'BUY', 10, 100, 1000, 0, 'h1')"
    )
    # Cena: 100 -> 120 (od 2025-06-01). Forward-fill utrzyma 120 do dziś.
    conn.execute("INSERT INTO prices (isin, date, price, source) VALUES ('PL01','2025-01-01',100,'yfinance')")
    conn.execute("INSERT INTO prices (isin, date, price, source) VALUES ('PL01','2025-06-01',120,'yfinance')")
    conn.commit()


def test_returns_has_all_periods():
    conn = _db()
    _setup(conn)
    r = portfolio_returns(conn)
    assert set(r.keys()) == {"1m", "3m", "ytd", "1y", "all"}


def test_returns_all_period_cumulative_twr():
    conn = _db()
    _setup(conn)
    r = portfolio_returns(conn)
    # Wartość 1000 -> 1200 (cena 100 -> 120), wkład 1000 na starcie nie zaburza TWR.
    assert r["all"]["twr"] == pytest.approx(0.20, abs=1e-3)
    assert r["all"]["xirr"] is not None and r["all"]["xirr"] > 0


def test_returns_ytd_flat_when_no_move_this_year():
    conn = _db()
    _setup(conn)
    r = portfolio_returns(conn)
    # Cały ruch ceny był w 2025; od 2026-01-01 wartość stała (120) -> YTD ~0%.
    assert r["ytd"]["twr"] == pytest.approx(0.0, abs=1e-6)


def test_returns_empty_without_transactions():
    conn = _db()
    assert portfolio_returns(conn) == {}
