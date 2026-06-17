"""Historia wartości portfela w czasie + backfill cen/kursów i przepływy do XIRR."""
from __future__ import annotations

import bisect
import sqlite3
from datetime import date, timedelta

from . import fx, prices
from .returns import xirr


def backfill_all(conn: sqlite3.Connection) -> dict:
    """Pobiera historyczne ceny i kursy NBP od daty pierwszej transakcji do dziś."""
    row = conn.execute("SELECT MIN(ts) AS first_ts FROM transactions").fetchone()
    if not row or not row["first_ts"]:
        return {"prices": 0, "fx": 0}
    start = row["first_ts"][:10]
    end = date.today().isoformat()

    instruments = [
        dict(r) for r in conn.execute(
            "SELECT * FROM instruments WHERE active = 1 AND needs_config = 0"
        )
    ]
    price_points = 0
    for inst in instruments:
        price_points += prices.fetch_history(conn, inst, start, end)

    currencies = {i["currency"] for i in instruments if i["currency"] and i["currency"] != "PLN"}
    fx_points = 0
    for cur in currencies:
        fx_points += fx.backfill_range(conn, cur, start, end)

    return {"prices": price_points, "fx": fx_points, "start": start, "end": end}


def _series_map(rows) -> dict[str, list]:
    """Buduje mapę klucz -> (lista_dat, lista_wartości) posortowaną rosnąco po dacie."""
    tmp: dict[str, list] = {}
    for key, day, val in rows:
        tmp.setdefault(key, []).append((day, val))
    out = {}
    for key, pairs in tmp.items():
        pairs.sort()
        out[key] = ([p[0] for p in pairs], [p[1] for p in pairs])
    return out


def _forward_fill(series: tuple[list, list] | None, day: str) -> float | None:
    """Ostatnia wartość z datą <= day (forward-fill)."""
    if not series:
        return None
    dates, values = series
    idx = bisect.bisect_right(dates, day) - 1
    return values[idx] if idx >= 0 else None


def _cash_timeline(conn: sqlite3.Connection):
    """Zwraca (lista_dat, skumulowane_saldo) gotówki oraz czy są wpłaty zewnętrzne."""
    flows = conn.execute("SELECT ts, kind, amount_pln FROM cash_flows ORDER BY ts ASC").fetchall()
    has_external = any(f["kind"] in ("deposit", "withdrawal") for f in flows)
    # Agregacja po dniu.
    by_day: dict[str, float] = {}
    for f in flows:
        day = f["ts"][:10]
        by_day[day] = by_day.get(day, 0.0) + f["amount_pln"]
    days = sorted(by_day)
    cum, running = [], 0.0
    for d in days:
        running += by_day[d]
        cum.append((d, running))
    return cum, has_external


def _contributions(conn: sqlite3.Connection, has_external: bool) -> list[tuple[date, float]]:
    """Wkłady kapitału do benchmarku: wpłaty (+)/wypłaty (−), a bez nich — kupna (+)/sprzedaże (−)."""
    if has_external:
        rows = conn.execute(
            "SELECT ts, amount_pln FROM cash_flows WHERE kind IN ('deposit', 'withdrawal')"
        ).fetchall()
        return [(date.fromisoformat(r["ts"][:10]), r["amount_pln"]) for r in rows]
    rows = conn.execute("SELECT ts, type, value_pln FROM transactions").fetchall()
    return [
        (date.fromisoformat(r["ts"][:10]), r["value_pln"] if r["type"] == "BUY" else -r["value_pln"])
        for r in rows
    ]


def portfolio_history(conn: sqlite3.Connection, benchmark_rate: float = 0.05) -> list[dict]:
    """Dzienna seria wartości portfela w PLN od pierwszej transakcji do dziś.

    Gdy istnieją wpłaty/wypłaty, do wyceny ETF doliczane jest saldo gotówki
    (pełna wartość konta). Bez wpłat seria pokazuje samą wycenę instrumentów.

    Dla każdego dnia liczony jest też `benchmark_pln`: te same wkłady kapitału
    oprocentowane stałą stopą `benchmark_rate` rocznie od daty wpłaty.
    """
    txs = conn.execute(
        "SELECT ts, isin, type, quantity FROM transactions ORDER BY ts ASC"
    ).fetchall()
    if not txs:
        return []

    cash_cum, has_external = _cash_timeline(conn)
    cash_dates = [c[0] for c in cash_cum]
    cash_vals = [c[1] for c in cash_cum]
    contributions = _contributions(conn, has_external)

    instr_ccy = {r["isin"]: r["currency"] for r in conn.execute("SELECT isin, currency FROM instruments")}
    price_map = _series_map([(r["isin"], r["date"], r["price"]) for r in conn.execute("SELECT isin, date, price FROM prices")])
    fx_map = _series_map([(r["currency"], r["date"], r["rate_to_pln"]) for r in conn.execute("SELECT currency, date, rate_to_pln FROM fx_rates")])

    # Zdarzenia zmiany ilości (sygnowane) wg dnia.
    events: dict[str, dict[str, float]] = {}
    for t in txs:
        day = t["ts"][:10]
        delta = t["quantity"] if t["type"] == "BUY" else -t["quantity"]
        events.setdefault(day, {}).setdefault(t["isin"], 0.0)
        events[day][t["isin"]] += delta

    start = date.fromisoformat(txs[0]["ts"][:10])
    end = date.today()
    holdings: dict[str, float] = {}
    out = []
    d = start
    while d <= end:
        day = d.isoformat()
        if day in events:
            for isin, delta in events[day].items():
                holdings[isin] = holdings.get(isin, 0.0) + delta

        total = 0.0
        for isin, qty in holdings.items():
            if qty <= 1e-9:
                continue
            price = _forward_fill(price_map.get(isin), day)
            if price is None:
                continue
            ccy = instr_ccy.get(isin)
            if ccy == "PLN":
                rate = 1.0
            else:
                rate = _forward_fill(fx_map.get(ccy), day)
                if rate is None:
                    continue
            total += qty * price * rate
        if has_external:
            total += _forward_fill((cash_dates, cash_vals), day) or 0.0

        # Benchmark: wkłady oprocentowane stałą stopą roczną od daty wpłaty.
        bench = 0.0
        for cdate, amount in contributions:
            if cdate <= d:
                years = (d - cdate).days / 365.0
                bench += amount * (1.0 + benchmark_rate) ** years

        out.append({"date": day, "value_pln": round(total, 2), "benchmark_pln": round(bench, 2)})
        d += timedelta(days=1)
    return out


def portfolio_xirr(
    conn: sqlite3.Connection,
    etf_value: float | None,
    portfolio_value: float | None = None,
) -> float | None:
    """Roczny zwrot money-weighted (XIRR).

    Jeśli są wpłaty/wypłaty, używa ich jako przepływów zewnętrznych (wpłata = −,
    wypłata = +) i wartości całego konta jako wartości końcowej — poprawny zwrot
    rachunku IKE. Bez wpłat: fallback na przepływy z transakcji (kupno −, sprzedaż +).
    """
    external = conn.execute(
        "SELECT ts, amount_pln FROM cash_flows WHERE kind IN ('deposit', 'withdrawal') ORDER BY ts ASC"
    ).fetchall()

    flows: list[tuple[date, float]] = []
    if external:
        for f in external:
            # amount_pln: wpłata +, wypłata − → przepływ inwestora ma znak przeciwny.
            flows.append((date.fromisoformat(f["ts"][:10]), -f["amount_pln"]))
        terminal = portfolio_value if portfolio_value is not None else etf_value
    else:
        txs = conn.execute("SELECT ts, type, value_pln FROM transactions ORDER BY ts ASC").fetchall()
        for t in txs:
            amt = -t["value_pln"] if t["type"] == "BUY" else t["value_pln"]
            flows.append((date.fromisoformat(t["ts"][:10]), amt))
        terminal = etf_value

    if terminal:
        flows.append((date.today(), terminal))
    return xirr(flows)
