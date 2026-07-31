"""Diagnostyka kompletności i spójności danych portfela."""
from __future__ import annotations

import hashlib
import sqlite3
from datetime import date

from . import portfolio as portfolio_mod


def _age(iso_date: str | None) -> int | None:
    if not iso_date:
        return None
    try:
        return (date.today() - date.fromisoformat(iso_date[:10])).days
    except ValueError:
        return None


def inspect(conn: sqlite3.Connection, stale_after_days: int = 4) -> dict:
    valued = portfolio_mod.value_positions(conn)
    held = {p["isin"]: p for p in valued["positions"]}
    instruments = [dict(r) for r in conn.execute(
        "SELECT * FROM instruments WHERE active = 1 ORDER BY name"
    )]
    issues: list[dict] = []

    def add(code: str, severity: str, title: str, detail: str, *, entity: str | None = None,
            action: str | None = None) -> None:
        issues.append({
            "code": code,
            "severity": severity,
            "title": title,
            "detail": detail,
            "entity": entity,
            "action": action,
        })

    latest_price_date = None
    currencies: set[str] = set()
    for inst in instruments:
        isin = inst["isin"]
        position = held.get(isin)
        if inst["needs_config"] or not inst["ticker"] or not inst["currency"]:
            add(
                "instrument_config", "error" if position else "warning",
                "Instrument wymaga konfiguracji",
                f"{inst['name']} nie ma kompletnego tickera lub waluty.",
                entity=isin, action="Uzupełnij instrument w sekcji mapowania notowań.",
            )
        if not (inst.get("category") or "").strip():
            add(
                "missing_category", "warning", "Brak klasy aktywów",
                f"{inst['name']} nie jest przypisany do kategorii.",
                entity=isin, action="Przypisz kategorię, aby alokacja i analiza były kompletne.",
            )

        price = conn.execute(
            "SELECT date FROM prices WHERE isin = ? ORDER BY date DESC LIMIT 1", (isin,)
        ).fetchone()
        price_date = price["date"] if price else None
        if price_date and (latest_price_date is None or price_date > latest_price_date):
            latest_price_date = price_date
        if position and price_date is None:
            add(
                "missing_price", "error", "Brak wyceny pozycji",
                f"{inst['name']} ma otwartą pozycję, ale nie ma żadnej ceny.",
                entity=isin, action="Odśwież wyceny lub uzupełnij historię notowań.",
            )
        elif position and (_age(price_date) or 0) > stale_after_days:
            add(
                "stale_price", "warning", "Nieaktualna wycena",
                f"Ostatnia cena {inst['name']} pochodzi z {price_date}.",
                entity=isin, action="Odśwież wyceny.",
            )
        if position and inst["currency"] and inst["currency"].upper() != "PLN":
            currencies.add(inst["currency"].upper())

    latest_fx_date = None
    for currency in sorted(currencies):
        row = conn.execute(
            "SELECT date FROM fx_rates WHERE currency = ? ORDER BY date DESC LIMIT 1", (currency,)
        ).fetchone()
        fx_date = row["date"] if row else None
        if fx_date and (latest_fx_date is None or fx_date > latest_fx_date):
            latest_fx_date = fx_date
        if fx_date is None:
            add(
                "missing_fx", "error", "Brak kursu walutowego",
                f"Brakuje kursu {currency}/PLN potrzebnego do wyceny.",
                entity=currency, action="Odśwież wyceny i kursy NBP.",
            )
        elif (_age(fx_date) or 0) > stale_after_days:
            add(
                "stale_fx", "warning", "Nieaktualny kurs walutowy",
                f"Ostatni kurs {currency}/PLN pochodzi z {fx_date}.",
                entity=currency, action="Odśwież wyceny i kursy NBP.",
            )

    holdings: dict[str, float] = {}
    oversells = 0
    transactions = conn.execute(
        "SELECT * FROM transactions ORDER BY ts ASC, id ASC"
    ).fetchall()
    missing_trade_cash = 0
    for tx in transactions:
        qty = float(tx["quantity"])
        if qty <= 0 or float(tx["price_pln"]) < 0:
            add(
                "invalid_transaction", "error", "Nieprawidłowa transakcja",
                f"Transakcja #{tx['id']} ma nieprawidłową ilość lub cenę.",
                entity=str(tx["id"]), action="Edytuj transakcję.",
            )
        current = holdings.get(tx["isin"], 0.0)
        holdings[tx["isin"]] = current + qty if tx["type"] == "BUY" else current - qty
        if holdings[tx["isin"]] < -1e-9:
            oversells += 1

        cash_hash = hashlib.sha1(f"cash|{tx['import_hash']}".encode()).hexdigest()
        expected = -abs(tx["value_pln"]) if tx["type"] == "BUY" else abs(tx["value_pln"])
        cash_row = conn.execute(
            "SELECT amount_pln FROM cash_flows WHERE import_hash = ?", (cash_hash,)
        ).fetchone()
        if cash_row is None or abs(float(cash_row["amount_pln"]) - expected) > 0.01:
            missing_trade_cash += 1

    if oversells:
        add(
            "oversell", "error", "Sprzedaż przekracza stan pozycji",
            f"Wykryto {oversells} operacji prowadzących do ujemnej liczby jednostek.",
            action="Sprawdź kolejność, daty i ilości transakcji sprzedaży.",
        )
    if missing_trade_cash:
        add(
            "cash_reconciliation", "error", "Niespójna księga gotówki",
            f"{missing_trade_cash} transakcji nie ma poprawnego ruchu gotówkowego.",
            action="Sprawdź ręcznie edytowane lub starsze transakcje.",
        )

    target_sum = conn.execute(
        "SELECT COALESCE(SUM(weight_pct), 0) AS total FROM target_allocation"
    ).fetchone()["total"]
    if target_sum and abs(float(target_sum) - 100.0) >= 0.01:
        add(
            "allocation_target", "warning", "Niepełny model alokacji",
            f"Wagi docelowe sumują się do {float(target_sum):.1f}%, zamiast 100%.",
            action="Popraw wagi na ekranie Alokacja.",
        )

    severity_order = {"error": 0, "warning": 1, "info": 2}
    issues.sort(key=lambda item: (severity_order[item["severity"]], item["title"], item["entity"] or ""))
    errors = sum(i["severity"] == "error" for i in issues)
    warnings = sum(i["severity"] == "warning" for i in issues)
    status = "error" if errors else "warning" if warnings else "good"
    return {
        "status": status,
        "checked_at": date.today().isoformat(),
        "summary": {"errors": errors, "warnings": warnings, "issues": len(issues)},
        "stats": {
            "instruments": len(instruments),
            "open_positions": len(held),
            "transactions": len(transactions),
            "latest_price_date": latest_price_date,
            "latest_fx_date": latest_fx_date,
            "fully_valued": valued["totals"]["fully_valued"],
        },
        "issues": issues,
    }
