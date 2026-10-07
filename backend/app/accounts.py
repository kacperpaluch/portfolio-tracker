"""Konta inwestycyjne (IKE, zwykły rachunek…) i szacunek podatku od zysków.

Konto to cecha transakcji i operacji gotówkowej (`account_id`). Widok jednego konta albo
całego portfela daje `db.read_session(account_id)` — moduły analityczne o kontach nie wiedzą.
"""
from __future__ import annotations

import sqlite3

from . import portfolio
from .db import read_session

DEFAULT_ID = 1
BELKA_RATE = 0.19


def list_accounts(conn: sqlite3.Connection) -> list[dict]:
    return [dict(r) for r in conn.execute("SELECT id, name, taxed FROM accounts ORDER BY id")]


def require(conn: sqlite3.Connection, account_id: int | None) -> int:
    """Zwraca istniejące id konta (None → domyślne); nieznane konto to błąd, nie cichy zapis."""
    account_id = DEFAULT_ID if account_id is None else account_id
    if conn.execute("SELECT 1 FROM accounts WHERE id = ?", (account_id,)).fetchone() is None:
        raise ValueError("Nieznane konto")
    return account_id


def save(conn: sqlite3.Connection, account_id: int | None, name: str, taxed: bool) -> dict:
    """Tworzy konto (account_id=None) albo zmienia jego nazwę i opodatkowanie."""
    name = name.strip()
    if not name:
        raise ValueError("Nazwa konta jest wymagana")
    try:
        if account_id is None:
            account_id = conn.execute(
                "INSERT INTO accounts (name, taxed) VALUES (?, ?)", (name, int(taxed))
            ).lastrowid
        else:
            require(conn, account_id)
            conn.execute(
                "UPDATE accounts SET name = ?, taxed = ? WHERE id = ?", (name, int(taxed), account_id)
            )
    except sqlite3.IntegrityError:
        raise ValueError("Konto o takiej nazwie już istnieje")
    conn.commit()
    return dict(conn.execute("SELECT id, name, taxed FROM accounts WHERE id = ?", (account_id,)).fetchone())


def apply_tax(positions: list[dict]) -> float:
    """Dopisuje pozycjom `tax_pln` = 19% zysku przy sprzedaży dziś i zwraca sumę.

    ponytail: szacunek ostrożny — strata jednej pozycji nie pomniejsza podatku innej,
    brak opłaty za wcześniejszy wykup obligacji; koszt średni, a PIT-38 liczy FIFO.
    """
    total = 0.0
    for p in positions:
        p["tax_pln"] = round(BELKA_RATE * max(0.0, p.get("pl_pln") or 0.0), 2)
        total += p["tax_pln"]
    return total


def estimate_tax(accounts: list[dict], account_id: int | None, positions: list[dict]) -> float:
    """Podatek dla widoku: jedno konto (jego `positions`) albo suma kont opodatkowanych.
    W widoku łącznym pozycje są zlane per ISIN, więc każde konto liczymy na własnym widoku."""
    total = 0.0
    for account in accounts:
        if not account["taxed"] or account_id not in (None, account["id"]):
            continue
        if account_id == account["id"]:
            total += apply_tax(positions)
        else:
            with read_session(account["id"]) as conn:
                total += apply_tax(portfolio.value_positions(conn)["positions"])
    return round(total, 2)
