"""Testy digestu /api/summary — ceny/FX wstrzykiwane ręcznie, bez sieci."""
from __future__ import annotations

import sqlite3

import pytest

from app.allocation import set_targets
from app.db import SCHEMA
from app.summary import build


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def _setup(conn):
    conn.execute(
        "INSERT INTO instruments (isin, name, ticker, currency, source, active, needs_config, category) "
        "VALUES ('PL01', 'Test ETF', 'X.WA', 'PLN', 'yfinance', 1, 0, 'Akcje')"
    )
    conn.execute(
        "INSERT INTO transactions (ts, isin, type, quantity, price_pln, value_pln, commission_pln, import_hash) "
        "VALUES ('2025-01-01T10:00:00', 'PL01', 'BUY', 10, 100, 1000, 0, 'h1')"
    )
    conn.execute("INSERT INTO prices (isin, date, price, source) VALUES ('PL01','2025-01-01',100,'yfinance')")
    conn.execute("INSERT INTO prices (isin, date, price, source) VALUES ('PL01','2025-06-01',120,'yfinance')")
    conn.commit()


def test_summary_structure_and_account():
    conn = _db()
    _setup(conn)
    s = build(conn)
    assert set(s.keys()) == {"generated_at", "account", "pl", "change", "returns", "allocation"}
    # Wartość: 10 szt. * 120 PLN = 1200, brak gotówki.
    assert s["account"]["value_pln"] == pytest.approx(1200.0)
    assert s["account"]["etf_value_pln"] == pytest.approx(1200.0)
    # Zysk całkowity = 1200 - 1000 = 200.
    assert s["pl"]["total_pln"] == pytest.approx(200.0)


def test_summary_returns_periods_present():
    conn = _db()
    _setup(conn)
    s = build(conn)
    assert set(s["returns"].keys()) == {"xirr", "twr", "ytd", "1y", "all"}
    assert s["returns"]["all"] == pytest.approx(0.20, abs=1e-3)


def test_summary_allocation_vs_target():
    conn = _db()
    _setup(conn)
    set_targets(conn, {"Akcje": 60.0})
    s = build(conn)
    a = s["allocation"]
    # Cała wartość w jednej grupie -> 100% rzeczywistych vs 60% docelowych -> dryf +40 p.p.
    grp = next(g for g in a["groups"] if g["category"] == "Akcje")
    assert grp["target_pct"] == pytest.approx(60.0)
    assert grp["actual_pct"] == pytest.approx(100.0)
    assert grp["drift_pp"] == pytest.approx(40.0)
    # Rebalans: 60% * 1200 - 1200 = -480 (do sprzedania).
    assert grp["rebalance_pln"] == pytest.approx(-480.0)
    assert a["max_drift"]["category"] == "Akcje"


def test_summary_no_targets_no_max_drift():
    conn = _db()
    _setup(conn)
    s = build(conn)
    assert s["allocation"]["max_drift"] is None
    assert s["allocation"]["target_complete"] is False
