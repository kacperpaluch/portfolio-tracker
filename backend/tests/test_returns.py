"""Testy XIRR."""
from __future__ import annotations

from datetime import date

import pytest

from app.returns import twr, twr_detail, xirr


def test_xirr_simple_doubling_one_year():
    # -1000 dziś, +1100 za rok -> 10%.
    cfs = [(date(2025, 1, 1), -1000.0), (date(2026, 1, 1), 1100.0)]
    assert xirr(cfs) == pytest.approx(0.10, abs=1e-3)


def test_xirr_negative_return():
    cfs = [(date(2025, 1, 1), -1000.0), (date(2026, 1, 1), 900.0)]
    assert xirr(cfs) == pytest.approx(-0.10, abs=1e-3)


def test_xirr_multiple_contributions():
    # Dwie wpłaty po 1000, wartość końcowa 2200 po ~1 i ~0.5 roku.
    cfs = [
        (date(2025, 1, 1), -1000.0),
        (date(2025, 7, 1), -1000.0),
        (date(2026, 1, 1), 2200.0),
    ]
    r = xirr(cfs)
    assert r is not None and 0.10 < r < 0.30


def test_xirr_requires_sign_change():
    assert xirr([(date(2025, 1, 1), -100.0), (date(2026, 1, 1), -50.0)]) is None
    assert xirr([(date(2025, 1, 1), 100.0)]) is None


def test_twr_no_cashflows_equals_simple_return():
    series = [(date(2025, 1, 1), 1000.0), (date(2026, 1, 1), 1100.0)]
    assert twr(series, {}) == pytest.approx(0.10, abs=1e-6)


def test_twr_neutralizes_deposit_timing():
    # +6,67% w I poł. roku, potem wpłata 500, +10% w II poł. -> TWR ~17,33% (wpłata nie zaburza).
    series = [
        (date(2025, 1, 1), 1000.0),
        (date(2025, 7, 1), 1600.0),  # 1000 -> 1066.67 (wzrost) + 500 wpłaty
        (date(2026, 1, 1), 1760.0),  # 1600 -> 1760 (+10%)
    ]
    cf = {date(2025, 7, 1): 500.0}
    result = twr(series, cf)
    assert result == pytest.approx(0.1733, abs=1e-3)


def test_twr_detail_cumulative_vs_annualized():
    # +10% w pół roku -> skumulowany 10%, roczny ~21% (annualizacja).
    series = [(date(2025, 1, 1), 1000.0), (date(2025, 7, 2), 1100.0)]
    cum, annual = twr_detail(series, {})
    assert cum == pytest.approx(0.10, abs=1e-6)
    assert annual == pytest.approx((1.10) ** (365 / 182) - 1, abs=1e-6)
    # Krótkie okno: skumulowany jest „uczciwszy" niż roczny (mniejszy).
    assert cum < annual
