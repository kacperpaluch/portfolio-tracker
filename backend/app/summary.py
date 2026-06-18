"""Zwięzły digest portfela do powiadomień (np. n8n → Telegram/mail).

Składa gotowy „jednym GET-em" obraz konta z istniejących modułów: wartość, P/L,
zmiana D/D, zwroty (XIRR/TWR + okresy) oraz alokacja rzeczywista vs docelowa
z odchyleniami. Czyta z cache (jak `/api/portfolio` bez refresh) — uruchamiaj po
codziennym odświeżeniu cen (cron ~21:00), nie dubluj odpytywania Yahoo/NBP.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from . import allocation as allocation_mod
from . import history as history_mod
from . import portfolio as portfolio_mod


def build(conn: sqlite3.Connection) -> dict:
    result = portfolio_mod.value_positions(conn)
    t = result["totals"]

    etf_value = t.get("value_pln")
    if etf_value is None:
        etf_value = t.get("value_pln_partial")
    portfolio_value = t.get("portfolio_value_pln")
    if portfolio_value is None:
        portfolio_value = (etf_value or 0.0) + (t.get("cash_pln") or 0.0)

    # Zmiana wartości dzień-do-dnia z dziennej serii (ostatnie dwa punkty).
    series = history_mod.portfolio_history(conn)
    day_pln = day_pct = None
    if len(series) >= 2:
        prev, last = series[-2]["value_pln"], series[-1]["value_pln"]
        day_pln = round(last - prev, 2)
        day_pct = round((last - prev) / prev * 100, 2) if prev else None

    returns = history_mod.portfolio_returns(conn)
    period = lambda key: (returns.get(key) or {}).get("twr")  # noqa: E731

    alloc = allocation_mod.compute(conn)
    # Grupa najbardziej odjechana od celu (moduł odchylenia) — gotowy trigger alertu.
    drifts = [g for g in alloc["groups"] if g.get("drift_pp") is not None]
    worst = max(drifts, key=lambda g: abs(g["drift_pp"]), default=None)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "account": {
            "value_pln": portfolio_value,
            "etf_value_pln": etf_value,
            "cash_pln": t.get("cash_pln"),
            "net_deposits_pln": t.get("net_deposits_pln"),
        },
        "pl": {
            "total_pln": t.get("total_pl_pln"),
            "unrealized_pln": t.get("unrealized_pl_pln"),
            "realized_pln": t.get("realized_pl_pln"),
            "total_return_pct": t.get("total_return_pct"),
        },
        "change": {"day_pln": day_pln, "day_pct": day_pct},
        "returns": {
            "xirr": history_mod.portfolio_xirr(conn, etf_value, portfolio_value),
            "twr": history_mod.portfolio_twr(conn),
            "ytd": period("ytd"),
            "1y": period("1y"),
            "all": period("all"),
        },
        "allocation": {
            "target_complete": alloc.get("target_complete"),
            "total_pln": alloc.get("total_pln"),
            "max_drift": {
                "category": worst["category"],
                "drift_pp": worst["drift_pp"],
                "rebalance_pln": worst["rebalance_pln"],
            } if worst else None,
            "groups": [
                {
                    "category": g["category"],
                    "target_pct": g["target_pct"],
                    "actual_pct": g["actual_pct"],
                    "drift_pp": g["drift_pp"],
                    "rebalance_pln": g["rebalance_pln"],
                }
                for g in alloc["groups"]
            ],
        },
    }
