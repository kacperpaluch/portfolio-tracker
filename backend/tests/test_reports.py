from __future__ import annotations

import sqlite3
from datetime import date

import pytest

from app.db import SCHEMA
from app.reports import _comparison_range, build, export_csv


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.execute(
        "INSERT INTO instruments (isin, name, ticker, currency, source, category, active, needs_config) "
        "VALUES ('A', 'ETF A', 'A.WA', 'PLN', 'test', 'Akcje', 1, 0)"
    )
    conn.execute(
        "INSERT INTO transactions (ts, isin, type, quantity, price_pln, value_pln, commission_pln, import_hash) "
        "VALUES ('2026-06-01T10:00:00', 'A', 'BUY', 10, 100, 1000, 5, 'buy')"
    )
    conn.execute(
        "INSERT INTO transactions (ts, isin, type, quantity, price_pln, value_pln, commission_pln, import_hash) "
        "VALUES ('2026-07-15T10:00:00', 'A', 'SELL', 2, 108, 216, 3, 'sell')"
    )
    conn.executemany(
        "INSERT INTO cash_flows (ts, kind, amount_pln, import_hash) VALUES (?, ?, ?, ?)",
        [
            ('2026-06-01T08:00:00', 'deposit', 2000, 'deposit'),
            ('2026-06-01T10:00:00', 'buy', -1000, 'cash-buy'),
            ('2026-07-15T10:00:00', 'sell', 216, 'cash-sell'),
        ],
    )
    conn.executemany(
        "INSERT INTO prices (isin, date, price, source) VALUES ('A', ?, ?, 'test')",
        [('2026-06-01', 100), ('2026-06-30', 100), ('2026-07-15', 108), ('2026-07-31', 110)],
    )
    conn.commit()
    return conn


def test_period_report_calculates_result_and_attribution():
    report = build(_db(), date(2026, 7, 1), date(2026, 7, 31))
    period = report["period"]
    assert period["opening_value_pln"] == 2000
    assert period["closing_value_pln"] == 2096
    assert period["result_pln"] == 96
    assert period["twr"] == pytest.approx(0.048, abs=1e-4)
    assert period["activity"] == {"transactions": 1, "buys": 0, "sells": 1, "commissions_pln": 3}
    assert period["attribution"]["totals"]["realized_pl_pln"] == 16
    assert period["attribution"]["totals"]["unrealized_change_pln"] == 80
    assert period["attribution"]["instruments"][0]["total_pl_pln"] == 96


def test_report_has_comparison_monthly_returns_and_quality():
    report = build(_db(), date(2026, 7, 1), date(2026, 7, 31))
    assert report["comparison"] is not None
    july = next(row for row in report["monthly_returns"] if row["year"] == 2026)["months"]["7"]
    assert july == pytest.approx(4.8, abs=0.01)
    assert report["quality"]["status"] in {"good", "warning", "error"}


def test_calendar_comparisons_align_month_and_year():
    conn = _db()
    monthly = build(conn, date(2026, 7, 1), date(2026, 7, 31))["comparison"]
    assert monthly["requested_from"] == "2026-06-01"
    assert monthly["requested_to"] == "2026-06-30"
    yearly = build(conn, date(2026, 1, 1), date(2026, 7, 31))["comparison"]
    assert yearly is None  # historia testowa zaczyna się dopiero w czerwcu 2026
    assert _comparison_range(date(2026, 1, 1), date(2026, 7, 31)) == (
        date(2025, 1, 1), date(2025, 7, 31)
    )


def test_report_csv_contains_sections_and_utf8_bom():
    text = export_csv(build(_db(), date(2026, 7, 1), date(2026, 7, 31)))
    assert text.startswith("\ufeff")
    assert "Raport portfela;2026-07-01;2026-07-31" in text
    assert "ETF A;A.WA;Akcje;PLN;96.0;16.0;80.0" in text


def test_report_rejects_invalid_range():
    with pytest.raises(ValueError, match="początkowa"):
        build(_db(), date(2026, 8, 1), date(2026, 7, 1))
