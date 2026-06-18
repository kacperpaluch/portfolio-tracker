"""Testy benchmarku inflacyjnego (HICP + X%) — indeks CPI wstrzykiwany ręcznie, bez sieci."""
from __future__ import annotations

import sqlite3
from datetime import date

import pytest

from app import cpi
from app.db import SCHEMA
from app.history import portfolio_history


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def _setup(conn):
    """PLN ETF: kup 10 @ 100 = 1000 PLN dnia 2025-01-01, cena stała (forward-fill 100)."""
    conn.execute(
        "INSERT INTO instruments (isin, name, ticker, currency, source, active, needs_config) "
        "VALUES ('PL01', 'Test ETF', 'X.WA', 'PLN', 'yfinance', 1, 0)"
    )
    conn.execute(
        "INSERT INTO transactions (ts, isin, type, quantity, price_pln, value_pln, commission_pln, import_hash) "
        "VALUES ('2025-01-01T10:00:00', 'PL01', 'BUY', 10, 100, 1000, 0, 'h1')"
    )
    conn.execute("INSERT INTO prices (isin, date, price, source) VALUES ('PL01','2025-01-01',100,'yfinance')")
    conn.commit()


def _seed_cpi(conn, points):
    for month, idx in points:
        conn.execute("INSERT OR REPLACE INTO cpi_index (month, idx) VALUES (?, ?)", (month, idx))
    conn.commit()


# --- index_at (czysta interpolacja) -------------------------------------------

def test_index_at_endpoints_and_interpolation():
    pts = [(date(2025, 1, 1), 100.0), (date(2025, 2, 1), 110.0)]
    assert cpi.index_at(pts, date(2025, 1, 1)) == pytest.approx(100.0)
    assert cpi.index_at(pts, date(2025, 2, 1)) == pytest.approx(110.0)
    # 15/31 dnia drogi między 100 a 110.
    assert cpi.index_at(pts, date(2025, 1, 16)) == pytest.approx(100 + 10 * 15 / 31, abs=1e-6)


def test_index_at_clamps_outside_range():
    pts = [(date(2025, 1, 1), 100.0), (date(2025, 2, 1), 110.0)]
    assert cpi.index_at(pts, date(2024, 6, 1)) == pytest.approx(100.0)  # przed pierwszym
    assert cpi.index_at(pts, date(2030, 1, 1)) == pytest.approx(110.0)  # po ostatnim (forward-fill)


def test_index_at_empty_is_none():
    assert cpi.index_at([], date(2025, 1, 1)) is None


# --- benchmark inflacyjny w portfolio_history ---------------------------------

def test_cpi_benchmark_tracks_inflation_no_spread():
    conn = _db()
    _setup(conn)
    # Inflacja +10% w pół roku (indeks 100 -> 110 między 2025-01-01 a 2025-07-01).
    _seed_cpi(conn, [("2025-01-01", 100.0), ("2025-07-01", 110.0)])
    series = portfolio_history(conn, cpi_spread=0.0)
    by_date = {r["date"]: r for r in series}
    # Dzień wpłaty: mnożnik 1.0 -> benchmark == wkład (1000), stopa 0%.
    assert by_date["2025-01-01"]["benchmark_cpi_pln"] == pytest.approx(1000.0)
    assert by_date["2025-01-01"]["benchmark_cpi_pct"] == pytest.approx(0.0, abs=1e-6)
    # Po pół roku: 1000 * 110/100 = 1100, stopa +10%.
    assert by_date["2025-07-01"]["benchmark_cpi_pln"] == pytest.approx(1100.0, abs=0.01)
    assert by_date["2025-07-01"]["benchmark_cpi_pct"] == pytest.approx(10.0, abs=0.01)


def test_cpi_benchmark_spread_adds_premium():
    conn = _db()
    _setup(conn)
    _seed_cpi(conn, [("2025-01-01", 100.0), ("2025-07-01", 110.0)])
    base = {r["date"]: r for r in portfolio_history(conn, cpi_spread=0.0)}
    spread = {r["date"]: r for r in portfolio_history(conn, cpi_spread=0.03)}
    # Premia +3%/rok podnosi benchmark ponad samą inflację.
    assert spread["2025-07-01"]["benchmark_cpi_pln"] > base["2025-07-01"]["benchmark_cpi_pln"]


def test_cpi_benchmark_none_without_data():
    """Brak danych CPI w cache → pola benchmarku inflacyjnego = None (linia się nie pokaże)."""
    conn = _db()
    _setup(conn)
    series = portfolio_history(conn)
    assert all(r["benchmark_cpi_pln"] is None for r in series)
    assert all(r["benchmark_cpi_pct"] is None for r in series)
    # Stały benchmark dalej działa.
    assert series[-1]["benchmark_pln"] is not None
