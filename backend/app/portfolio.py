"""Agregacja pozycji (średni koszt), wycena bieżąca i P/L w PLN."""
from __future__ import annotations

import sqlite3

from . import cash as cash_mod
from . import fx, prices


def compute_positions(conn: sqlite3.Connection) -> tuple[list[dict], float]:
    """Liczy pozycje netto metodą średniego kosztu, chronologicznie po transakcjach.

    Zwraca (lista_pozycji, zrealizowany_zysk_PLN). Zrealizowany zysk akumuluje się
    przy każdej sprzedaży jako (przychód − średni_koszt × sprzedana_ilość).
    """
    instruments = {r["isin"]: dict(r) for r in conn.execute("SELECT * FROM instruments")}
    txs = conn.execute(
        "SELECT isin, type, quantity, value_pln FROM transactions ORDER BY ts ASC"
    ).fetchall()

    state: dict[str, dict] = {}
    realized_pl = 0.0
    for t in txs:
        s = state.setdefault(t["isin"], {"qty": 0.0, "cost": 0.0})
        if t["type"] == "BUY":
            s["qty"] += t["quantity"]
            s["cost"] += t["value_pln"]
        else:  # SELL — redukcja kosztu po średniej cenie + zrealizowany zysk
            avg = (s["cost"] / s["qty"]) if s["qty"] else 0.0
            realized_pl += t["value_pln"] - avg * t["quantity"]
            s["qty"] -= t["quantity"]
            s["cost"] -= avg * t["quantity"]
            if s["qty"] <= 1e-9:
                s["qty"] = 0.0
                s["cost"] = 0.0

    positions = []
    for isin, s in state.items():
        if s["qty"] <= 1e-9:
            continue
        inst = instruments.get(isin, {})
        positions.append(
            {
                "isin": isin,
                "name": inst.get("name", isin),
                "currency": inst.get("currency"),
                "ticker": inst.get("ticker"),
                "category": inst.get("category"),
                "needs_config": bool(inst.get("needs_config", 1)),
                "quantity": round(s["qty"], 6),
                "cost_pln": round(s["cost"], 2),
                "avg_cost_pln": round(s["cost"] / s["qty"], 4),
            }
        )
    positions.sort(key=lambda p: p["name"])
    return positions, round(realized_pl, 2)


def value_positions(conn: sqlite3.Connection, refresh: bool = False) -> dict:
    """Wzbogaca pozycje o bieżącą wycenę i P/L w PLN.

    refresh=True wymusza pobranie świeżych cen i kursów z sieci; w przeciwnym razie
    używa najnowszych wartości z cache.
    """
    positions, realized_pl = compute_positions(conn)
    instruments = {r["isin"]: dict(r) for r in conn.execute("SELECT * FROM instruments")}

    total_cost = 0.0
    total_value = 0.0
    valued_all = True

    for p in positions:
        total_cost += p["cost_pln"]
        inst = instruments.get(p["isin"], {})

        price_info = None
        if refresh:
            price_info = prices.fetch_latest(conn, inst)
        if price_info is None:
            price_info = prices.latest_cached_price(conn, p["isin"])

        if price_info is None or not p["currency"]:
            # Brak wyceny (np. nieskonfigurowany ticker) — pokazujemy tylko koszt.
            p.update(price=None, price_date=None, fx_rate=None, value_pln=None,
                     pl_pln=None, pl_pct=None)
            valued_all = False
            continue

        price_date, price = price_info
        try:
            _, rate = fx.get_rate(conn, p["currency"]) if refresh else _cached_fx(conn, p["currency"])
        except Exception:
            rate = None
        if rate is None:
            p.update(price=price, price_date=price_date, fx_rate=None, value_pln=None,
                     pl_pln=None, pl_pct=None)
            valued_all = False
            continue

        value = price * p["quantity"] * rate
        pl = value - p["cost_pln"]
        p.update(
            price=round(price, 4),
            price_date=price_date,
            fx_rate=round(rate, 4),
            value_pln=round(value, 2),
            pl_pln=round(pl, 2),
            pl_pct=round(pl / p["cost_pln"] * 100, 2) if p["cost_pln"] else None,
        )
        total_value += value

    unrealized_pl = total_value - total_cost
    cash_pln = cash_mod.balance(conn)
    net_deposits = cash_mod.deposits_total(conn)
    # Zysk całkowity = niezrealizowany (otwarte pozycje) + zrealizowany (sprzedaże).
    total_pl = unrealized_pl + realized_pl
    # Wartość całego portfela = wycena ETF + gotówka.
    portfolio_value = total_value + cash_pln
    return {
        "positions": positions,
        "totals": {
            "cost_pln": round(total_cost, 2),
            "value_pln": round(total_value, 2) if valued_all else None,
            "value_pln_partial": round(total_value, 2),
            # P/L otwartych pozycji (niezrealizowany):
            "unrealized_pl_pln": round(unrealized_pl, 2) if valued_all else None,
            "pl_pln": round(unrealized_pl, 2) if valued_all else None,
            "pl_pct": round(unrealized_pl / total_cost * 100, 2) if valued_all and total_cost else None,
            # Zrealizowany i całkowity:
            "realized_pl_pln": round(realized_pl, 2),
            "total_pl_pln": round(total_pl, 2) if valued_all else None,
            # Gotówka i wartość całego portfela:
            "cash_pln": cash_pln,
            "net_deposits_pln": net_deposits,
            "portfolio_value_pln": round(portfolio_value, 2) if valued_all else None,
            "total_return_pct": round(total_pl / net_deposits * 100, 2) if valued_all and net_deposits else (
                round(total_pl / total_cost * 100, 2) if valued_all and total_cost else None
            ),
            "fully_valued": valued_all,
        },
    }


def _cached_fx(conn: sqlite3.Connection, currency: str) -> tuple[str, float | None]:
    if currency.upper() == "PLN":
        return "", 1.0
    row = conn.execute(
        "SELECT date, rate_to_pln FROM fx_rates WHERE currency = ? ORDER BY date DESC LIMIT 1",
        (currency.upper(),),
    ).fetchone()
    return (row[0], row[1]) if row else ("", None)
