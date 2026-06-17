"""Testy klienta NBP — w szczególności dzielenie backfillu na okna ≤367 dni."""
from __future__ import annotations

import sqlite3
from datetime import date

from app import fx as fx_mod
from app.db import SCHEMA


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


class _FakeResp:
    def raise_for_status(self):  # noqa: D401
        pass

    def json(self):
        return {"rates": []}


def test_backfill_splits_into_windows_under_367_days(monkeypatch):
    calls = []

    def fake_get(url, timeout=None):
        # URL: .../A/EUR/<start>/<end>/?format=json
        parts = url.split("/A/EUR/")[1].split("/?")[0].split("/")
        calls.append((date.fromisoformat(parts[0]), date.fromisoformat(parts[1])))
        return _FakeResp()

    monkeypatch.setattr(fx_mod.httpx, "get", fake_get)
    conn = _db()
    # Zakres ~800 dni — bez podziału NBP zwróciłby 400.
    fx_mod.backfill_range(conn, "EUR", "2024-01-01", "2026-03-11")

    assert len(calls) >= 3  # podzielone na kilka okien
    for s, e in calls:
        assert (e - s).days <= 367  # każde okno w limicie NBP
    # Okna są ciągłe i pokrywają cały zakres.
    assert calls[0][0] == date(2024, 1, 1)
    assert calls[-1][1] == date(2026, 3, 11)
    for prev, nxt in zip(calls, calls[1:]):
        assert (nxt[0] - prev[1]).days == 1  # bez luk i nakładek


def test_backfill_pln_is_noop():
    conn = _db()
    assert fx_mod.backfill_range(conn, "PLN", "2024-01-01", "2026-03-11") == 0
