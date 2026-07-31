"""Raporty okresowe: wyniki, benchmarki, atrybucja, przepływy i eksport CSV."""
from __future__ import annotations

import csv
import io
import sqlite3
from collections import defaultdict
from datetime import date, timedelta

from . import data_quality
from . import history as history_mod
from .returns import twr_detail, twr_index, xirr


def _round(value: float | None, digits: int = 2) -> float | None:
    return round(value, digits) if value is not None else None


def _month_end(day: date) -> date:
    next_month = date(day.year + (day.month == 12), 1 if day.month == 12 else day.month + 1, 1)
    return next_month - timedelta(days=1)


def _same_day_previous_year(day: date) -> date:
    try:
        return day.replace(year=day.year - 1)
    except ValueError:  # 29 lutego -> 28 lutego
        return day.replace(year=day.year - 1, day=28)


def _comparison_range(from_date: date, to_date: date) -> tuple[date, date]:
    # YTD i pełny rok porównujemy rok do roku (te same daty kalendarzowe).
    if from_date.month == 1 and from_date.day == 1 and from_date.year == to_date.year:
        return date(from_date.year - 1, 1, 1), _same_day_previous_year(to_date)
    # Miesiąc bieżący/pełny porównujemy z analogiczną częścią poprzedniego miesiąca.
    if from_date.day == 1 and (from_date.year, from_date.month) == (to_date.year, to_date.month):
        previous_end = from_date - timedelta(days=1)
        previous_start = date(previous_end.year, previous_end.month, 1)
        elapsed = (to_date - from_date).days
        return previous_start, min(previous_start + timedelta(days=elapsed), previous_end)
    # Dla własnego i kroczącego zakresu: bezpośrednio poprzedni okres tej samej długości.
    length = (to_date - from_date).days
    comparison_to = from_date - timedelta(days=1)
    return comparison_to - timedelta(days=length), comparison_to


def _capital_flows(conn: sqlite3.Connection) -> tuple[list[tuple[date, float]], bool]:
    _, has_external = history_mod._cash_timeline(conn)
    return history_mod._contributions(conn, has_external), has_external


def _window_rows(rows: list[dict], from_date: date, to_date: date) -> tuple[list[dict], date, date] | None:
    dated = [(date.fromisoformat(row["date"]), row) for row in rows]
    end_candidates = [(day, row) for day, row in dated if day <= to_date]
    if not end_candidates or end_candidates[-1][0] < from_date:
        return None
    end_day, _ = end_candidates[-1]
    before = [(day, row) for day, row in dated if day < from_date]
    if before:
        opening_day = before[-1][0]
    else:
        in_range = [(day, row) for day, row in dated if from_date <= day <= end_day]
        if not in_range:
            return None
        opening_day = in_range[0][0]
    selected = [row for day, row in dated if opening_day <= day <= end_day]
    return selected, opening_day, end_day


def _metric(series: list[tuple[date, float]], flows: dict[date, float]) -> dict:
    detail = twr_detail(series, flows)
    if not series:
        return {"twr": None, "twr_annualized": None, "xirr": None}
    xr_flows = [(series[0][0], -series[0][1])]
    xr_flows.extend((day, -amount) for day, amount in sorted(flows.items()))
    xr_flows.append((series[-1][0], series[-1][1]))
    xr = xirr(xr_flows)
    return {
        "twr": _round(detail[0], 6) if detail else None,
        "twr_annualized": _round(detail[1], 6) if detail else None,
        "xirr": _round(xr, 6),
    }


def _indexed_series(rows: list[dict], flows: dict[date, float]) -> list[dict]:
    fields = {
        "portfolio_pct": "value_pln",
        "benchmark_pct": "benchmark_pln",
        "benchmark_cpi_pct": "benchmark_cpi_pln",
    }
    indices: dict[str, dict[date, float]] = {}
    for output_key, source_key in fields.items():
        points = [
            (date.fromisoformat(row["date"]), float(row[source_key]))
            for row in rows if row.get(source_key) is not None
        ]
        indices[output_key] = {day: (growth - 1) * 100 for day, growth in twr_index(points, flows)}

    output = []
    for row in rows:
        day = date.fromisoformat(row["date"])
        output.append({
            "date": row["date"],
            "value_pln": row["value_pln"],
            **{key: _round(values.get(day), 4) for key, values in indices.items()},
        })
    return output


def _period_flows(conn: sqlite3.Connection, from_date: date, to_date: date) -> dict:
    totals = {"deposits_pln": 0.0, "withdrawals_pln": 0.0, "purchases_pln": 0.0, "sales_pln": 0.0}
    monthly: dict[str, dict] = {}
    kind_key = {
        "deposit": "deposits_pln", "withdrawal": "withdrawals_pln",
        "buy": "purchases_pln", "sell": "sales_pln",
    }
    rows = conn.execute(
        "SELECT ts, kind, amount_pln FROM cash_flows WHERE substr(ts, 1, 10) BETWEEN ? AND ? ORDER BY ts",
        (from_date.isoformat(), to_date.isoformat()),
    ).fetchall()
    for row in rows:
        key = kind_key.get(row["kind"])
        if not key:
            continue
        amount = abs(float(row["amount_pln"]))
        totals[key] += amount
        month = row["ts"][:7]
        item = monthly.setdefault(month, {"month": month, **{name: 0.0 for name in totals}})
        item[key] += amount
    for item in monthly.values():
        for key in totals:
            item[key] = round(item[key], 2)
        item["net_external_pln"] = round(item["deposits_pln"] - item["withdrawals_pln"], 2)
    for key in totals:
        totals[key] = round(totals[key], 2)
    totals["net_external_pln"] = round(totals["deposits_pln"] - totals["withdrawals_pln"], 2)
    totals["net_trades_pln"] = round(totals["sales_pln"] - totals["purchases_pln"], 2)
    return {"totals": totals, "monthly": list(monthly.values())}


def _cash_at(conn: sqlite3.Connection, day: date, has_external: bool) -> float:
    if not has_external:
        return 0.0
    value = conn.execute(
        "SELECT COALESCE(SUM(amount_pln), 0) FROM cash_flows WHERE substr(ts, 1, 10) <= ?",
        (day.isoformat(),),
    ).fetchone()[0]
    return round(float(value), 2)


def _snapshot_value(
    isin: str,
    day: date,
    transactions: list[sqlite3.Row],
    currency: str | None,
    price_map: dict,
    fx_map: dict,
) -> float:
    qty = 0.0
    for tx in transactions:
        if tx["isin"] == isin and tx["ts"][:10] <= day.isoformat():
            qty += tx["quantity"] if tx["type"] == "BUY" else -tx["quantity"]
    if qty <= 1e-9:
        return 0.0
    price = history_mod._forward_fill(price_map.get(isin), day.isoformat())
    if price is None:
        return 0.0
    rate = 1.0 if (currency or "PLN").upper() == "PLN" else history_mod._forward_fill(
        fx_map.get((currency or "").upper()), day.isoformat()
    )
    return qty * price * (rate or 0.0)


def _attribution(
    conn: sqlite3.Connection,
    from_date: date,
    opening_date: date,
    to_date: date,
) -> dict:
    instruments = {row["isin"]: dict(row) for row in conn.execute(
        "SELECT isin, name, ticker, category, currency FROM instruments"
    )}
    transactions = conn.execute(
        "SELECT id, ts, isin, type, quantity, value_pln, commission_pln "
        "FROM transactions WHERE substr(ts, 1, 10) <= ? ORDER BY ts, id",
        (to_date.isoformat(),),
    ).fetchall()
    price_map = history_mod._series_map([
        (row["isin"], row["date"], row["price"]) for row in conn.execute("SELECT isin, date, price FROM prices")
    ])
    fx_map = history_mod._series_map([
        (row["currency"], row["date"], row["rate_to_pln"]) for row in conn.execute("SELECT currency, date, rate_to_pln FROM fx_rates")
    ])

    realized: dict[str, float] = defaultdict(float)
    state: dict[str, dict[str, float]] = defaultdict(lambda: {"qty": 0.0, "cost": 0.0})
    for tx in transactions:
        item = state[tx["isin"]]
        if tx["type"] == "BUY":
            item["qty"] += tx["quantity"]
            item["cost"] += tx["value_pln"]
        else:
            avg = item["cost"] / item["qty"] if item["qty"] else 0.0
            if from_date.isoformat() <= tx["ts"][:10] <= to_date.isoformat():
                realized[tx["isin"]] += tx["value_pln"] - avg * tx["quantity"]
            item["qty"] -= tx["quantity"]
            item["cost"] -= avg * tx["quantity"]
            if item["qty"] <= 1e-9:
                item["qty"], item["cost"] = 0.0, 0.0

    rows = []
    for isin in sorted(set(instruments) & {tx["isin"] for tx in transactions}):
        meta = instruments[isin]
        opening_value = _snapshot_value(isin, opening_date, transactions, meta.get("currency"), price_map, fx_map)
        closing_value = _snapshot_value(isin, to_date, transactions, meta.get("currency"), price_map, fx_map)
        calc_trades = [tx for tx in transactions if tx["isin"] == isin and opening_date.isoformat() < tx["ts"][:10] <= to_date.isoformat()]
        purchases = sum(tx["value_pln"] for tx in calc_trades if tx["type"] == "BUY")
        sales = sum(tx["value_pln"] for tx in calc_trades if tx["type"] == "SELL")
        total_pl = closing_value - opening_value - purchases + sales
        realized_pl = realized.get(isin, 0.0)
        if all(abs(value) < 0.005 for value in (opening_value, closing_value, purchases, sales, realized_pl)):
            continue
        rows.append({
            "isin": isin,
            "name": meta["name"],
            "ticker": meta.get("ticker"),
            "category": (meta.get("category") or "").strip() or "Nieprzypisane",
            "currency": (meta.get("currency") or "?").upper(),
            "opening_value_pln": round(opening_value, 2),
            "closing_value_pln": round(closing_value, 2),
            "purchases_pln": round(purchases, 2),
            "sales_pln": round(sales, 2),
            "realized_pl_pln": round(realized_pl, 2),
            "unrealized_change_pln": round(total_pl - realized_pl, 2),
            "total_pl_pln": round(total_pl, 2),
        })

    total = sum(row["total_pl_pln"] for row in rows)
    for row in rows:
        row["contribution_pct"] = round(row["total_pl_pln"] / abs(total) * 100, 2) if abs(total) > 0.01 else None
    rows.sort(key=lambda row: row["total_pl_pln"], reverse=True)

    def aggregate(field: str, label: str) -> list[dict]:
        grouped: dict[str, dict] = {}
        for row in rows:
            key = row[field]
            item = grouped.setdefault(key, {label: key, "instruments": 0, "total_pl_pln": 0.0})
            item["instruments"] += 1
            item["total_pl_pln"] += row["total_pl_pln"]
        output = []
        for item in grouped.values():
            item["total_pl_pln"] = round(item["total_pl_pln"], 2)
            item["contribution_pct"] = round(item["total_pl_pln"] / abs(total) * 100, 2) if abs(total) > 0.01 else None
            output.append(item)
        return sorted(output, key=lambda item: abs(item["total_pl_pln"]), reverse=True)

    return {
        "instruments": rows,
        "categories": aggregate("category", "category"),
        "currencies": aggregate("currency", "currency"),
        "winners": rows[:5],
        "losers": sorted(rows, key=lambda row: row["total_pl_pln"])[:5],
        "totals": {
            "realized_pl_pln": round(sum(row["realized_pl_pln"] for row in rows), 2),
            "unrealized_change_pln": round(sum(row["unrealized_change_pln"] for row in rows), 2),
            "total_pl_pln": round(total, 2),
        },
    }


def _activity(conn: sqlite3.Connection, from_date: date, to_date: date) -> dict:
    rows = conn.execute(
        "SELECT type, commission_pln FROM transactions WHERE substr(ts, 1, 10) BETWEEN ? AND ?",
        (from_date.isoformat(), to_date.isoformat()),
    ).fetchall()
    return {
        "transactions": len(rows),
        "buys": sum(row["type"] == "BUY" for row in rows),
        "sells": sum(row["type"] == "SELL" for row in rows),
        "commissions_pln": round(sum(float(row["commission_pln"]) for row in rows), 2),
    }


def _build_period(
    conn: sqlite3.Connection,
    history_rows: list[dict],
    capital_flows: list[tuple[date, float]],
    has_external: bool,
    from_date: date,
    to_date: date,
    include_details: bool = True,
) -> dict | None:
    window = _window_rows(history_rows, from_date, to_date)
    if not window:
        return None
    rows, opening_date, end_date = window
    calc_flows: dict[date, float] = defaultdict(float)
    for day, amount in capital_flows:
        if opening_date < day <= end_date:
            calc_flows[day] += amount
    portfolio_series = [(date.fromisoformat(row["date"]), float(row["value_pln"])) for row in rows]
    portfolio_metric = _metric(portfolio_series, dict(calc_flows))

    benchmark_metrics = {}
    for label, key in (("fixed", "benchmark_pln"), ("inflation", "benchmark_cpi_pln")):
        series = [(date.fromisoformat(row["date"]), float(row[key])) for row in rows if row.get(key) is not None]
        benchmark_metrics[label] = _metric(series, dict(calc_flows)) if len(series) >= 2 else {"twr": None, "twr_annualized": None, "xirr": None}

    opening_value = portfolio_series[0][1]
    closing_value = portfolio_series[-1][1]
    net_capital = sum(calc_flows.values())
    result = {
        "requested_from": from_date.isoformat(),
        "requested_to": to_date.isoformat(),
        "opening_date": opening_date.isoformat(),
        "from": max(from_date, opening_date).isoformat(),
        "to": end_date.isoformat(),
        "days": max(0, (end_date - max(from_date, opening_date)).days + 1),
        "opening_value_pln": round(opening_value, 2),
        "closing_value_pln": round(closing_value, 2),
        "net_capital_pln": round(net_capital, 2),
        "result_pln": round(closing_value - opening_value - net_capital, 2),
        **portfolio_metric,
        "benchmark_fixed": benchmark_metrics["fixed"],
        "benchmark_inflation": benchmark_metrics["inflation"],
        "excess_fixed_pp": _round((portfolio_metric["twr"] - benchmark_metrics["fixed"]["twr"]) * 100, 2)
            if portfolio_metric["twr"] is not None and benchmark_metrics["fixed"]["twr"] is not None else None,
        "excess_inflation_pp": _round((portfolio_metric["twr"] - benchmark_metrics["inflation"]["twr"]) * 100, 2)
            if portfolio_metric["twr"] is not None and benchmark_metrics["inflation"]["twr"] is not None else None,
    }
    if include_details:
        result.update({
            "series": _indexed_series(rows, dict(calc_flows)),
            "flows": _period_flows(conn, from_date, end_date),
            "cash": {
                "opening_pln": _cash_at(conn, opening_date, has_external),
                "closing_pln": _cash_at(conn, end_date, has_external),
            },
            "activity": _activity(conn, from_date, end_date),
            "attribution": _attribution(conn, from_date, opening_date, end_date),
        })
    return result


def _monthly_returns(history_rows: list[dict], capital_flows: list[tuple[date, float]]) -> list[dict]:
    if not history_rows:
        return []
    first = date.fromisoformat(history_rows[0]["date"])
    last = date.fromisoformat(history_rows[-1]["date"])
    current = date(first.year, first.month, 1)
    by_year: dict[int, dict] = {}
    while current <= last:
        window = _window_rows(history_rows, current, min(_month_end(current), last))
        value = None
        if window:
            rows, opening, end = window
            flows: dict[date, float] = defaultdict(float)
            for day, amount in capital_flows:
                if opening < day <= end:
                    flows[day] += amount
            series = [(date.fromisoformat(row["date"]), float(row["value_pln"])) for row in rows]
            detail = twr_detail(series, dict(flows))
            value = _round(detail[0] * 100, 2) if detail else None
        year = by_year.setdefault(current.year, {"year": current.year, "months": {}})
        year["months"][str(current.month)] = value
        current = date(current.year + (current.month == 12), 1 if current.month == 12 else current.month + 1, 1)

    for year, item in by_year.items():
        window = _window_rows(history_rows, date(year, 1, 1), min(date(year, 12, 31), last))
        annual = None
        if window:
            rows, opening, end = window
            flows: dict[date, float] = defaultdict(float)
            for day, amount in capital_flows:
                if opening < day <= end:
                    flows[day] += amount
            detail = twr_detail(
                [(date.fromisoformat(row["date"]), float(row["value_pln"])) for row in rows],
                dict(flows),
            )
            annual = _round(detail[0] * 100, 2) if detail else None
        item["annual_pct"] = annual
    return [by_year[year] for year in sorted(by_year, reverse=True)]


def build(
    conn: sqlite3.Connection,
    from_date: date,
    to_date: date,
    benchmark_rate: float = 0.05,
    cpi_spread: float = 0.0,
) -> dict:
    if from_date > to_date:
        raise ValueError("Data początkowa nie może być późniejsza niż końcowa")
    if to_date > date.today():
        raise ValueError("Raport nie może kończyć się w przyszłości")
    history_rows = history_mod.portfolio_history(conn, benchmark_rate, cpi_spread)
    if not history_rows:
        raise ValueError("Brak danych historycznych do przygotowania raportu")
    capital_flows, has_external = _capital_flows(conn)
    current = _build_period(conn, history_rows, capital_flows, has_external, from_date, to_date)
    if current is None:
        raise ValueError("Wybrany okres nie zawiera danych portfela")

    comparison_from, comparison_to = _comparison_range(from_date, to_date)
    comparison = _build_period(
        conn, history_rows, capital_flows, has_external,
        comparison_from, comparison_to, include_details=False,
    )
    return {
        "generated_at": date.today().isoformat(),
        "benchmark_rate": benchmark_rate,
        "cpi_spread": cpi_spread,
        "period": current,
        "comparison": comparison,
        "monthly_returns": _monthly_returns(history_rows, capital_flows),
        "quality": data_quality.inspect(conn),
    }


def export_csv(report: dict) -> str:
    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.writer(output, delimiter=";")
    period = report["period"]
    writer.writerow(["Raport portfela", period["from"], period["to"]])
    writer.writerow([])
    writer.writerow(["Podsumowanie", "Wartość"])
    for label, key in (
        ("Wartość początkowa PLN", "opening_value_pln"),
        ("Wartość końcowa PLN", "closing_value_pln"),
        ("Wynik okresu PLN", "result_pln"),
        ("TWR", "twr"), ("XIRR roczny", "xirr"),
        ("Kapitał netto PLN", "net_capital_pln"),
    ):
        writer.writerow([label, period.get(key)])
    writer.writerow([])
    writer.writerow(["Instrument", "Ticker", "Kategoria", "Waluta", "Wynik PLN", "Zrealizowany PLN", "Zmiana niezrealizowanego PLN"])
    for row in period["attribution"]["instruments"]:
        writer.writerow([row["name"], row.get("ticker"), row["category"], row["currency"], row["total_pl_pln"], row["realized_pl_pln"], row["unrealized_change_pln"]])
    writer.writerow([])
    writer.writerow(["Miesiąc", "Wpłaty PLN", "Wypłaty PLN", "Zakupy PLN", "Sprzedaże PLN", "Kapitał netto PLN"])
    for row in period["flows"]["monthly"]:
        writer.writerow([row["month"], row["deposits_pln"], row["withdrawals_pln"], row["purchases_pln"], row["sales_pln"], row["net_external_pln"]])
    writer.writerow([])
    writer.writerow(["Rok", *[str(month) for month in range(1, 13)], "Rok TWR %"])
    for row in report["monthly_returns"]:
        writer.writerow([row["year"], *[row["months"].get(str(month)) for month in range(1, 13)], row["annual_pct"]])
    return output.getvalue()
