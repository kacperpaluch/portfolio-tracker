"""Historia wartości portfela w czasie + backfill cen/kursów i przepływy do XIRR."""
from __future__ import annotations

import bisect
import sqlite3
from datetime import date, timedelta

from . import fx, prices
from .returns import twr, xirr


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


def instrument_history(conn: sqlite3.Connection, isin: str) -> dict | None:
    """Dzienna historia jednego waloru: cena natywna, kurs NBP, cena w PLN i posiadana ilość."""
    inst = conn.execute("SELECT * FROM instruments WHERE isin = ?", (isin,)).fetchone()
    if inst is None:
        return None
    currency = inst["currency"] or "PLN"

    price_rows = conn.execute(
        "SELECT date, price FROM prices WHERE isin = ? ORDER BY date ASC", (isin,)
    ).fetchall()

    fx_rows = conn.execute(
        "SELECT date, rate_to_pln FROM fx_rates WHERE currency = ? ORDER BY date ASC", (currency,)
    ).fetchall()
    fx_dates = [r["date"] for r in fx_rows]
    fx_vals = [r["rate_to_pln"] for r in fx_rows]

    # Zdarzenia (data, delta_ilości, wartość_PLN) — do śledzenia ilości i kosztu (średni koszt).
    tx_rows = conn.execute(
        "SELECT ts, type, quantity, value_pln FROM transactions WHERE isin = ? ORDER BY ts ASC", (isin,)
    ).fetchall()
    events = sorted(
        (t["ts"][:10], t["type"], t["quantity"], t["value_pln"]) for t in tx_rows
    )

    rows = []
    held = 0.0
    cost = 0.0
    ev_idx = 0
    for pr in price_rows:
        day = pr["date"]
        # Zastosuj transakcje z datą <= bieżący dzień (średni koszt).
        while ev_idx < len(events) and events[ev_idx][0] <= day:
            _, etype, eqty, evalue = events[ev_idx]
            if etype == "BUY":
                held += eqty
                cost += evalue
            else:
                avg = (cost / held) if held else 0.0
                cost -= avg * eqty
                held -= eqty
                if held <= 1e-9:
                    held, cost = 0.0, 0.0
            ev_idx += 1

        fx_rate = 1.0 if currency == "PLN" else _forward_fill((fx_dates, fx_vals), day)
        price_pln = round(pr["price"] * fx_rate, 4) if fx_rate is not None else None
        qty = round(held, 6) if held > 1e-9 else 0.0
        rows.append({
            "date": day,
            "price_native": round(pr["price"], 4),
            "currency": currency,
            "fx_rate": round(fx_rate, 4) if fx_rate is not None else None,
            "price_pln": price_pln,
            "quantity": qty,
            "value_pln": round(qty * price_pln, 2) if price_pln is not None else None,
            "cost_pln": round(cost, 2),
            "_native_raw": pr["price"],
        })

    # Kurs bazowy = kurs z pierwszego dnia z niezerową pozycją (moment wejścia).
    baseline_fx = next((r["fx_rate"] for r in rows if r["quantity"] > 0 and r["fx_rate"] is not None), None)
    for r in rows:
        if baseline_fx is not None and r["quantity"] > 0:
            r["value_const_fx"] = round(r["quantity"] * r["_native_raw"] * baseline_fx, 2)
        else:
            r["value_const_fx"] = r["value_pln"]
        del r["_native_raw"]

    # Atrybucja zysku na stan końcowy: total = z instrumentu + z waluty.
    summary = None
    last = rows[-1] if rows else None
    if last and last["value_pln"] is not None and last["quantity"] > 0:
        total_pl = round(last["value_pln"] - last["cost_pln"], 2)
        fx_pl = round(last["value_pln"] - last["value_const_fx"], 2)
        summary = {
            "value_pln": last["value_pln"],
            "cost_pln": last["cost_pln"],
            "total_pl_pln": total_pl,
            "fx_pl_pln": fx_pl,
            "instrument_pl_pln": round(total_pl - fx_pl, 2),
            "baseline_fx": round(baseline_fx, 4) if baseline_fx else None,
        }

    return {
        "isin": isin,
        "name": inst["name"],
        "ticker": inst["ticker"],
        "currency": currency,
        "category": inst["category"],
        "rows": rows,
        "summary": summary,
    }


def portfolio_twr(conn: sqlite3.Connection) -> float | None:
    """Roczny TWR całego konta — z dziennej serii wartości i przepływów zewnętrznych."""
    series_rows = portfolio_history(conn)
    if len(series_rows) < 2:
        return None
    series = [(date.fromisoformat(r["date"]), r["value_pln"]) for r in series_rows]

    flows = conn.execute(
        "SELECT ts, amount_pln FROM cash_flows WHERE kind IN ('deposit', 'withdrawal')"
    ).fetchall()
    cf_by_day: dict[date, float] = {}
    for f in flows:
        d = date.fromisoformat(f["ts"][:10])
        cf_by_day[d] = cf_by_day.get(d, 0.0) + f["amount_pln"]

    return twr(series, cf_by_day)


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
