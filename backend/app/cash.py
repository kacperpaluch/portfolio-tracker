"""Księga gotówki: saldo, wpłaty/wypłaty (ręczne) oraz przepływy z transakcji."""
from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime


def has_external(conn: sqlite3.Connection) -> bool:
    """Czy użytkownik śledzi gotówkę (dodał choć jedną wpłatę/wypłatę)."""
    row = conn.execute(
        "SELECT 1 FROM cash_flows WHERE kind IN ('deposit', 'withdrawal') LIMIT 1"
    ).fetchone()
    return row is not None


def balance(conn: sqlite3.Connection) -> float:
    """Saldo gotówki = suma wszystkich przepływów. Gdy brak wpłat (konto gotówkowe
    nieaktywne) zwraca 0, żeby nie pokazywać mylącego ujemnego salda z samych zakupów."""
    if not has_external(conn):
        return 0.0
    row = conn.execute("SELECT COALESCE(SUM(amount_pln), 0) FROM cash_flows").fetchone()
    return round(row[0], 2)


def deposits_total(conn: sqlite3.Connection) -> float:
    """Suma netto wpłat zewnętrznych (wpłaty − wypłaty)."""
    row = conn.execute(
        "SELECT COALESCE(SUM(amount_pln), 0) FROM cash_flows WHERE kind IN ('deposit', 'withdrawal')"
    ).fetchone()
    return round(row[0], 2)


def list_external(conn: sqlite3.Connection) -> list[dict]:
    """Tylko wpłaty/wypłaty (do ręcznej edycji w UI)."""
    rows = conn.execute(
        "SELECT * FROM cash_flows WHERE kind IN ('deposit', 'withdrawal') ORDER BY ts DESC, id DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def add_flow(conn: sqlite3.Connection, ts: str, kind: str, amount: float, note: str | None = None) -> dict:
    """Dodaje ręczną wpłatę/wypłatę. amount > 0; znak ustalany przez kind."""
    kind = kind.lower()
    if kind not in ("deposit", "withdrawal"):
        raise ValueError("kind musi być 'deposit' lub 'withdrawal'")
    # Normalizacja daty (akceptuje 'YYYY-MM-DD' lub pełny ISO).
    ts = normalize_ts(ts)
    signed = abs(amount) if kind == "deposit" else -abs(amount)
    cur = conn.execute(
        "INSERT INTO cash_flows (ts, kind, amount_pln, note, import_hash) VALUES (?, ?, ?, ?, NULL)",
        (ts, kind, signed, note),
    )
    conn.commit()
    return dict(conn.execute("SELECT * FROM cash_flows WHERE id = ?", (cur.lastrowid,)).fetchone())


def delete_flow(conn: sqlite3.Connection, flow_id: int) -> bool:
    cur = conn.execute(
        "DELETE FROM cash_flows WHERE id = ? AND kind IN ('deposit', 'withdrawal')", (flow_id,)
    )
    conn.commit()
    return cur.rowcount > 0


def record_trade_cash(conn: sqlite3.Connection, ts: str, tx_type: str, value_pln: float, import_hash: str) -> None:
    """Zapisuje wpływ transakcji na gotówkę (kupno −, sprzedaż +). Idempotentne."""
    kind = "buy" if tx_type == "BUY" else "sell"
    signed = -abs(value_pln) if tx_type == "BUY" else abs(value_pln)
    h = hashlib.sha1(f"cash|{import_hash}".encode()).hexdigest()
    conn.execute(
        "INSERT OR IGNORE INTO cash_flows (ts, kind, amount_pln, note, import_hash) VALUES (?, ?, ?, NULL, ?)",
        (ts, kind, signed, h),
    )


def remove_trade_cash(conn: sqlite3.Connection, import_hash: str) -> None:
    """Usuwa przepływ gotówki powiązany z transakcją (po jej import_hash)."""
    h = hashlib.sha1(f"cash|{import_hash}".encode()).hexdigest()
    conn.execute("DELETE FROM cash_flows WHERE import_hash = ?", (h,))


def normalize_ts(ts: str) -> str:
    """Akceptuje datę, datetime-local lub pełny ISO; zwraca ISO 8601."""
    ts = ts.strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(ts, fmt).isoformat()
        except ValueError:
            continue
    return ts
