"""Kursy walut z NBP (tabela A) + cache w tabeli fx_rates.

NBP nie publikuje kursów w weekendy/święta, więc dla danej daty robimy lookback
do ostatniego dostępnego dnia roboczego.
"""
from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta

import httpx

NBP_BASE = "https://api.nbp.pl/api/exchangerates/rates/A"
_TIMEOUT = 15.0


def _cache_get(conn: sqlite3.Connection, currency: str, day: str) -> float | None:
    row = conn.execute(
        "SELECT rate_to_pln FROM fx_rates WHERE date = ? AND currency = ?",
        (day, currency),
    ).fetchone()
    return row[0] if row else None


def _cache_put(conn: sqlite3.Connection, currency: str, day: str, rate: float) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO fx_rates (date, currency, rate_to_pln) VALUES (?, ?, ?)",
        (day, currency, rate),
    )


def get_rate(conn: sqlite3.Connection, currency: str, day: str | None = None) -> tuple[str, float]:
    """Zwraca (data_kursu, kurs_do_PLN) dla waluty na zadany dzień (domyślnie dziś).

    PLN -> 1.0. Dla EUR/USD itp. pobiera z NBP z lookbackiem i cache'uje pod
    *faktyczną* datą kursu NBP oraz pod datą zapytania (żeby kolejne trafienia były szybkie).
    """
    currency = currency.upper()
    if currency == "PLN":
        return (day or date.today().isoformat()), 1.0

    target = date.fromisoformat(day) if day else date.today()
    target_str = target.isoformat()

    cached = _cache_get(conn, currency, target_str)
    if cached is not None:
        return target_str, cached

    # Pobierz zakres [target-10 dni, target] i weź ostatni dostępny kurs <= target.
    start = (target - timedelta(days=10)).isoformat()
    url = f"{NBP_BASE}/{currency}/{start}/{target_str}/?format=json"
    try:
        resp = httpx.get(url, timeout=_TIMEOUT)
        resp.raise_for_status()
        rates = resp.json().get("rates", [])
    except Exception:
        rates = []

    if not rates:
        raise LookupError(f"Brak kursu NBP dla {currency} na {target_str}")

    last = rates[-1]
    eff_date = last["effectiveDate"]
    rate = float(last["mid"])
    # Zapis pod datą efektywną i pod datą zapytania (alias), by domknąć weekendy.
    _cache_put(conn, currency, eff_date, rate)
    _cache_put(conn, currency, target_str, rate)
    conn.commit()
    return target_str, rate


def backfill_range(conn: sqlite3.Connection, currency: str, start: str, end: str) -> int:
    """Pobiera kursy NBP dla zakresu dat i cache'uje. Zwraca liczbę zapisanych dni."""
    currency = currency.upper()
    if currency == "PLN":
        return 0
    url = f"{NBP_BASE}/{currency}/{start}/{end}/?format=json"
    try:
        resp = httpx.get(url, timeout=_TIMEOUT)
        resp.raise_for_status()
        rates = resp.json().get("rates", [])
    except Exception:
        return 0
    for r in rates:
        _cache_put(conn, currency, r["effectiveDate"], float(r["mid"]))
    conn.commit()
    return len(rates)
