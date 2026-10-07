"""Detaliczne obligacje skarbowe: wycena z tabel odsetkowych MF (obligacjeskarbowe.pl).

Obligacje oszczędnościowe nie mają notowań. MF publikuje za to dla każdej serii i każdego
okresu odsetkowego tabelę PDF z narosłymi odsetkami (zł na 1 sztukę) na każdy dzień —
wartość obligacji = 100 zł + odsetki z tabeli. Tabele trzymamy lokalnie w `bond_interest`;
sieć jest potrzebna tylko wtedy, gdy lokalne dane serii się kończą (raz na okres odsetkowy).

Tabela zakłada zakup w pierwszym dniu sprzedaży serii; przy zakupie później wartości
przesuwają się o liczbę dni od początku sprzedaży (przypis MF w każdej tabeli). Dzień zakupu
siedzi w identyfikatorze instrumentu: `EDO0334-20240315` (seria + data), ticker = seria.
"""
from __future__ import annotations

import io
import re
import sqlite3
from datetime import date, datetime, timedelta

import httpx

SOURCE = "obligacje"
NOMINAL = 100.0
BASE_URL = "https://www.obligacjeskarbowe.pl"
TABLES_URL = f"{BASE_URL}/tabela-odsetkowa/"
# ponytail: tylko typy kapitalizujące odsetki (tabela skumulowana od zakupu). COI/ROR/DOR
# wypłacają odsetki co okres — wymagają przepływu gotówki `interest`, dodać razem z nim.
SUPPORTED_TYPES = ("EDO", "TOS", "ROS", "ROD")
# MF publikuje tabelę kolejnego okresu ~2 tygodnie przed jego początkiem.
SYNC_AHEAD_DAYS = 14
_SERIES_RE = re.compile(r"[A-Z]{3}\d{4}")
_TIMEOUT = 30.0


def normalize_series(series: str) -> str:
    series = (series or "").strip().upper()
    if not _SERIES_RE.fullmatch(series):
        raise ValueError("Kod serii musi mieć postać np. EDO0334")
    if series[:3] not in SUPPORTED_TYPES:
        raise ValueError(
            f"Obsługiwane są obligacje kapitalizujące odsetki: {', '.join(SUPPORTED_TYPES)}"
        )
    return series


def purchase_date(isin: str) -> date:
    """Dzień zakupu zakodowany w identyfikatorze instrumentu (`SERIA-YYYYMMDD`)."""
    return datetime.strptime(isin.rsplit("-", 1)[-1], "%Y%m%d").date()


def _pdf_text_tables(content: bytes) -> tuple[str, list]:
    import pdfplumber

    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
            return text, [t for page in pdf.pages for t in page.extract_tables()]
    except Exception as exc:
        raise ValueError("Nie udało się odczytać pliku PDF") from exc


def parse_table_pdf(content: bytes, period_start: str | None = None) -> dict:
    """Parsuje tabelę odsetkową MF: {series, sale_start, points[(data, odsetki)]}.

    Wiersz = dzień miesiąca, kolumna = miesiąc `YYYY-MM`. Tabele sprzed 2023 r. mają
    nagłówki miesięcy obróconym tekstem (nieczytelne po ekstrakcji) i nie podają początku
    sprzedaży — wtedy kolumny to kolejne miesiące od `period_start` (znany z listy okresów MF).
    Rzuca ValueError, gdy układu nie da się rozpoznać.
    """
    text, tables = _pdf_text_tables(content)
    series = _SERIES_RE.search(text)
    sale_start = re.search(r"OD (\d{4}-\d{2}-\d{2})", text)
    points: list[tuple[str, float]] = []
    for table in tables:
        months = [(m or "").strip() for m in table[0][1:]] if table else []
        if not months:
            continue
        if not all(re.fullmatch(r"\d{4}-\d{2}", m) for m in months):
            if not period_start:
                continue
            first = int(period_start[:4]) * 12 + int(period_start[5:7]) - 1
            months = [f"{(first + n) // 12}-{(first + n) % 12 + 1:02d}" for n in range(len(months))]
        for row in table[1:]:
            for month, cell in zip(months, row[1:]):
                if not (cell or "").strip():
                    continue
                try:
                    day = date(int(month[:4]), int(month[5:]), int(row[0]))
                    points.append((day.isoformat(), float(cell.replace(" ", "").replace(",", "."))))
                except (TypeError, ValueError):
                    continue
    if not series or not points:
        raise ValueError("Nie rozpoznano tabeli odsetkowej MF (seria, wartości dzienne)")
    return {
        "series": series.group(0),
        "sale_start": sale_start.group(1) if sale_start else None,
        "points": sorted(points),
    }


def store_table(conn: sqlite3.Connection, parsed: dict) -> int:
    """Zapisuje sparsowaną tabelę. Punkt (początek sprzedaży, 0 zł) kotwiczy przesunięcie."""
    series = parsed["series"]
    if parsed["sale_start"]:
        conn.execute(
            "INSERT OR IGNORE INTO bond_interest (series, date, interest) VALUES (?, ?, 0)",
            (series, parsed["sale_start"]),
        )
    conn.executemany(
        "INSERT OR REPLACE INTO bond_interest (series, date, interest) VALUES (?, ?, ?)",
        [(series, day, interest) for day, interest in parsed["points"]],
    )
    conn.commit()
    return len(parsed["points"])


def sale_start(conn: sqlite3.Connection, series: str) -> str | None:
    return conn.execute(
        "SELECT MIN(date) FROM bond_interest WHERE series = ?", (series,)
    ).fetchone()[0]


def _series_periods(html: str, series: str) -> list[tuple[str, str, str]]:
    """Z listy rozwijanej strony MF: [(table_id, początek_okresu, koniec_okresu)] dla serii."""
    emission = re.search(r'value="(\d+),[a-z]+"\s+data-id="[a-z]+">\s*' + series + r"\s*<", html)
    if not emission:
        raise ValueError(f"Nie znaleziono serii {series} na obligacjeskarbowe.pl")
    return re.findall(
        r'value="(\d+),' + emission.group(1)
        + r'"\s+data-id="\d+">\s*(\d{4}-\d{2}-\d{2}) -&gt; (\d{4}-\d{2}-\d{2})',
        html,
    )


def sync_series(conn: sqlite3.Connection, series: str, today: date | None = None) -> int:
    """Dociąga brakujące tabele serii. Bez sieci, gdy lokalne dane sięgają dalej niż
    SYNC_AHEAD_DAYS w przód. Zwraca liczbę pobranych tabel; rzuca httpx.HTTPError/ValueError."""
    today = today or date.today()
    have = conn.execute(
        "SELECT MAX(date) FROM bond_interest WHERE series = ?", (series,)
    ).fetchone()[0]
    if have and have >= (today + timedelta(days=SYNC_AHEAD_DAYS)).isoformat():
        return 0

    fetched = 0
    with httpx.Client(timeout=_TIMEOUT, follow_redirects=True,
                      headers={"User-Agent": "Mozilla/5.0 portfolio-tracker"}) as client:
        index = client.get(TABLES_URL)
        index.raise_for_status()
        for table_id, period_start, period_end in _series_periods(index.text, series):
            if have and period_end <= have:
                continue
            page = client.get(TABLES_URL, params={"table_id": table_id})
            page.raise_for_status()
            link = re.search(r'class="files__item"\s+href="(/media_files/[^"]+\.pdf)"', page.text)
            if not link:
                continue
            pdf = client.get(BASE_URL + link.group(1))
            pdf.raise_for_status()
            try:
                parsed = parse_table_pdf(pdf.content, period_start)
            except ValueError:
                continue  # nierozpoznany układ PDF — pomijamy okres, pozostałe nadal wyceniają
            if parsed["series"] == series:
                store_table(conn, parsed)
                fetched += 1
    return fetched


def try_sync(conn: sqlite3.Connection, series: str) -> str | None:
    """sync_series bez wyjątków: zwraca komunikat błędu albo None. Awaria strony MF nie może
    wywalić odświeżania — wycena stoi wtedy na lokalnych danych (data_quality: stale_price)."""
    try:
        sync_series(conn, series)
        return None
    except httpx.HTTPError:
        return "Nie udało się pobrać tabel odsetkowych z obligacjeskarbowe.pl"
    except ValueError as exc:
        return str(exc)


def price_points(conn: sqlite3.Connection, instrument: dict, start: str, end: str) -> list[tuple[str, float]]:
    """Dzienna wartość 1 sztuki w [start, end], nie wcześniej niż zakup i nie później niż dziś
    (tabela zna odsetki na rok naprzód, a przyszła data w `prices` zawyżyłaby bieżącą wycenę)."""
    series = instrument["ticker"]
    first = sale_start(conn, series)
    if not first:
        return []
    bought = purchase_date(instrument["isin"])
    offset = timedelta(days=(bought - date.fromisoformat(first)).days)
    lo = max(date.fromisoformat(start[:10]) if start else bought, bought)
    hi = min(date.fromisoformat(end[:10]), date.today())
    rows = conn.execute(
        "SELECT date, interest FROM bond_interest WHERE series = ? AND date BETWEEN ? AND ? ORDER BY date",
        (series, (lo - offset).isoformat(), (hi - offset).isoformat()),
    ).fetchall()
    return [
        ((date.fromisoformat(day) + offset).isoformat(), round(NOMINAL + interest, 2))
        for day, interest in rows
    ]
