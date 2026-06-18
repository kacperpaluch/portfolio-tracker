"""Historia wartości portfela w czasie + backfill cen/kursów i przepływy do XIRR."""
from __future__ import annotations

import bisect
import sqlite3
from datetime import date, timedelta

from . import cpi, fx, prices
from .returns import twr, twr_detail, twr_index, xirr


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

    cpi_points = cpi.refresh_cpi(conn)

    return {"prices": price_points, "fx": fx_points, "cpi": cpi_points, "start": start, "end": end}


def refresh_latest(conn: sqlite3.Connection, fill_gaps: bool = True) -> dict:
    """Odświeża bieżące ceny i kursy FX, a przy okazji dociąga luki w historii.

    Dla każdego aktywnego, skonfigurowanego instrumentu pobiera najświeższy punkt
    (`fetch_latest`), a gdy w cache jest luka między ostatnim znanym dniem a dziś
    (np. po awarii sieci o 21:00 albo dla świeżo dodanego instrumentu), uzupełnia
    brakujący zakres (`fetch_history`). To samo dla kursów NBP (`backfill_range`).
    Nakładające się zakresy są idempotentne (INSERT OR REPLACE).

    Bez `fill_gaps` zachowuje się jak dawne odświeżanie — sam bieżący punkt.
    """
    row = conn.execute("SELECT MIN(ts) AS first_ts FROM transactions").fetchone()
    first_day = row["first_ts"][:10] if row and row["first_ts"] else None
    end = date.today().isoformat()

    # Tylko AKTUALNIE TRZYMANE walory (suma BUY−SELL > 0). Sprzedany do zera ETF nie
    # potrzebuje już bieżącej wyceny — przestajemy go odpytywać i zaśmiecać cache nowymi
    # punktami pod dzisiejszą datą. Historia z okresu posiadania zostaje w cache nietknięta;
    # pełną rekonstrukcję od zera robi dopiero ręczny `backfill_all` (obejmuje wszystkie walory).
    held = {
        r["isin"] for r in conn.execute(
            "SELECT isin FROM transactions GROUP BY isin "
            "HAVING SUM(CASE WHEN type = 'BUY' THEN quantity ELSE -quantity END) > 1e-9"
        )
    }
    instruments = [
        dict(r) for r in conn.execute(
            "SELECT * FROM instruments WHERE active = 1 AND needs_config = 0"
        )
        if r["isin"] in held
    ]

    prices_updated = 0
    gap_prices = 0
    for inst in instruments:
        if fill_gaps and first_day:
            cached = prices.latest_cached_price(conn, inst["isin"])
            # Brak cache → dociągnij od pierwszej transakcji; inaczej od ostatniego znanego dnia.
            gap_start = cached[0] if cached else first_day
            if gap_start < end:
                gap_prices += prices.fetch_history(conn, inst, gap_start, end)
        if prices.fetch_latest(conn, inst):
            prices_updated += 1

    currencies = {i["currency"] for i in instruments if i["currency"] and i["currency"] != "PLN"}
    fx_updated = 0
    gap_fx = 0
    for cur in currencies:
        if fill_gaps and first_day:
            last_fx = conn.execute(
                "SELECT MAX(date) FROM fx_rates WHERE currency = ?", (cur,)
            ).fetchone()[0]
            gap_start = last_fx or first_day
            if gap_start < end:
                gap_fx += fx.backfill_range(conn, cur, gap_start, end)
        try:
            fx.get_rate(conn, cur)
            fx_updated += 1
        except Exception:
            pass

    cpi_points = cpi.refresh_cpi(conn)

    return {
        "prices": prices_updated,
        "fx": fx_updated,
        "gap_prices": gap_prices,
        "gap_fx": gap_fx,
        "cpi": cpi_points,
        "instruments": len(instruments),
    }


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
    """Ostatnia wartość z datą <= day. Przed pierwszą znaną datą zwraca najwcześniejszą
    wartość (back-fill startu), żeby walor z późniejszym pierwszym notowaniem nie „wskakiwał"
    z 0 do pełnej wartości — co psułoby TWR i wykres."""
    if not series:
        return None
    dates, values = series
    if not dates:
        return None
    idx = bisect.bisect_right(dates, day) - 1
    return values[idx] if idx >= 0 else values[0]


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


def portfolio_history(
    conn: sqlite3.Connection, benchmark_rate: float = 0.05, cpi_spread: float = 0.0
) -> list[dict]:
    """Dzienna seria wartości portfela w PLN od pierwszej transakcji do dziś.

    Gdy istnieją wpłaty/wypłaty, do wyceny ETF doliczane jest saldo gotówki
    (pełna wartość konta). Bez wpłat seria pokazuje samą wycenę instrumentów.

    Dla każdego dnia liczone są DWA benchmarki (oba money-weighted — każdy wkład
    oprocentowany od swojej daty):
      * `benchmark_pln`/`benchmark_pct` — stała stopa roczna `benchmark_rate`.
      * `benchmark_cpi_pln`/`benchmark_cpi_pct` — inflacja (indeks HICP) + `cpi_spread`
        rocznie: wkład × indeks(dzień)/indeks(data_wpłaty) × (1+cpi_spread)^lata.
        Gdy brak danych CPI w cache (Eurostat niepobrany) → pola = None (linia się nie pokaże).
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

    # Benchmark inflacyjny: indeks HICP na dzień wpłaty (baza dla mnożnika inflacji).
    cpi_points = cpi.load_points(conn)
    has_cpi = bool(cpi_points)
    contrib_cpi = (
        [(cdate, amount, cpi.index_at(cpi_points, cdate)) for cdate, amount in contributions]
        if has_cpi else []
    )

    # Skumulowane wkłady kapitału per dzień — do przeliczenia serii na stopę zwrotu (%).
    # Budowane raz (O(wpłaty)); w pętli dziennej tylko inkrementalnie dodajemy deltę dnia.
    contrib_by_day: dict[str, float] = {}
    for cdate, amount in contributions:
        d = cdate.isoformat()
        contrib_by_day[d] = contrib_by_day.get(d, 0.0) + amount

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
    cum_contrib = 0.0  # skumulowane wkłady kapitału (do_stopa_zwrotu %)
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

        # Benchmark 1: wkłady oprocentowane stałą stopą roczną od daty wpłaty.
        bench = 0.0
        for cdate, amount in contributions:
            if cdate <= d:
                years = (d - cdate).days / 365.0
                bench += amount * (1.0 + benchmark_rate) ** years

        # Benchmark 2: inflacja (indeks HICP) + cpi_spread. Mnożnik inflacji od daty wpłaty
        # = indeks(dziś)/indeks(wpłata); plus stała premia (1+spread)^lata.
        bench_cpi = 0.0
        if has_cpi:
            idx_now = cpi.index_at(cpi_points, d)
            for cdate, amount, idx_base in contrib_cpi:
                if cdate <= d and idx_base:
                    years = (d - cdate).days / 365.0
                    bench_cpi += amount * (idx_now / idx_base) * (1.0 + cpi_spread) ** years

        # Stopa zwrotu (%) vs benchmarki — inkrementalnie, O(dni + wpłaty).
        # Przed pierwszą wpłatą (cum_contrib <= 0) → null (przerwa w linii).
        cum_contrib += contrib_by_day.get(day, 0.0)
        if cum_contrib > 1e-9:
            portfolio_pct = round((total - cum_contrib) / cum_contrib * 100, 2)
            benchmark_pct = round((bench - cum_contrib) / cum_contrib * 100, 2)
            benchmark_cpi_pct = round((bench_cpi - cum_contrib) / cum_contrib * 100, 2) if has_cpi else None
        else:
            portfolio_pct = None
            benchmark_pct = None
            benchmark_cpi_pct = None

        out.append({
            "date": day,
            "value_pln": round(total, 2),
            "benchmark_pln": round(bench, 2),
            "benchmark_cpi_pln": round(bench_cpi, 2) if has_cpi else None,
            "portfolio_pct": portfolio_pct,
            "benchmark_pct": benchmark_pct,
            "benchmark_cpi_pct": benchmark_cpi_pct,
        })
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


def portfolio_daily_changes(conn: sqlite3.Connection) -> list[dict]:
    """Dzienny zysk/strata portfela (zmiana wartości rynkowej ETF dzień-do-dnia).

    Liczone na wartości samych instrumentów (gotówka nie ma stopy zwrotu, więc P/L
    jej nie dotyczy). `change_pln = wartość_ETF[d] − wartość_ETF[d−1] − przepływ_handlowy[d]`,
    gdzie przepływ = koszt kupna (+) / przychód ze sprzedaży (−) tego dnia — dzięki temu sam
    zakup nie liczy się jako zysk. `flow_pln` pokazuje ten przepływ (czytelność skoków).
    Seria rosnąco po dacie; dni bez notowań mają zmianę 0 (forward-fill ceny).

    `change_pln` rozbijane na dwa źródła (`instrument_pln + fx_pln == change_pln`):
    - `fx_pln`  = efekt zmiany kursu NBP: Σ ilość × cena_dziś × (kurs_dziś − kurs_wczoraj),
    - `instrument_pln` = reszta, czyli ruch samej ceny instrumentu (dla PLN = całość).
    Dzięki temu widać, czy dzień zrobił ETF, czy złoty (np. skok fixingu w poniedziałek).
    """
    txs = conn.execute(
        "SELECT ts, isin, type, quantity, value_pln FROM transactions ORDER BY ts ASC"
    ).fetchall()
    if not txs:
        return []

    instr_ccy = {r["isin"]: r["currency"] for r in conn.execute("SELECT isin, currency FROM instruments")}
    price_map = _series_map([(r["isin"], r["date"], r["price"]) for r in conn.execute("SELECT isin, date, price FROM prices")])
    fx_map = _series_map([(r["currency"], r["date"], r["rate_to_pln"]) for r in conn.execute("SELECT currency, date, rate_to_pln FROM fx_rates")])

    events: dict[str, dict[str, float]] = {}
    trade_flow: dict[str, float] = {}
    for t in txs:
        day = t["ts"][:10]
        delta = t["quantity"] if t["type"] == "BUY" else -t["quantity"]
        events.setdefault(day, {}).setdefault(t["isin"], 0.0)
        events[day][t["isin"]] += delta
        trade_flow[day] = trade_flow.get(day, 0.0) + (t["value_pln"] if t["type"] == "BUY" else -t["value_pln"])

    start = date.fromisoformat(txs[0]["ts"][:10])
    end = date.today()
    holdings: dict[str, float] = {}
    out = []
    prev_val: float | None = None
    prev_day: str | None = None
    d = start
    while d <= end:
        day = d.isoformat()
        if day in events:
            for isin, delta in events[day].items():
                holdings[isin] = holdings.get(isin, 0.0) + delta

        total = 0.0
        fx_comp = 0.0  # efekt kursu NBP D/D (Σ ilość × cena_dziś × Δkurs)
        for isin, qty in holdings.items():
            if qty <= 1e-9:
                continue
            price = _forward_fill(price_map.get(isin), day)
            if price is None:
                continue
            ccy = instr_ccy.get(isin)
            rate = 1.0 if ccy == "PLN" else _forward_fill(fx_map.get(ccy), day)
            if rate is None:
                continue
            total += qty * price * rate
            if prev_day is not None and ccy != "PLN":
                rate_prev = _forward_fill(fx_map.get(ccy), prev_day)
                if rate_prev is not None:
                    fx_comp += qty * price * (rate - rate_prev)

        if prev_val is not None:
            flow = trade_flow.get(day, 0.0)
            change = total - prev_val - flow
            base = prev_val + flow
            # Instrument = reszta po wyjęciu kursu; liczone z zaokrąglonych wartości,
            # by kolumny zawsze sumowały się do change_pln (bez błędu o grosz).
            change_r = round(change, 2)
            fx_r = round(fx_comp, 2)
            out.append({
                "date": day,
                "value_pln": round(total, 2),
                "flow_pln": round(flow, 2),
                "change_pln": change_r,
                "instrument_pln": round(change_r - fx_r, 2),
                "fx_pln": fx_r,
                "change_pct": round(change / base * 100, 2) if abs(base) > 1e-9 else None,
            })
        prev_val = total
        prev_day = day
        d += timedelta(days=1)
    return out


def _window_returns(
    series: list[tuple[date, float]],
    cf_by_day: dict[date, float],
    start_d: date,
) -> dict | None:
    """Zwroty (TWR skumulowany/roczny + XIRR) dla okna [start_d, koniec serii]."""
    sub = [(d, v) for d, v in series if d >= start_d]
    if len(sub) < 2:
        return None
    start, end = sub[0][0], sub[-1][0]

    # TWR: neutralizuj wkłady dopiero PO dniu startu (wartość startowa już je zawiera).
    cf_intra = {d: a for d, a in cf_by_day.items() if d > start}
    detail = twr_detail(sub, cf_intra)
    twr_cum, twr_ann = (None, None) if detail is None else detail

    # XIRR okna: wartość startowa = wkład kapitału (−), wartość końcowa = wypływ (+).
    flows = [(start, -sub[0][1])]
    for d, amt in sorted(cf_by_day.items()):
        if start < d <= end:
            flows.append((d, -amt))
    flows.append((end, sub[-1][1]))
    xr = xirr(flows)

    return {
        "from": start.isoformat(),
        "to": end.isoformat(),
        "twr": round(twr_cum, 4) if twr_cum is not None else None,
        "twr_annualized": round(twr_ann, 4) if twr_ann is not None else None,
        "xirr": round(xr, 4) if xr is not None else None,
    }


def portfolio_returns(conn: sqlite3.Connection) -> dict:
    """Zwroty portfela w standardowych okresach: 1M, 3M, YTD, 1R, od początku.

    Dla każdego okresu zwraca TWR skumulowany (wynik portfela w tym okresie),
    TWR zannualizowany oraz XIRR (money-weighted, roczny). Wkłady kapitału
    (wpłaty lub — bez gotówki — kupna/sprzedaże) są spójne z serią wartości,
    więc neutralizacja TWR i baza XIRR liczą tylko zwrot portfela, nie dopłaty.
    """
    series_rows = portfolio_history(conn)
    if len(series_rows) < 2:
        return {}
    series = [(date.fromisoformat(r["date"]), r["value_pln"]) for r in series_rows]

    _, has_external = _cash_timeline(conn)
    cf_by_day: dict[date, float] = {}
    for cdate, amount in _contributions(conn, has_external):
        cf_by_day[cdate] = cf_by_day.get(cdate, 0.0) + amount

    inception, today = series[0][0], series[-1][0]
    windows = {
        "1m": today - timedelta(days=30),
        "3m": today - timedelta(days=91),
        "ytd": date(today.year, 1, 1),
        "1y": today - timedelta(days=365),
        "all": inception,
    }
    out: dict[str, dict | None] = {}
    for key, start_d in windows.items():
        out[key] = _window_returns(series, cf_by_day, max(start_d, inception))
    return out


def portfolio_drawdown(conn: sqlite3.Connection) -> dict:
    """Obsunięcie portfela (drawdown) liczone na indeksie wzrostu TWR — flow-neutral.

    Drawdown danego dnia = `indeks / dotychczasowy_szczyt − 1` (≤ 0). Indeks to
    skumulowany TWR (a NIE surowa wartość PLN), więc wpłaty IKE nie maskują spadków,
    a wypłaty nie udają obsunięć — spójnie z resztą metryk (TWR, zwroty okresowe).

    Zwraca:
    - `series` — dzienna krzywa „pod wodą" (`drawdown_pct` ≤ 0) do wykresu,
    - `max_drawdown` (%) z datami szczytu/dołka (`..._from`/`..._to`) i odbicia (`recovery_date`),
    - `current_drawdown` (%) oraz `in_drawdown` (czy jesteśmy obecnie pod szczytem).
    """
    series_rows = portfolio_history(conn)
    empty = {
        "series": [], "max_drawdown": None, "max_drawdown_from": None,
        "max_drawdown_to": None, "recovery_date": None, "current_drawdown": None,
        "in_drawdown": False,
    }
    if len(series_rows) < 2:
        return empty
    series = [(date.fromisoformat(r["date"]), r["value_pln"]) for r in series_rows]

    _, has_external = _cash_timeline(conn)
    cf_by_day: dict[date, float] = {}
    for cdate, amount in _contributions(conn, has_external):
        cf_by_day[cdate] = cf_by_day.get(cdate, 0.0) + amount

    index = twr_index(series, cf_by_day)  # [(data, growth)], growth[0] = 1.0
    if not index:
        return empty

    out = []
    peak = index[0][1]
    peak_date = index[0][0]
    max_dd = 0.0
    max_dd_peak = peak_date
    max_dd_peak_level = peak
    max_dd_trough = index[0][0]
    for d, g in index:
        if g > peak:
            peak, peak_date = g, d
        dd = (g / peak - 1.0) if peak > 1e-12 else 0.0
        if dd < max_dd:
            max_dd, max_dd_trough = dd, d
            max_dd_peak, max_dd_peak_level = peak_date, peak
        out.append({"date": d.isoformat(), "drawdown_pct": round(dd * 100, 2)})

    # Odbicie: pierwszy dzień po dołku, gdy indeks wraca do poziomu szczytu sprzed obsunięcia.
    recovery_date = None
    if max_dd < 0:
        for d, g in index:
            if d > max_dd_trough and g >= max_dd_peak_level - 1e-12:
                recovery_date = d.isoformat()
                break

    current_dd = out[-1]["drawdown_pct"]
    return {
        "series": out,
        "max_drawdown": round(max_dd * 100, 2),
        "max_drawdown_from": max_dd_peak.isoformat() if max_dd < 0 else None,
        "max_drawdown_to": max_dd_trough.isoformat() if max_dd < 0 else None,
        "recovery_date": recovery_date,
        "current_drawdown": current_dd,
        "in_drawdown": current_dd < 0,
    }


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
