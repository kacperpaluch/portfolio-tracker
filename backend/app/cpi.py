"""Wskaźnik inflacji HICP (Eurostat) + cache w tabeli cpi_index.

Eurostat publikuje MIESIĘCZNY indeks cen HICP dla Polski (baza 2015=100) —
skumulowany poziom cen, idealny do benchmarku „inflacja + X%": mnożnik inflacji
między dwiema datami = indeks(do) / indeks(od).

Dlaczego HICP, a nie CPI GUS: GUS BDL API udostępnia krajowy CPI tylko rocznie
(temat P2955) i kwartalnie (P2496) — MIESIĘCZNEGO indeksu CPI nie ma tam wcale
(dane.gov.pl/strony GUS publikują go tylko jako HTML). Eurostat HICP to jedyne
czyste API z rozdzielczością miesięczną. Metodologicznie minimalnie inny niż CPI
GUS (różnice rzędu ~0,2 pp/rok — w skali benchmarku nieistotne).
"""
from __future__ import annotations

import sqlite3
from bisect import bisect_right
from datetime import date

import httpx

# prc_hicp_midx = miesięczny indeks HICP; unit I15 = baza 2015=100; CP00 = ogółem; geo PL.
EUROSTAT_URL = (
    "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
    "prc_hicp_midx?format=JSON&geo=PL&coicop=CP00&unit=I15&lang=EN"
)
_TIMEOUT = 30.0


def refresh_cpi(conn: sqlite3.Connection) -> int:
    """Pobiera pełną serię miesięcznego indeksu HICP (PL) z Eurostatu i cache'uje.

    Zwraca liczbę zapisanych punktów. Sieć/parsing padł → 0 (cache zostaje nietknięty,
    benchmark inflacyjny po prostu się nie pokaże, reszta działa).
    """
    try:
        resp = httpx.get(EUROSTAT_URL, timeout=_TIMEOUT)
        resp.raise_for_status()
        payload = resp.json()
    except Exception:
        return 0

    time_idx = payload.get("dimension", {}).get("time", {}).get("category", {}).get("index", {})
    values = payload.get("value", {})
    if not time_idx or not values:
        return 0

    inv = {pos: month for month, pos in time_idx.items()}  # pozycja -> 'YYYY-MM'
    n = 0
    for pos, val in values.items():
        month = inv.get(int(pos))
        if not month or val is None:
            continue
        conn.execute(
            "INSERT OR REPLACE INTO cpi_index (month, idx) VALUES (?, ?)",
            (f"{month}-01", float(val)),
        )
        n += 1
    conn.commit()
    return n


def load_points(conn: sqlite3.Connection) -> list[tuple[date, float]]:
    """Posortowana lista (pierwszy_dzień_miesiąca, indeks) z cache. Pusta gdy brak danych."""
    rows = conn.execute("SELECT month, idx FROM cpi_index ORDER BY month ASC").fetchall()
    return [(date.fromisoformat(r["month"]), r["idx"]) for r in rows]


def index_at(points: list[tuple[date, float]], d: date) -> float | None:
    """Indeks HICP na dany dzień z interpolacją liniową między punktami miesięcznymi.

    Przed pierwszym punktem / po ostatnim — wartość skrajna (forward-fill końca,
    bo Eurostat publikuje z ~miesięcznym opóźnieniem). Zwraca None tylko gdy brak danych.
    """
    if not points:
        return None
    if d <= points[0][0]:
        return points[0][1]
    if d >= points[-1][0]:
        return points[-1][1]
    dates = [p[0] for p in points]
    i = bisect_right(dates, d)  # points[i-1] <= d < points[i]
    d0, v0 = points[i - 1]
    d1, v1 = points[i]
    span = (d1 - d0).days
    if span <= 0:
        return v0
    return v0 + (v1 - v0) * ((d - d0).days / span)
