"""Przekrojowa analiza wyniku według instrumentów, kategorii i wpłat."""
from __future__ import annotations

import sqlite3

from . import history as history_mod
from . import portfolio as portfolio_mod


def build(conn: sqlite3.Connection) -> dict:
    valued = portfolio_mod.value_positions(conn)
    positions = {p["isin"]: p for p in valued["positions"]}
    instrument_rows = {
        r["isin"]: dict(r) for r in conn.execute(
            "SELECT isin, name, ticker, category FROM instruments"
        )
    }

    state: dict[str, dict[str, float]] = {}
    realized: dict[str, float] = {}
    txs = conn.execute(
        "SELECT isin, type, quantity, value_pln, commission_pln, ts "
        "FROM transactions ORDER BY ts ASC, id ASC"
    ).fetchall()
    for tx in txs:
        item = state.setdefault(tx["isin"], {"quantity": 0.0, "cost": 0.0})
        if tx["type"] == "BUY":
            item["quantity"] += tx["quantity"]
            item["cost"] += tx["value_pln"]
        else:
            avg = item["cost"] / item["quantity"] if item["quantity"] else 0.0
            realized[tx["isin"]] = realized.get(tx["isin"], 0.0) + tx["value_pln"] - avg * tx["quantity"]
            item["quantity"] -= tx["quantity"]
            item["cost"] -= avg * tx["quantity"]
            if item["quantity"] <= 1e-9:
                item["quantity"], item["cost"] = 0.0, 0.0

    all_isins = set(instrument_rows) & (set(state) | set(realized))
    total_pl = sum(
        (positions.get(isin, {}).get("pl_pln") or 0.0) + realized.get(isin, 0.0)
        for isin in all_isins
    )
    instruments = []
    categories: dict[str, dict[str, float | int | str]] = {}
    for isin in all_isins:
        meta = instrument_rows[isin]
        position = positions.get(isin, {})
        unrealized = position.get("pl_pln") or 0.0
        realized_pl = realized.get(isin, 0.0)
        combined = unrealized + realized_pl
        category = (meta.get("category") or "").strip() or "Nieprzypisane"
        row = {
            "isin": isin,
            "name": meta["name"],
            "ticker": meta.get("ticker"),
            "category": category,
            "value_pln": position.get("value_pln") or 0.0,
            "cost_pln": position.get("cost_pln") or 0.0,
            "unrealized_pl_pln": round(unrealized, 2),
            "realized_pl_pln": round(realized_pl, 2),
            "total_pl_pln": round(combined, 2),
            "contribution_pct": round(combined / abs(total_pl) * 100, 2) if abs(total_pl) > 0.01 else None,
        }
        instruments.append(row)
        cat = categories.setdefault(category, {
            "category": category, "value_pln": 0.0, "cost_pln": 0.0,
            "unrealized_pl_pln": 0.0, "realized_pl_pln": 0.0, "total_pl_pln": 0.0,
            "instruments": 0,
        })
        cat["value_pln"] += row["value_pln"]
        cat["cost_pln"] += row["cost_pln"]
        cat["unrealized_pl_pln"] += row["unrealized_pl_pln"]
        cat["realized_pl_pln"] += row["realized_pl_pln"]
        cat["total_pl_pln"] += row["total_pl_pln"]
        cat["instruments"] += 1

    instruments.sort(key=lambda r: abs(r["total_pl_pln"]), reverse=True)
    category_rows = []
    for cat in categories.values():
        for key in ("value_pln", "cost_pln", "unrealized_pl_pln", "realized_pl_pln", "total_pl_pln"):
            cat[key] = round(float(cat[key]), 2)
        cat["contribution_pct"] = (
            round(float(cat["total_pl_pln"]) / abs(total_pl) * 100, 2)
            if abs(total_pl) > 0.01 else None
        )
        category_rows.append(cat)
    category_rows.sort(key=lambda r: abs(r["total_pl_pln"]), reverse=True)

    contributions: dict[str, dict[str, float | str]] = {}
    for flow in conn.execute(
        "SELECT ts, kind, amount_pln FROM cash_flows "
        "WHERE kind IN ('deposit', 'withdrawal') ORDER BY ts"
    ):
        month = flow["ts"][:7]
        item = contributions.setdefault(month, {
            "month": month, "deposits_pln": 0.0, "withdrawals_pln": 0.0, "net_pln": 0.0
        })
        if flow["kind"] == "deposit":
            item["deposits_pln"] += abs(flow["amount_pln"])
        else:
            item["withdrawals_pln"] += abs(flow["amount_pln"])
        item["net_pln"] += flow["amount_pln"]
    contribution_rows = list(contributions.values())
    for item in contribution_rows:
        for key in ("deposits_pln", "withdrawals_pln", "net_pln"):
            item[key] = round(float(item[key]), 2)

    first_tx = txs[0]["ts"] if txs else None
    last_tx = txs[-1]["ts"] if txs else None
    return {
        "instruments": instruments,
        "categories": category_rows,
        "contributions": contribution_rows,
        "activity": {
            "first_transaction": first_tx,
            "last_transaction": last_tx,
            "transactions": len(txs),
            "buys": sum(tx["type"] == "BUY" for tx in txs),
            "sells": sum(tx["type"] == "SELL" for tx in txs),
            "commissions_pln": round(sum(tx["commission_pln"] for tx in txs), 2),
        },
        "risk": history_mod.portfolio_drawdown(conn),
        "totals": {
            "value_pln": valued["totals"].get("portfolio_value_pln"),
            "unrealized_pl_pln": valued["totals"].get("unrealized_pl_pln"),
            "realized_pl_pln": valued["totals"].get("realized_pl_pln"),
            "total_pl_pln": valued["totals"].get("total_pl_pln"),
        },
    }
