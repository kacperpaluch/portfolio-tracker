"""Testy XIRR."""
from __future__ import annotations

from datetime import date

import pytest

from app.returns import xirr


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
