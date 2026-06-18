"""Testy importu cen z CSV (ratunek, gdy Yahoo nie oddaje historii)."""
from __future__ import annotations

import sqlite3

import pytest

from app import prices as prices_mod
from app.db import SCHEMA

STOOQ_CSV = (
    "Data,Otwarcie,Najwyzszy,Najnizszy,Zamkniecie,Wolumen\n"
    "2026-04-08,5.191,5.191,5.152,5.154,2248\n"
    "2026-04-09,5.3,5.3,5.046,5.046,1240\n"
    "2026-06-18,4.68,4.68,4.399,4.565,4260\n"
).encode()


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.execute(
        "INSERT INTO instruments (isin, name, ticker, currency, source, active, needs_config) "
        "VALUES ('SE0024738389', 'ETNVCOIN50', 'ETNVCOIN50.WA', 'PLN', 'yfinance', 1, 0)"
    )
    return conn


def test_parse_stooq_close_column():
    rows = prices_mod.parse_price_csv(STOOQ_CSV)
    assert rows == [("2026-04-08", 5.154), ("2026-04-09", 5.046), ("2026-06-18", 4.565)]


def test_parse_accepts_english_headers_and_comma_decimal():
    csv = b"Date;Open;High;Low;Close;Volume\n2026-01-02;1;1;1;12,5;0\n"
    assert prices_mod.parse_price_csv(csv) == [("2026-01-02", 12.5)]


def test_parse_rejects_unknown_header():
    with pytest.raises(ValueError):
        prices_mod.parse_price_csv(b"foo,bar\n1,2\n")


def test_import_prices_requires_currency_when_missing():
    # Scenariusz ratunkowy: provider nigdy nie pobrał ceny → currency = NULL. Bez podanej
    # waluty import musi ODMÓWIĆ — nie zgadujemy PLN (stooq notuje też w USD/EUR/GBP).
    conn = _db()
    conn.execute("UPDATE instruments SET currency = NULL WHERE isin = 'SE0024738389'")
    with pytest.raises(ValueError):
        prices_mod.import_prices(conn, "SE0024738389", STOOQ_CSV)


def test_import_prices_sets_currency_when_provided():
    # Waluta NULL + podana jawnie (np. USD dla papieru notowanego w USD) → ustawiana.
    conn = _db()
    conn.execute("UPDATE instruments SET currency = NULL WHERE isin = 'SE0024738389'")
    result = prices_mod.import_prices(conn, "SE0024738389", STOOQ_CSV, currency="usd")
    assert result["currency"] == "USD"
    ccy = conn.execute("SELECT currency FROM instruments WHERE isin = 'SE0024738389'").fetchone()[0]
    assert ccy == "USD"


def test_import_prices_keeps_existing_currency():
    # Gdy waluta już jest i nie podajemy nowej — import jej NIE rusza.
    conn = _db()
    conn.execute("UPDATE instruments SET currency = 'EUR' WHERE isin = 'SE0024738389'")
    result = prices_mod.import_prices(conn, "SE0024738389", STOOQ_CSV)
    assert result["currency"] == "EUR"
    ccy = conn.execute("SELECT currency FROM instruments WHERE isin = 'SE0024738389'").fetchone()[0]
    assert ccy == "EUR"


def test_import_prices_writes_cache_and_overwrites():
    conn = _db()
    # Stara, błędna cena z Yahoo dla 2026-06-18 — import musi ją nadpisać.
    conn.execute(
        "INSERT INTO prices (isin, date, price, source) VALUES ('SE0024738389', '2026-06-18', 4.399, 'yfinance')"
    )
    result = prices_mod.import_prices(conn, "SE0024738389", STOOQ_CSV)

    assert result["imported"] == 3
    assert result["first_date"] == "2026-04-08"
    assert result["last_date"] == "2026-06-18"

    rows = conn.execute(
        "SELECT date, price, source FROM prices WHERE isin = 'SE0024738389' ORDER BY date"
    ).fetchall()
    assert len(rows) == 3
    overwritten = next(r for r in rows if r["date"] == "2026-06-18")
    assert overwritten["price"] == 4.565
    assert overwritten["source"] == "csv"
