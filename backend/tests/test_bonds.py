"""Testy obligacji detalicznych: parser tabeli MF, przesunięcie o dzień zakupu, zakup (bez sieci)."""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta

import pytest

from app import bonds, importer
from app import cash as cash_mod
from app.db import SCHEMA

TEXT = (
    "TABELA ODSETKOWA\nEDO0334\nNABYTYCH W DNIACH OD 2024-03-01 DO 2024-03-31\n"
    "Okres odsetkowy: 1\nOprocentowanie w bieżącym okresie: 6,80%"
)
TABLE = [
    ["DZIEŃ\nM-CA", "2024-03", "2024-04"],
    ["01", "", "0,58"],
    ["02", "0,02", "0,60"],
    ["31", "0,56", None],  # 31 kwietnia nie istnieje — komórka pusta
]


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def _seed_series(conn, series="EDO0334", start=date(2024, 3, 1), days=1200):
    """Tabela syntetyczna: 0,02 zł odsetek dziennie od początku sprzedaży."""
    bonds.store_table(conn, {
        "series": series,
        "sale_start": start.isoformat(),
        "points": [((start + timedelta(days=n)).isoformat(), round(0.02 * n, 2)) for n in range(1, days)],
    })


def test_parse_table(monkeypatch):
    monkeypatch.setattr(bonds, "_pdf_text_tables", lambda _: (TEXT, [TABLE]))
    parsed = bonds.parse_table_pdf(b"%PDF-fake")
    assert parsed["series"] == "EDO0334"
    assert parsed["sale_start"] == "2024-03-01"
    assert parsed["points"] == [
        ("2024-03-02", 0.02), ("2024-03-31", 0.56), ("2024-04-01", 0.58), ("2024-04-02", 0.60),
    ]


def test_parse_old_layout_needs_period_start(monkeypatch):
    # tabele sprzed 2023: nagłówki miesięcy nieczytelne, brak początku sprzedaży w tekście
    old = [["a\nń e", "Ń\nE\nZ 8", "Y 8\nT 1"], ["1", "0,00", "0,23"], ["31", "0,22", ""]]
    monkeypatch.setattr(bonds, "_pdf_text_tables", lambda _: ("OBLIGACJI 10-LETNICH EDO0128", [old]))
    with pytest.raises(ValueError):
        bonds.parse_table_pdf(b"%PDF-old")
    parsed = bonds.parse_table_pdf(b"%PDF-old", "2018-12-01")
    assert parsed["sale_start"] is None
    assert parsed["points"] == [("2018-12-01", 0.0), ("2018-12-31", 0.22), ("2019-01-01", 0.23)]


def test_series_periods_from_mf_dropdowns():
    html = (
        '<option class="x" value="218715,coi" data-id="coi"> COI0328 </option>'
        '<option class="x" selected="selected" value="218717,edo"\n data-id="edo">\n EDO0334\n </option>'
        '<option value="20331,218717" data-id="218717"> 2024-03-01 -&gt; 2025-03-01 </option>'
        '<option value="99999,218715" data-id="218715"> 2024-03-01 -&gt; 2025-03-01 </option>'
        '<option value="21728,218717" data-id="218717"> 2025-03-01 -&gt; 2026-03-01 </option>'
    )
    assert bonds._series_periods(html, "EDO0334") == [
        ("20331", "2024-03-01", "2025-03-01"), ("21728", "2025-03-01", "2026-03-01"),
    ]
    with pytest.raises(ValueError):
        bonds._series_periods(html, "EDO0134")


def test_price_points_shift_by_purchase_day_and_stop_today():
    conn = _db()
    _seed_series(conn, start=date.today() - timedelta(days=400), days=800)  # tabela sięga w przyszłość
    start = date.today() - timedelta(days=400)
    bought = start + timedelta(days=14)
    inst = {"isin": f"EDO0334-{bought:%Y%m%d}", "ticker": "EDO0334"}
    points = dict(bonds.price_points(conn, inst, "", "2999-01-01"))
    assert min(points) == bought.isoformat() and points[bought.isoformat()] == 100.0
    assert max(points) == date.today().isoformat()  # żadnych przyszłych dat
    # dzień po zakupie = pierwszy dzień odsetek z tabeli, niezależnie od dnia zakupu
    assert points[(bought + timedelta(days=1)).isoformat()] == 100.02
    assert points[date.today().isoformat()] == round(100 + 0.02 * (400 - 14), 2)


def test_add_bond_purchase(monkeypatch):
    monkeypatch.setattr(bonds, "sync_series", lambda *a, **k: 0)
    conn = _db()
    _seed_series(conn)

    result = importer.add_bond_purchase(conn, series="edo0334", purchase_date="2024-03-15", quantity=10)
    isin = result["isin"]
    assert result["created"] and isin == "EDO0334-20240315"
    inst = conn.execute("SELECT * FROM instruments WHERE isin = ?", (isin,)).fetchone()
    assert (inst["ticker"], inst["currency"], inst["source"], inst["needs_config"]) == ("EDO0334", "PLN", "obligacje", 0)
    first = conn.execute("SELECT date, price FROM prices WHERE isin = ? ORDER BY date LIMIT 1", (isin,)).fetchone()
    assert tuple(first) == ("2024-03-15", 100.0)
    # księga gotówki nieaktywna → zakup jej nie włącza
    assert not cash_mod.has_external(conn)

    cash_mod.add_flow(conn, "2024-01-01", "deposit", 5000)
    importer.add_bond_purchase(conn, series="EDO0334", purchase_date="2024-03-20", quantity=5, price_pln=99.9)
    assert cash_mod.balance(conn) == 5000 - 1000  # drugi zakup pokryty własną wpłatą 499,50

    with pytest.raises(ValueError):
        importer.add_bond_purchase(conn, series="EDO0334", purchase_date="2025-03-15", quantity=1)
    with pytest.raises(ValueError):
        importer.add_bond_purchase(conn, series="COI0328", purchase_date="2024-03-15", quantity=1)


def test_missing_table_points_to_manual_upload(monkeypatch):
    def offline(*a, **k):
        raise bonds.httpx.ConnectError("offline")

    monkeypatch.setattr(bonds, "sync_series", offline)
    with pytest.raises(ValueError, match="PDF"):
        importer.add_bond_purchase(_db(), series="EDO0334", purchase_date="2024-03-15", quantity=1)
