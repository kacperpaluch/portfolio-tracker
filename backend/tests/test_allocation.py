"""Testy alokacji docelowej vs rzeczywistej."""
from __future__ import annotations

import sqlite3

import pytest

from app import allocation as alloc
from app import cash as cash_mod
from app.db import SCHEMA


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def _inst(conn, isin, category, ticker="X", source="stooq", ccy="PLN"):
    conn.execute(
        "INSERT INTO instruments (isin, name, ticker, currency, source, category, active, needs_config) "
        "VALUES (?, ?, ?, ?, ?, ?, 1, 0)",
        (isin, isin, ticker, ccy, source, category),
    )


def _tx(conn, isin, qty, value_pln, h):
    ts = "2026-01-01T10:00:00"
    conn.execute(
        "INSERT INTO transactions (ts, isin, type, quantity, price_pln, value_pln, commission_pln, import_hash) "
        "VALUES (?, ?, 'BUY', ?, ?, ?, 0, ?)",
        (ts, isin, qty, value_pln / qty, value_pln, h),
    )
    # Odzwierciedl wpływ kupna na gotówkę (jak robi to importer).
    cash_mod.record_trade_cash(conn, ts, "BUY", value_pln, h)


def _price(conn, isin, price):
    conn.execute("INSERT INTO prices (isin, date, price, source) VALUES (?, '2026-06-16', ?, 'stooq')", (isin, price))


def test_actual_allocation_and_drift():
    conn = _db()
    _inst(conn, "AKC", "Akcje")
    _inst(conn, "OBL", "Obligacje")
    _tx(conn, "AKC", 10, 600, "h1")
    _tx(conn, "OBL", 10, 400, "h2")
    _price(conn, "AKC", 60)  # wartość 600
    _price(conn, "OBL", 40)  # wartość 400
    conn.commit()
    # Cel: 50/50, rzeczywiście 600/400 = 60/40.
    alloc.set_targets(conn, {"Akcje": 50, "Obligacje": 50})

    res = alloc.compute(conn)
    by = {g["category"]: g for g in res["groups"]}
    assert res["total_pln"] == pytest.approx(1000.0)
    assert by["Akcje"]["actual_pct"] == pytest.approx(60.0)
    assert by["Akcje"]["drift_pp"] == pytest.approx(10.0)
    # Rebalans Akcje: cel 50% z 1000 = 500, jest 600 -> sprzedać 100.
    assert by["Akcje"]["rebalance_pln"] == pytest.approx(-100.0)
    assert by["Obligacje"]["rebalance_pln"] == pytest.approx(100.0)
    assert res["target_complete"] is True


def test_cash_as_group():
    conn = _db()
    _inst(conn, "AKC", "Akcje")
    _tx(conn, "AKC", 10, 900, "h1")
    _price(conn, "AKC", 90)  # wartość 900
    cash_mod.add_flow(conn, "2026-01-01", "deposit", 1000)  # gotówka 1000 - 900 = 100
    conn.commit()
    res = alloc.compute(conn)
    by = {g["category"]: g for g in res["groups"]}
    assert "Gotówka" in by
    assert by["Gotówka"]["actual_pln"] == pytest.approx(100.0)
    assert res["total_pln"] == pytest.approx(1000.0)
    assert by["Gotówka"]["actual_pct"] == pytest.approx(10.0)


def test_unassigned_group():
    conn = _db()
    _inst(conn, "AKC", None)  # brak kategorii
    _tx(conn, "AKC", 10, 500, "h1")
    _price(conn, "AKC", 50)
    conn.commit()
    res = alloc.compute(conn)
    by = {g["category"]: g for g in res["groups"]}
    assert "Nieprzypisane" in by
    assert by["Nieprzypisane"]["actual_pln"] == pytest.approx(500.0)
