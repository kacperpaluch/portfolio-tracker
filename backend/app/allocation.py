"""Alokacja docelowa: model wag grup vs rzeczywisty udział (z gotówką jako grupą)."""
from __future__ import annotations

import sqlite3

from . import cash as cash_mod
from . import portfolio as portfolio_mod

CASH_GROUP = "Gotówka"
UNASSIGNED = "Nieprzypisane"


def get_targets(conn: sqlite3.Connection) -> dict[str, float]:
    return {r["category"]: r["weight_pct"] for r in conn.execute("SELECT * FROM target_allocation")}


def set_targets(conn: sqlite3.Connection, targets: dict[str, float]) -> dict[str, float]:
    """Zastępuje cały model docelowy. Puste/zerowe wagi pomijane."""
    conn.execute("DELETE FROM target_allocation")
    for category, weight in targets.items():
        cat = (category or "").strip()
        if not cat or weight is None:
            continue
        conn.execute(
            "INSERT OR REPLACE INTO target_allocation (category, weight_pct) VALUES (?, ?)",
            (cat, float(weight)),
        )
    conn.commit()
    return get_targets(conn)


def compute(conn: sqlite3.Connection) -> dict:
    """Zwraca porównanie alokacji: per grupa docelowy %, rzeczywisty %, odchylenie, kwota rebalansu."""
    result = portfolio_mod.value_positions(conn)
    positions = result["positions"]

    # Rzeczywiste wartości per grupa (kategoria instrumentu; brak -> "Nieprzypisane").
    actual: dict[str, float] = {}
    for p in positions:
        # Gdy brak bieżącej wyceny, użyj kosztu, by pozycja nie znikała z alokacji.
        val = p["value_pln"] if p["value_pln"] is not None else p["cost_pln"]
        cat = (p.get("category") or "").strip() or UNASSIGNED
        actual[cat] = actual.get(cat, 0.0) + val

    cash = cash_mod.balance(conn)
    if cash:
        actual[CASH_GROUP] = actual.get(CASH_GROUP, 0.0) + cash

    targets = get_targets(conn)
    total = sum(actual.values())

    groups = []
    for cat in sorted(set(actual) | set(targets)):
        actual_pln = round(actual.get(cat, 0.0), 2)
        actual_pct = round(actual_pln / total * 100, 2) if total else None
        target_pct = targets.get(cat)
        drift_pp = round((actual_pct or 0) - target_pct, 2) if target_pct is not None and actual_pct is not None else None
        # Kwota do rebalansu: ile dokupić(+)/sprzedać(−), by trafić w docelowy %.
        rebalance_pln = round((target_pct / 100 * total) - actual_pln, 2) if target_pct is not None and total else None
        groups.append({
            "category": cat,
            "target_pct": target_pct,
            "actual_pln": actual_pln,
            "actual_pct": actual_pct,
            "drift_pp": drift_pp,
            "rebalance_pln": rebalance_pln,
        })

    target_sum = round(sum(targets.values()), 2) if targets else 0.0
    return {
        "groups": groups,
        "total_pln": round(total, 2),
        "target_sum_pct": target_sum,
        "target_complete": abs(target_sum - 100.0) < 0.01 if targets else False,
    }


def contribution_plan(conn: sqlite3.Connection, amount_pln: float) -> dict:
    """Symuluje podział nowej wpłaty bez sprzedaży istniejących pozycji."""
    if amount_pln <= 0:
        raise ValueError("Kwota wpłaty musi być większa od zera")
    allocation = compute(conn)
    if not allocation["target_complete"]:
        raise ValueError("Wagi docelowe muszą sumować się do 100%")

    current = {g["category"]: g["actual_pln"] for g in allocation["groups"]}
    targets = get_targets(conn)
    future_total = allocation["total_pln"] + amount_pln
    desired_cash = targets.get(CASH_GROUP, 0.0) / 100 * future_total
    current_cash = current.get(CASH_GROUP, 0.0)
    reserve_cash = min(amount_pln, max(0.0, desired_cash - current_cash))
    investable = max(0.0, amount_pln - reserve_cash)

    gaps = []
    for category, target_pct in targets.items():
        if category == CASH_GROUP:
            continue
        desired = target_pct / 100 * future_total
        gap = max(0.0, desired - current.get(category, 0.0))
        if gap > 0.01:
            candidates = [
                {"isin": r["isin"], "name": r["name"], "ticker": r["ticker"]}
                for r in conn.execute(
                    "SELECT isin, name, ticker FROM instruments "
                    "WHERE active = 1 AND category = ? ORDER BY name", (category,)
                )
            ]
            gaps.append({
                "category": category,
                "target_pct": target_pct,
                "current_pln": round(current.get(category, 0.0), 2),
                "gap_pln": gap,
                "candidates": candidates,
            })

    gap_total = sum(g["gap_pln"] for g in gaps)
    scale = min(1.0, investable / gap_total) if gap_total else 0.0
    recommendations = []
    allocated = 0.0
    for index, gap in enumerate(sorted(gaps, key=lambda g: g["gap_pln"], reverse=True), start=1):
        amount = round(gap["gap_pln"] * scale, 2)
        if amount <= 0:
            continue
        allocated += amount
        recommendations.append({
            **gap,
            "amount_pln": amount,
            "priority": index,
            "future_pln": round(gap["current_pln"] + amount, 2),
        })

    rounding_remainder = round(investable - allocated, 2)
    if recommendations and abs(rounding_remainder) <= 0.05:
        recommendations[-1]["amount_pln"] = round(
            recommendations[-1]["amount_pln"] + rounding_remainder, 2
        )
        recommendations[-1]["future_pln"] = round(
            recommendations[-1]["future_pln"] + rounding_remainder, 2
        )
        allocated += rounding_remainder

    unallocated = round(amount_pln - reserve_cash - allocated, 2)
    return {
        "contribution_pln": round(amount_pln, 2),
        "current_total_pln": allocation["total_pln"],
        "future_total_pln": round(future_total, 2),
        "reserved_cash_pln": round(reserve_cash + max(0.0, unallocated), 2),
        "invested_pln": round(allocated, 2),
        "recommendations": recommendations,
        "note": "Plan nie zakłada sprzedaży ani zmian istniejących pozycji.",
    }
