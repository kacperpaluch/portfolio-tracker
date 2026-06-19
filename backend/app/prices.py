"""Pobieranie wycen instrumentów (yfinance — rynki zagraniczne i GPW przez .WA) + cache.
Waluta wykrywana automatycznie.

Yahoo dla giełdy londyńskiej zwraca ceny w pensach (GBx) — normalizujemy do GBP
(dzielenie przez 100), żeby przeliczenie kursem NBP było poprawne.

Gdy Yahoo nie ma poprawnej historii dla danego ISIN, ratunkiem jest import
dziennych cen z CSV (format stooq) — patrz `import_prices`.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime


def _cache_put(conn: sqlite3.Connection, isin: str, day: str, price: float, source: str) -> None:
    """Zapis ceny do cache. Ręczny import z CSV (`source='csv'`) jest „święty":
    automatyczny provider (yfinance) go NIE nadpisuje — inaczej backfill/refresh skasowałby
    dane wgrane dla papierów, których Yahoo nie obsługuje. Re-import CSV nadpisuje wszystko.
    """
    if source == "csv":
        conn.execute(
            "INSERT OR REPLACE INTO prices (isin, date, price, source) VALUES (?, ?, ?, ?)",
            (isin, day, price, source),
        )
    else:
        # UPSERT: wypełnij brakujący dzień / zaktualizuj punkt z yfinance, ale NIE ruszaj
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
    result = _yf_last(ticker)
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

    Ratunek, gdy provider (np. Yahoo) nie oddaje poprawnej historii dla danego ISIN.
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
