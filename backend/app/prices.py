"""Pobieranie wycen instrumentów (yfinance dla rynków zagranicznych i GPW przez .WA,
stooq jako alternatywa dla GPW) + cache. Waluta wykrywana automatycznie.

Yahoo dla giełdy londyńskiej zwraca ceny w pensach (GBx) — normalizujemy do GBP
(dzielenie przez 100), żeby przeliczenie kursem NBP było poprawne.
"""
from __future__ import annotations

import io
import sqlite3

import httpx

_TIMEOUT = 20.0
STOOQ_HIST = "https://stooq.com/q/d/l/?s={ticker}&d1={start}&d2={end}&i=d"
STOOQ_LAST = "https://stooq.pl/q/l/?s={ticker}&f=sd2t2ohlc&e=csv"


def _cache_put(conn: sqlite3.Connection, isin: str, day: str, price: float, source: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO prices (isin, date, price, source) VALUES (?, ?, ?, ?)",
        (isin, day, price, source),
    )


def _normalize_ccy(currency: str | None, price: float) -> tuple[str | None, float]:
    """GBx/GBp (pensy) -> GBP (dzielenie przez 100)."""
    if currency in ("GBp", "GBX", "GBx"):
        return "GBP", price / 100.0
    return currency, price


# ---------------------------------------------------------------- yfinance

def _yf_currency(ticker: str) -> str | None:
    try:
        import yfinance as yf

        return yf.Ticker(ticker).fast_info.get("currency")
    except Exception:
        return None


def _yf_last(ticker: str) -> tuple[str, float, str | None] | None:
    try:
        import yfinance as yf

        hist = yf.Ticker(ticker).history(period="5d", auto_adjust=False)
        if hist.empty:
            return None
        day = hist.index[-1].date().isoformat()
        price = float(hist["Close"].iloc[-1])
        ccy, price = _normalize_ccy(_yf_currency(ticker), price)
        return day, price, ccy
    except Exception:
        return None


def _yf_hist(ticker: str, start: str, end: str) -> tuple[list[tuple[str, float]], str | None]:
    try:
        import yfinance as yf

        ccy = _yf_currency(ticker)
        hist = yf.Ticker(ticker).history(start=start, end=end, auto_adjust=False)
        if hist.empty:
            return [], ccy
        factor = 0.01 if ccy in ("GBp", "GBX", "GBx") else 1.0
        ccy = "GBP" if factor == 0.01 else ccy
        series = [(idx.date().isoformat(), float(row["Close"]) * factor) for idx, row in hist.iterrows()]
        return series, ccy
    except Exception:
        return [], None


# ---------------------------------------------------------------- stooq (GPW/PLN)

def _stooq_last(ticker: str) -> tuple[str, float, str] | None:
    try:
        resp = httpx.get(STOOQ_LAST.format(ticker=ticker.lower()), timeout=_TIMEOUT)
        resp.raise_for_status()
        lines = resp.text.strip().splitlines()
        if len(lines) < 2 or "," not in lines[1]:
            return None
        cols = lines[1].split(",")  # symbol,date,time,open,high,low,close
        return cols[1], float(cols[6]), "PLN"
    except Exception:
        return None


def _stooq_hist(ticker: str, start: str, end: str) -> tuple[list[tuple[str, float]], str]:
    url = STOOQ_HIST.format(ticker=ticker.lower(), start=start.replace("-", ""), end=end.replace("-", ""))
    try:
        resp = httpx.get(url, timeout=_TIMEOUT)
        resp.raise_for_status()
        reader = io.StringIO(resp.text)
        header = reader.readline()
        if not header.lower().startswith("date"):
            return [], "PLN"
        out = []
        for line in reader:
            cols = line.strip().split(",")
            if len(cols) >= 5:
                out.append((cols[0], float(cols[4])))
        return out, "PLN"
    except Exception:
        return [], "PLN"


# ---------------------------------------------------------------- API publiczne

def _sync_currency(conn: sqlite3.Connection, isin: str, currency: str | None) -> None:
    """Aktualizuje wykrytą walutę instrumentu (jeśli znana)."""
    if currency:
        conn.execute("UPDATE instruments SET currency = ? WHERE isin = ?", (currency, isin))


def fetch_latest(conn: sqlite3.Connection, instrument: dict) -> tuple[str, float] | None:
    """Pobiera ostatnią cenę (waluta natywna, znormalizowana), cache'uje i synchronizuje walutę."""
    ticker, source = instrument.get("ticker"), instrument.get("source")
    if not ticker or not source:
        return None
    result = _stooq_last(ticker) if source == "stooq" else _yf_last(ticker)
    if result is None:
        return None
    day, price, ccy = result
    _cache_put(conn, instrument["isin"], day, price, source)
    _sync_currency(conn, instrument["isin"], ccy)
    conn.commit()
    return day, price


def fetch_history(conn: sqlite3.Connection, instrument: dict, start: str, end: str) -> int:
    """Backfill dziennych cen w zakresie [start, end]. Zwraca liczbę zapisanych punktów."""
    ticker, source = instrument.get("ticker"), instrument.get("source")
    if not ticker or not source:
        return 0
    if source == "stooq":
        series, ccy = _stooq_hist(ticker, start, end)
    else:
        series, ccy = _yf_hist(ticker, start, end)
    for day, price in series:
        _cache_put(conn, instrument["isin"], day, price, source)
    _sync_currency(conn, instrument["isin"], ccy)
    conn.commit()
    return len(series)


def latest_cached_price(conn: sqlite3.Connection, isin: str) -> tuple[str, float] | None:
    row = conn.execute(
        "SELECT date, price FROM prices WHERE isin = ? ORDER BY date DESC LIMIT 1",
        (isin,),
    ).fetchone()
    return (row[0], row[1]) if row else None


def resolve_currency(ticker: str, source: str) -> str | None:
    """Zwraca wykrytą walutę dla tickera (do auto-uzupełnienia w UI)."""
    if source == "stooq":
        return "PLN"
    return _normalize_ccy(_yf_currency(ticker), 0.0)[0]
