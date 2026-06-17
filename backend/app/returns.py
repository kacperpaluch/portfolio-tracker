"""Stopa zwrotu XIRR (wewnętrzna stopa zwrotu uwzględniająca terminy przepływów).

Przepływy w PLN: zakup = wypływ (−), sprzedaż = wpływ (+), bieżąca wartość
portfela = wpływ „dziś". Rozwiązanie metodą Newtona z fallbackiem na bisekcję.
"""
from __future__ import annotations

from datetime import date


def _xnpv(rate: float, cashflows: list[tuple[date, float]]) -> float:
    t0 = cashflows[0][0]
    return sum(cf / (1.0 + rate) ** ((d - t0).days / 365.0) for d, cf in cashflows)


def _xnpv_deriv(rate: float, cashflows: list[tuple[date, float]]) -> float:
    t0 = cashflows[0][0]
    total = 0.0
    for d, cf in cashflows:
        years = (d - t0).days / 365.0
        if years == 0:
            continue
        total += -years * cf / (1.0 + rate) ** (years + 1.0)
    return total


def xirr(cashflows: list[tuple[date, float]], guess: float = 0.1) -> float | None:
    """Zwraca roczną stopę zwrotu (np. 0.12 = 12%) lub None, gdy nieobliczalna.

    Wymaga co najmniej jednego przepływu dodatniego i jednego ujemnego.
    """
    if len(cashflows) < 2:
        return None
    flows = sorted(cashflows, key=lambda x: x[0])
    if not (any(cf > 0 for _, cf in flows) and any(cf < 0 for _, cf in flows)):
        return None

    # Newton.
    rate = guess
    for _ in range(100):
        try:
            value = _xnpv(rate, flows)
            deriv = _xnpv_deriv(rate, flows)
        except (OverflowError, ZeroDivisionError):
            break
        if abs(value) < 1e-7:
            return rate
        if deriv == 0:
            break
        new_rate = rate - value / deriv
        if new_rate <= -0.9999:  # ochrona przed (1+r) <= 0
            new_rate = (rate - 0.9999) / 2
        if abs(new_rate - rate) < 1e-9:
            return new_rate
        rate = new_rate

    # Fallback: bisekcja w bezpiecznym zakresie.
    lo, hi = -0.9999, 10.0
    flo, fhi = _xnpv(lo, flows), _xnpv(hi, flows)
    if flo * fhi > 0:
        return None
    for _ in range(200):
        mid = (lo + hi) / 2
        fmid = _xnpv(mid, flows)
        if abs(fmid) < 1e-7:
            return mid
        if flo * fmid < 0:
            hi, fhi = mid, fmid
        else:
            lo, flo = mid, fmid
    return (lo + hi) / 2
