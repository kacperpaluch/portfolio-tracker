"""Testy parsowania i importu CSV."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.db import SCHEMA
from app.importer import import_transactions, parse_csv, parse_number

CSV_PATH = Path(__file__).resolve().parents[2] / "hisPW-10.csv"


def _csv_bytes() -> bytes:
    return CSV_PATH.read_bytes()


def _mem_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def test_parse_number():
    assert parse_number("34,3375") == pytest.approx(34.3375)
    assert parse_number("1 234,56") == pytest.approx(1234.56)
    assert parse_number("0,00") == 0.0


def test_parse_csv_basic():
    rows = parse_csv(_csv_bytes())
    # Plik ma 43 wiersze danych (linie 2-44).
    assert len(rows) == 43
    # Pierwszy wiersz: sprzedaż? Nie — to kupno Invesco FTSE All-World.
    first = rows[0]
    assert first["isin"] == "IE000716YHJ7"
    assert first["type"] == "BUY"
    assert first["quantity"] == 2
    assert first["price_pln"] == pytest.approx(34.3375)


def test_parse_handles_sells():
    rows = parse_csv(_csv_bytes())
    sells = [r for r in rows if r["type"] == "SELL"]
    # W pliku jest 5 sprzedaży: cztery z 15.06 + jedna z 01.04 (Xtrackers Pakistan).
    assert len(sells) == 5
    assert all(r["value_pln"] > 0 for r in sells)


def test_import_idempotent():
    conn = _mem_db()
    content = _csv_bytes()
    first = import_transactions(conn, content)
    assert first["imported"] == 43
    assert first["skipped_duplicates"] == 0
    # Ponowny import nie dubluje.
    second = import_transactions(conn, content)
    assert second["imported"] == 0
    assert second["skipped_duplicates"] == 43
    total = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    assert total == 43


def test_instruments_created_with_seed():
    conn = _mem_db()
    import_transactions(conn, _csv_bytes())
    # ETF PZU: zweryfikowany ticker GPW (.WA), PLN, gotowy do wyceny.
    pzu = conn.execute(
        "SELECT ticker, currency, source, needs_config FROM instruments WHERE isin = ?",
        ("PLPZUMW00018",),
    ).fetchone()
    assert pzu["ticker"] == "ETFPZUWORLD.WA"
    assert pzu["currency"] == "PLN"
    assert pzu["source"] == "yfinance"
    assert pzu["needs_config"] == 0

    # ETF w EUR (Invesco FTSE All-World na Xetrze).
    inv = conn.execute(
        "SELECT ticker, currency, source, needs_config FROM instruments WHERE isin = ?",
        ("IE000716YHJ7",),
    ).fetchone()
    assert inv["ticker"] == "FWIA.DE"
    assert inv["currency"] == "EUR"
    assert inv["needs_config"] == 0


def test_position_quantities():
    """Sanity: dla Invesco FTSE All-World suma BUY - SELL = netto posiadanych."""
    conn = _mem_db()
    import_transactions(conn, _csv_bytes())
    rows = conn.execute(
        "SELECT type, quantity FROM transactions WHERE isin = ?", ("IE000716YHJ7",)
    ).fetchall()
    net = sum(r["quantity"] if r["type"] == "BUY" else -r["quantity"] for r in rows)
    # Z pliku: kupna 2+1+2+2+16+10+10+12 = 55, brak sprzedaży -> 55.
    assert net == 55
