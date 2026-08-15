"""Pobieranie wycen instrumentów (Yahoo, EODHD, Alpha Vantage) + cache.

Provider jest wybierany per instrument przez `instruments.source`, a `ticker` zawiera
symbol w konwencji wybranego źródła (np. WEBN.DE / WEBN.XETRA / WEBN.DEX).
Klucze API są czytane wyłącznie z EODHD_API_KEY i ALPHA_VANTAGE_API_KEY.

Yahoo dla giełdy londyńskiej zwraca ceny w pensach (GBx) — normalizujemy do GBP
(dzielenie przez 100), żeby przeliczenie kursem NBP było poprawne.

Gdy automatyczny provider nie ma poprawnej historii dla danego ISIN, ratunkiem jest import
dziennych cen z CSV (format stooq) — patrz `import_prices`.
"""
from __future__ import annotations

import math
import os
import sqlite3
import threading
import time
from datetime import datetime, timezone
from typing import Callable
from urllib.parse import quote

import httpx

SUPPORTED_SOURCES = {"yfinance", "eodhd", "alphavantage", "csv"}
PROVIDER_KEY_ENV = {
    "eodhd": "EODHD_API_KEY",
    "alphavantage": "ALPHA_VANTAGE_API_KEY",
}

# Limity działają per proces aplikacji. Wartości domyślne są zachowawcze dla
# darmowych planów; można je dostroić zmiennymi środowiskowymi bez zmiany kodu.
_DEFAULT_INTERVALS = {"eodhd": 1.0, "alphavantage": 12.0}
_RATE_LOCKS = {provider: threading.Lock() for provider in _DEFAULT_INTERVALS}
_LAST_REQUEST = {provider: 0.0 for provider in _DEFAULT_INTERVALS}


def _provider_interval(provider: str) -> float:
    env_name = f"{provider.upper()}_MIN_INTERVAL_SECONDS"
    try:
        return max(0.0, float(os.environ.get(env_name, _DEFAULT_INTERVALS[provider])))
    except (TypeError, ValueError):
        return _DEFAULT_INTERVALS[provider]


def _wait_for_provider(provider: str) -> None:
    """Serializuje zapytania i zachowuje minimalny odstęp per provider/proces."""
    with _RATE_LOCKS[provider]:
        delay = _provider_interval(provider) - (time.monotonic() - _LAST_REQUEST[provider])
        if delay > 0:
            time.sleep(delay)
        _LAST_REQUEST[provider] = time.monotonic()


def _retry_delay(response, attempt: int) -> float:
    retry_after = getattr(response, "headers", {}).get("Retry-After") if response is not None else None
    try:
        return max(0.0, float(retry_after))
    except (TypeError, ValueError):
        return float(2 ** attempt)


def _get_json(
    provider: str,
    url: str,
    params: dict,
    payload_retryable: Callable[[object], bool] | None = None,
):
    """GET z limitem, maks. 3 próbami i backoffem dla 429/5xx/błędów sieci."""
    for attempt in range(3):
        response = None
        try:
            _wait_for_provider(provider)
            response = httpx.get(url, params=params, timeout=20.0)
            status = getattr(response, "status_code", 200)
            if status == 429 or status >= 500:
                if attempt < 2:
                    time.sleep(_retry_delay(response, attempt))
                    continue
                return None
            response.raise_for_status()
            data = response.json()
            if payload_retryable and payload_retryable(data):
                if attempt < 2:
                    time.sleep(_retry_delay(response, attempt))
                    continue
                return None
            return data
        except (httpx.TimeoutException, httpx.TransportError, ValueError):
            if attempt < 2:
                time.sleep(_retry_delay(response, attempt))
                continue
            return None
        except httpx.HTTPError:
            return None
    return None


def provider_configured(source: str | None) -> bool:
    """Czy provider może działać w bieżącym środowisku."""
    source = (source or "").strip().lower()
    env_name = PROVIDER_KEY_ENV.get(source)
    return bool(os.environ.get(env_name, "").strip()) if env_name else source in {"yfinance", "csv"}


def _cache_put(conn: sqlite3.Connection, isin: str, day: str, price: float, source: str) -> None:
    """Zapis ceny do cache. Ręczny import z CSV (`source='csv'`) jest „święty":
    automatyczny provider go NIE nadpisuje — inaczej backfill/refresh skasowałby
    dane wgrane dla papierów bez poprawnych danych providera. Re-import CSV nadpisuje wszystko.

    NaN/inf są pomijane: sqlite3 binduje NaN jako NULL, co wywala NOT NULL na prices.price
    (yfinance zwraca świeży dzień z Close=NaN, zanim giełda poda kurs).
    """
    if price is None or not math.isfinite(price):
        return
    if source == "csv":
        conn.execute(
            "INSERT OR REPLACE INTO prices (isin, date, price, source) VALUES (?, ?, ?, ?)",
            (isin, day, price, source),
        )
    else:
        # UPSERT: wypełnij brakujący dzień / zaktualizuj punkt providera, ale NIE ruszaj
        # istniejącego wiersza pochodzącego z importu CSV.
        conn.execute(
            "INSERT INTO prices (isin, date, price, source) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(isin, date) DO UPDATE SET price = excluded.price, source = excluded.source "
            "WHERE prices.source IS NOT 'csv'",
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

        hist = yf.Ticker(ticker).history(period="5d", auto_adjust=False).dropna(subset=["Close"])
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


# ---------------------------------------------------------------- EODHD

def _eodhd_get(path: str, params: dict | None = None):
    api_key = os.environ.get("EODHD_API_KEY", "").strip()
    if not api_key:
        return None
    data = _get_json(
        "eodhd",
        f"https://eodhd.com/api/{path.lstrip('/')}",
        {**(params or {}), "api_token": api_key, "fmt": "json"},
    )
    if isinstance(data, dict) and (data.get("errors") or data.get("message")):
        return None
    return data


def _eodhd_last(ticker: str) -> tuple[str, float, str | None] | None:
    data = _eodhd_get(f"real-time/{ticker}")
    if not isinstance(data, dict) or data.get("close") is None:
        return None
    timestamp = data.get("timestamp")
    day = (
        datetime.fromtimestamp(timestamp, timezone.utc).date().isoformat()
        if isinstance(timestamp, (int, float))
        else datetime.now(timezone.utc).date().isoformat()
    )
    return day, float(data["close"]), None


def _eodhd_hist(ticker: str, start: str, end: str) -> tuple[list[tuple[str, float]], str | None]:
    data = _eodhd_get(f"eod/{ticker}", {"from": start, "to": end, "order": "a"})
    if not isinstance(data, list):
        return [], None
    series = [
        (str(row["date"]), float(row["close"]))
        for row in data
        if row.get("date") and row.get("close") is not None
    ]
    return series, None


# ---------------------------------------------------------------- Alpha Vantage

def _alpha_get(params: dict):
    api_key = os.environ.get("ALPHA_VANTAGE_API_KEY", "").strip()
    if not api_key:
        return None
    def throttled(payload: object) -> bool:
        return isinstance(payload, dict) and any(key in payload for key in ("Information", "Note"))

    data = _get_json(
        "alphavantage",
        "https://www.alphavantage.co/query",
        {**params, "apikey": api_key},
        payload_retryable=throttled,
    )
    if not isinstance(data, dict) or "Error Message" in data:
        return None
    return data


def _alpha_last(ticker: str) -> tuple[str, float, str | None] | None:
    data = _alpha_get({"function": "GLOBAL_QUOTE", "symbol": ticker})
    quote = data.get("Global Quote", {}) if data else {}
    day, price = quote.get("07. latest trading day"), quote.get("05. price")
    if not day or price is None:
        return None
    return str(day), float(price), None


def _alpha_hist(ticker: str, start: str, end: str) -> tuple[list[tuple[str, float]], str | None]:
    data = _alpha_get({
        "function": "TIME_SERIES_DAILY",
        "symbol": ticker,
        "outputsize": "compact",
    })
    raw = data.get("Time Series (Daily)", {}) if data else {}
    series = sorted(
        (day, float(values["4. close"]))
        for day, values in raw.items()
        if start <= day <= end and values.get("4. close") is not None
    )
    return series, None


def search_symbols(source: str, query: str) -> list[dict]:
    """Wyszukuje symbole providera i zwraca wspólny, bezpieczny format dla UI."""
    source = source.strip().lower()
    query = query.strip()
    if not query:
        return []
    if source == "eodhd":
        data = _eodhd_get(f"search/{quote(query, safe='')}")
        if not isinstance(data, list):
            return []
        return [
            {
                "symbol": ".".join(filter(None, (row.get("Code"), row.get("Exchange")))),
                "name": row.get("Name") or row.get("Code") or "",
                "exchange": row.get("Exchange") or "",
                "region": row.get("Country") or "",
                "currency": row.get("Currency") or "",
                "isin": row.get("ISIN") or "",
                "type": row.get("Type") or "",
            }
            for row in data[:20]
            if row.get("Code")
        ]
    if source == "alphavantage":
        data = _alpha_get({"function": "SYMBOL_SEARCH", "keywords": query})
        matches = data.get("bestMatches", []) if isinstance(data, dict) else []
        return [
            {
                "symbol": row.get("1. symbol") or "",
                "name": row.get("2. name") or row.get("1. symbol") or "",
                "exchange": "",
                "region": row.get("4. region") or "",
                "currency": row.get("8. currency") or "",
                "isin": "",
                "type": row.get("3. type") or "",
            }
            for row in matches[:20]
            if row.get("1. symbol")
        ]
    raise ValueError("Wyszukiwanie symboli obsługuje EODHD i Alpha Vantage")


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
    if source == "yfinance":
        result = _yf_last(ticker)
    elif source == "eodhd":
        result = _eodhd_last(ticker)
    elif source == "alphavantage":
        result = _alpha_last(ticker)
    else:
        return None
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
    if source == "yfinance":
        series, ccy = _yf_hist(ticker, start, end)
    elif source == "eodhd":
        series, ccy = _eodhd_hist(ticker, start, end)
    elif source == "alphavantage":
        series, ccy = _alpha_hist(ticker, start, end)
    else:
        return 0
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


# ---------------------------------------------------------------- import cen z CSV

_DATE_HEADERS = {"data", "date"}
_CLOSE_HEADERS = {"zamkniecie", "zamknięcie", "close", "kurs"}


def _parse_price_number(raw: str) -> float | None:
    raw = raw.strip().replace("\xa0", "").replace(" ", "")
    if not raw:
        return None
    # Część eksportów używa przecinka dziesiętnego (stooq.pl zwykle kropki).
    if "," in raw and "." not in raw:
        raw = raw.replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def _parse_price_date(raw: str) -> str | None:
    raw = raw.strip()
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def parse_price_csv(content: bytes) -> list[tuple[str, float]]:
    """Parsuje CSV stooq/„OHLC" (Data,…,Zamkniecie,…) do listy (date_iso, close).

    Funkcja czysta (bez DB). Rozpoznaje kolumny po nagłówku (PL/EN), wykrywa separator
    (',' / ';' / tab) i akceptuje datę ISO, YYYYMMDD lub DD.MM.YYYY oraz przecinek
    dziesiętny. Wiersze bez poprawnej daty/ceny są pomijane. Rzuca ValueError, gdy
    nagłówek nie zawiera kolumn daty i zamknięcia.
    """
    text = content.decode("utf-8-sig", errors="replace")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return []
    delim = max((",", ";", "\t"), key=lambda d: lines[0].count(d))
    header = [h.strip().lower() for h in lines[0].split(delim)]
    di = next((i for i, h in enumerate(header) if h in _DATE_HEADERS), None)
    ci = next((i for i, h in enumerate(header) if h in _CLOSE_HEADERS), None)
    if di is None or ci is None:
        raise ValueError(
            "Nie rozpoznano kolumn — wymagane nagłówki 'Data' i 'Zamkniecie' (lub Date/Close)."
        )
    out: list[tuple[str, float]] = []
    for line in lines[1:]:
        cols = line.split(delim)
        if len(cols) <= max(di, ci):
            continue
        day = _parse_price_date(cols[di])
        price = _parse_price_number(cols[ci])
        if day is None or price is None:
            continue
        out.append((day, price))
    return out


def import_prices(
    conn: sqlite3.Connection,
    isin: str,
    content: bytes,
    source: str = "csv",
    currency: str | None = None,
) -> dict:
    """Wgrywa dzienne ceny (w walucie natywnej instrumentu) z CSV do cache `prices`.

    Ratunek, gdy automatyczny provider nie oddaje poprawnej historii dla danego ISIN.
    Nadpisuje pokrywające się punkty (INSERT OR REPLACE); cena trafia wprost do kolumny
    `price` (przeliczenie kursem NBP dzieje się dalej w wycenie, dla PLN kurs = 1.0).

    Waluta jest WYMAGANA do wyceny (bez niej kurs FX → wartość 0), a CSV jej nie niesie.
    Dlatego: jeśli podasz `currency` — ustawiamy ją na instrumencie; w przeciwnym razie
    używamy waluty już zapisanej na instrumencie. Gdy obu brak — NIE zgadujemy (stooq
    notuje też w USD/EUR/GBP, więc domyślne PLN bywałoby błędem) i podnosimy ValueError.
    """
    rows = parse_price_csv(content)

    currency = (currency or "").strip().upper() or None
    row = conn.execute("SELECT currency FROM instruments WHERE isin = ?", (isin,)).fetchone()
    existing = row[0] if row else None
    effective = currency or existing
    if effective is None:
        raise ValueError(
            "Instrument nie ma ustawionej waluty — podaj walutę przy imporcie "
            "(np. PLN, USD, EUR, GBP). Nie zgadujemy jej, bo stooq notuje też w obcych walutach."
        )

    for day, price in rows:
        _cache_put(conn, isin, day, price, source)
    if currency and currency != existing:
        conn.execute("UPDATE instruments SET currency = ? WHERE isin = ?", (currency, isin))

    conn.commit()
    dates = [d for d, _ in rows]
    return {
        "imported": len(rows),
        "isin": isin,
        "first_date": min(dates) if dates else None,
        "last_date": max(dates) if dates else None,
        "currency": effective,
    }
