"""Testy zwrotów w okresach (portfolio_returns) — ceny/FX wstrzykiwane ręcznie."""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta

import pytest

from app import fx as fx_mod
from app import prices as prices_mod
from app.db import SCHEMA
from app.history import portfolio_daily_changes, portfolio_returns, refresh_latest


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def _setup(conn):
    # Instrument w PLN (kurs = 1.0, bez FX). Kup 10 szt. @ 100 PLN = 1000 PLN.
    conn.execute(
        "INSERT INTO instruments (isin, name, ticker, currency, source, active, needs_config) "
        "VALUES ('PL01', 'Test ETF', 'X.WA', 'PLN', 'yfinance', 1, 0)"
    )
    conn.execute(
        "INSERT INTO transactions (ts, isin, type, quantity, price_pln, value_pln, commission_pln, import_hash) "
        "VALUES ('2025-01-01T10:00:00', 'PL01', 'BUY', 10, 100, 1000, 0, 'h1')"
    )
    # Cena: 100 -> 120 (od 2025-06-01). Forward-fill utrzyma 120 do dziś.
    conn.execute("INSERT INTO prices (isin, date, price, source) VALUES ('PL01','2025-01-01',100,'yfinance')")
    conn.execute("INSERT INTO prices (isin, date, price, source) VALUES ('PL01','2025-06-01',120,'yfinance')")
    conn.commit()


def test_returns_has_all_periods():
    conn = _db()
    _setup(conn)
    r = portfolio_returns(conn)
    assert set(r.keys()) == {"1m", "3m", "ytd", "1y", "all"}


def test_returns_all_period_cumulative_twr():
    conn = _db()
    _setup(conn)
    r = portfolio_returns(conn)
    # Wartość 1000 -> 1200 (cena 100 -> 120), wkład 1000 na starcie nie zaburza TWR.
    assert r["all"]["twr"] == pytest.approx(0.20, abs=1e-3)
    assert r["all"]["xirr"] is not None and r["all"]["xirr"] > 0


def test_returns_ytd_flat_when_no_move_this_year():
    conn = _db()
    _setup(conn)
    r = portfolio_returns(conn)
    # Cały ruch ceny był w 2025; od 2026-01-01 wartość stała (120) -> YTD ~0%.
    assert r["ytd"]["twr"] == pytest.approx(0.0, abs=1e-6)


def test_returns_empty_without_transactions():
    conn = _db()
    assert portfolio_returns(conn) == {}


def test_daily_changes_market_move():
    conn = _db()
    _setup(conn)
    rows = portfolio_daily_changes(conn)
    by_date = {r["date"]: r for r in rows}
    # Dzień skoku ceny (100 -> 120): +200 zł na 10 szt.
    assert by_date["2025-06-01"]["change_pln"] == pytest.approx(200.0)
    assert by_date["2025-06-01"]["value_pln"] == pytest.approx(1200.0)
    # Dzień bez notowań/zmiany ceny: 0 zł.
    assert by_date["2025-05-31"]["change_pln"] == pytest.approx(0.0)


def test_daily_changes_buy_is_not_a_gain():
    conn = _db()
    _setup(conn)
    # Dokupienie 5 szt. @ 120 (600 zł) 2025-06-02 — to nie zysk, tylko koszt wejścia.
    conn.execute(
        "INSERT INTO transactions (ts, isin, type, quantity, price_pln, value_pln, commission_pln, import_hash) "
        "VALUES ('2025-06-02T10:00:00', 'PL01', 'BUY', 5, 120, 600, 0, 'h2')"
    )
    conn.execute("INSERT INTO prices (isin, date, price, source) VALUES ('PL01','2025-06-02',120,'yfinance')")
    conn.commit()
    by_date = {r["date"]: r for r in portfolio_daily_changes(conn)}
    # Wartość rośnie 1200 -> 1800, ale flow=+600 neutralizuje zakup -> zmiana 0.
    assert by_date["2025-06-02"]["flow_pln"] == pytest.approx(600.0)
    assert by_date["2025-06-02"]["change_pln"] == pytest.approx(0.0)
    assert by_date["2025-06-02"]["value_pln"] == pytest.approx(1800.0)


def test_daily_changes_empty_without_transactions():
    conn = _db()
    assert portfolio_daily_changes(conn) == []


def test_daily_changes_split_pln_is_all_instrument():
    """Instrument w PLN: cały dzienny ruch to instrument, efekt kursu = 0."""
    conn = _db()
    _setup(conn)  # PLN, skok 100 -> 120 dnia 2025-06-01
    by_date = {r["date"]: r for r in portfolio_daily_changes(conn)}
    r = by_date["2025-06-01"]
    assert r["fx_pln"] == pytest.approx(0.0)
    assert r["instrument_pln"] == pytest.approx(200.0)
    assert r["instrument_pln"] + r["fx_pln"] == pytest.approx(r["change_pln"])


def _setup_eur_fx(conn):
    """Instrument w EUR: cena stała 100, kurs 4.0 -> 4.2 (sam efekt waluty)."""
    conn.execute(
        "INSERT INTO instruments (isin, name, ticker, currency, source, active, needs_config) "
        "VALUES ('EU01', 'EUR ETF', 'X.DE', 'EUR', 'yfinance', 1, 0)"
    )
    conn.execute(
        "INSERT INTO transactions (ts, isin, type, quantity, price_pln, value_pln, commission_pln, import_hash) "
        "VALUES ('2025-03-03T10:00:00', 'EU01', 'BUY', 10, 400, 4000, 0, 'e1')"
    )
    conn.execute("INSERT INTO prices (isin,date,price,source) VALUES ('EU01','2025-03-03',100,'yfinance')")
    conn.execute("INSERT INTO prices (isin,date,price,source) VALUES ('EU01','2025-03-04',100,'yfinance')")
    conn.execute("INSERT INTO fx_rates (date,currency,rate_to_pln) VALUES ('2025-03-03','EUR',4.0)")
    conn.execute("INSERT INTO fx_rates (date,currency,rate_to_pln) VALUES ('2025-03-04','EUR',4.2)")
    conn.commit()


def test_daily_changes_split_fx_only():
    """Cena bez zmian, rośnie tylko kurs: cały dzienny ruch to efekt FX."""
    conn = _db()
    _setup_eur_fx(conn)
    by_date = {r["date"]: r for r in portfolio_daily_changes(conn)}
    r = by_date["2025-03-04"]
    # 10 szt × 100 EUR × (4.2 − 4.0) = 200 zł z kursu, 0 z instrumentu.
    assert r["fx_pln"] == pytest.approx(200.0)
    assert r["instrument_pln"] == pytest.approx(0.0)
    assert r["instrument_pln"] + r["fx_pln"] == pytest.approx(r["change_pln"])


def test_daily_changes_split_invariant_holds_every_day():
    """instrument_pln + fx_pln == change_pln dla każdego dnia (niezmiennik addytywny)."""
    conn = _db()
    _setup_eur_fx(conn)
    for r in portfolio_daily_changes(conn):
        assert r["instrument_pln"] + r["fx_pln"] == pytest.approx(r["change_pln"], abs=0.01)


# --- refresh_latest: pobieranie tylko nowych danych + luk (bez sieci) ---------

def _setup_eur(conn):
    """Instrument w EUR (uruchamia ścieżkę FX), pierwsza transakcja 2025-01-01."""
    conn.execute(
        "INSERT INTO instruments (isin, name, ticker, currency, source, active, needs_config) "
        "VALUES ('EU01', 'EUR ETF', 'X.DE', 'EUR', 'yfinance', 1, 0)"
    )
    conn.execute(
        "INSERT INTO transactions (ts, isin, type, quantity, price_pln, value_pln, commission_pln, import_hash) "
        "VALUES ('2025-01-01T10:00:00', 'EU01', 'BUY', 10, 100, 1000, 0, 'h1')"
    )
    conn.commit()


def _capture(monkeypatch):
    """Podmienia pobieranie z sieci na atrapy zapisujące zakres [start, end]."""
    calls = {"price_hist": [], "fx_range": []}
    monkeypatch.setattr(prices_mod, "fetch_history",
                        lambda conn, inst, start, end: calls["price_hist"].append((start, end)) or 0)
    monkeypatch.setattr(prices_mod, "fetch_latest", lambda conn, inst: None)
    monkeypatch.setattr(fx_mod, "backfill_range",
                        lambda conn, cur, start, end: calls["fx_range"].append((start, end)) or 0)
    monkeypatch.setattr(fx_mod, "get_rate", lambda conn, cur, day=None: ("", 4.3))
    return calls


def test_refresh_normal_day_fetches_only_recent_window(monkeypatch):
    """Cache do wczoraj → pobiera tylko [wczoraj, dziś], NIE od pierwszej transakcji."""
    conn = _db()
    _setup_eur(conn)
    today = date.today()
    yesterday = (today - timedelta(days=1)).isoformat()
    conn.execute("INSERT INTO prices (isin, date, price, source) VALUES ('EU01', ?, 100, 'yfinance')", (yesterday,))
    conn.execute("INSERT INTO fx_rates (date, currency, rate_to_pln) VALUES (?, 'EUR', 4.3)", (yesterday,))
    conn.commit()

    calls = _capture(monkeypatch)
    refresh_latest(conn)

    # Okno startuje od wczoraj (ostatni cache), nie od 2025-01-01.
    assert calls["price_hist"] == [(yesterday, today.isoformat())]
    assert calls["fx_range"] == [(yesterday, today.isoformat())]


def test_refresh_fills_only_the_gap_after_outage(monkeypatch):
    """Cache urwany 5 dni temu (awaria) → pobiera tylko 5-dniową lukę, nie wszystko."""
    conn = _db()
    _setup_eur(conn)
    today = date.today()
    gap_start = (today - timedelta(days=5)).isoformat()
    conn.execute("INSERT INTO prices (isin, date, price, source) VALUES ('EU01', ?, 100, 'yfinance')", (gap_start,))
    conn.execute("INSERT INTO fx_rates (date, currency, rate_to_pln) VALUES (?, 'EUR', 4.3)", (gap_start,))
    conn.commit()

    calls = _capture(monkeypatch)
    refresh_latest(conn)

    assert calls["price_hist"] == [(gap_start, today.isoformat())]
    assert calls["fx_range"] == [(gap_start, today.isoformat())]


def test_refresh_new_instrument_backfills_from_first_transaction(monkeypatch):
    """Instrument bez cache → jednorazowo pobiera historię od pierwszej transakcji."""
    conn = _db()
    _setup_eur(conn)  # zero wierszy w prices/fx_rates

    calls = _capture(monkeypatch)
    refresh_latest(conn)

    assert calls["price_hist"] == [("2025-01-01", date.today().isoformat())]
    assert calls["fx_range"] == [("2025-01-01", date.today().isoformat())]


def test_refresh_same_day_does_not_refetch_history(monkeypatch):
    """Drugi refresh tego samego dnia (cache = dziś) → żadnego pobrania historii."""
    conn = _db()
    _setup_eur(conn)
    today = date.today().isoformat()
    conn.execute("INSERT INTO prices (isin, date, price, source) VALUES ('EU01', ?, 100, 'yfinance')", (today,))
    conn.execute("INSERT INTO fx_rates (date, currency, rate_to_pln) VALUES (?, 'EUR', 4.3)", (today,))
    conn.commit()

    calls = _capture(monkeypatch)
    refresh_latest(conn)

    assert calls["price_hist"] == []
    assert calls["fx_range"] == []
