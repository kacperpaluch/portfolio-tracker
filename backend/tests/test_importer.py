"""Testy parsowania i importu CSV (na fikcyjnym pliku przykładowym)."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.db import SCHEMA
from app.importer import import_transactions, parse_csv, parse_number

# Fikcyjny plik przykładowy commitowany do repo (prawdziwe dane brokera są gitignorowane).
CSV_PATH = Path(__file__).resolve().parent / "sample_hisPW.csv"


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
    assert len(rows) == 5
    first = rows[0]
    assert first["isin"] == "IE000716YHJ7"
    assert first["type"] == "BUY"
    assert first["quantity"] == 10
    assert first["price_pln"] == pytest.approx(30.00)


def test_parse_handles_sells():
    rows = parse_csv(_csv_bytes())
    sells = [r for r in rows if r["type"] == "SELL"]
    assert len(sells) == 1
    assert sells[0]["isin"] == "IE000716YHJ7"
    assert sells[0]["value_pln"] == pytest.approx(175.00)


def test_import_idempotent():
    conn = _mem_db()
    content = _csv_bytes()
    first = import_transactions(conn, content)
    assert first["imported"] == 5
    assert first["skipped_duplicates"] == 0
    # Ponowny import nie dubluje.
    second = import_transactions(conn, content)
    assert second["imported"] == 0
    assert second["skipped_duplicates"] == 5
    total = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    assert total == 5


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
        "SELECT ticker, currency, needs_config FROM instruments WHERE isin = ?",
        ("IE000716YHJ7",),
    ).fetchone()
    assert inv["ticker"] == "FWIA.DE"
    assert inv["currency"] == "EUR"
    assert inv["needs_config"] == 0

    # Nieznany ISIN -> brak tickera, wymaga konfiguracji.
    unknown = conn.execute(
        "SELECT ticker, needs_config FROM instruments WHERE isin = ?", ("XX0000000000",)
    ).fetchone()
    assert unknown["ticker"] is None
    assert unknown["needs_config"] == 1


def test_position_quantities():
    """Netto Invesco FTSE All-World = 10 + 10 − 5 = 15."""
    conn = _mem_db()
    import_transactions(conn, _csv_bytes())
    rows = conn.execute(
        "SELECT type, quantity FROM transactions WHERE isin = ?", ("IE000716YHJ7",)
    ).fetchall()
    net = sum(r["quantity"] if r["type"] == "BUY" else -r["quantity"] for r in rows)
    assert net == 15


def test_trade_cash_flows_recorded():
    """Import zapisuje wpływ transakcji na gotówkę (kupno −, sprzedaż +)."""
    conn = _mem_db()
    import_transactions(conn, _csv_bytes())
    # Suma przepływów z transakcji = sprzedaże − kupna = 175 − (300+500+320+150) = −1095.
    total = conn.execute(
        "SELECT COALESCE(SUM(amount_pln), 0) FROM cash_flows WHERE kind IN ('buy', 'sell')"
    ).fetchone()[0]
    assert total == pytest.approx(-1095.00)
