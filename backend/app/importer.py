"""Import historii transakcji z CSV biura maklerskiego (format GPW „historia PW").

Cechy pliku:
- kodowanie CP1250 (Windows-1250),
- separator ';', liczby z przecinkiem dziesiętnym,
- data 'DD.MM.YYYY HH:MM:SS',
- kolumna typu: 'K' = kupno (BUY), 'S' = sprzedaż (SELL).
"""
from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime

from . import cash as cash_mod
from .instruments import ensure_instrument

ENCODING = "cp1250"
# Kolejność kolumn (po pozycji — nagłówek bywa zniekształcony przez kodowanie):
# data; papier; isin; ilość; [K/S]; cena; wartość; prowizja; po prowizji; waluta
COL_COUNT = 10


def parse_number(raw: str) -> float:
    """'34,3375' / '1 234,56' -> float."""
    return float(raw.replace("\xa0", "").replace(" ", "").replace(",", "."))


def parse_csv(content: bytes) -> list[dict]:
    """Parsuje surowe bajty CSV do listy znormalizowanych transakcji.

    Funkcja czysta (bez DB) — łatwa do testowania. Pomija nagłówek i puste linie.
    """
    text = content.decode(ENCODING)
    rows: list[dict] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(";")
        if len(parts) < COL_COUNT:
            continue
        # Pomiń wiersz nagłówka (pierwsza kolumna nie jest datą).
        try:
            ts = datetime.strptime(parts[0].strip(), "%d.%m.%Y %H:%M:%S")
        except ValueError:
            continue

        kind = parts[4].strip().upper()
        tx_type = {"K": "BUY", "S": "SELL"}.get(kind)
        if tx_type is None:
            continue

        isin = parts[2].strip()
        name = parts[1].strip()
        quantity = parse_number(parts[3])
        price_pln = parse_number(parts[5])
        value_pln = parse_number(parts[6])
        commission_pln = parse_number(parts[7]) if parts[7].strip() else 0.0

        import_hash = hashlib.sha1(
            f"{ts.isoformat()}|{isin}|{tx_type}|{quantity}|{price_pln}".encode()
        ).hexdigest()

        rows.append(
            {
                "ts": ts.isoformat(),
                "isin": isin,
                "name": name,
                "type": tx_type,
                "quantity": quantity,
                "price_pln": price_pln,
                "value_pln": value_pln,
                "commission_pln": commission_pln,
                "import_hash": import_hash,
            }
        )
    return rows


def import_transactions(conn: sqlite3.Connection, content: bytes) -> dict:
    """Importuje transakcje do bazy. Idempotentny — duplikaty (import_hash) pomijane."""
    rows = parse_csv(content)
    imported = 0
    skipped = 0
    new_instruments: set[str] = set()

    for r in rows:
        before = conn.execute(
            "SELECT 1 FROM instruments WHERE isin = ?", (r["isin"],)
        ).fetchone()
        ensure_instrument(conn, r["isin"], r["name"])
        if before is None:
            new_instruments.add(r["isin"])

        cur = conn.execute(
            """
            INSERT OR IGNORE INTO transactions
                (ts, isin, type, quantity, price_pln, value_pln, commission_pln, import_hash)
            VALUES (:ts, :isin, :type, :quantity, :price_pln, :value_pln, :commission_pln, :import_hash)
            """,
            r,
        )
        if cur.rowcount == 1:
            imported += 1
        else:
            skipped += 1

        # Wpływ transakcji na gotówkę (idempotentny po import_hash).
        cash_mod.record_trade_cash(conn, r["ts"], r["type"], r["value_pln"], r["import_hash"])

    conn.commit()
    return {
        "parsed": len(rows),
        "imported": imported,
        "skipped_duplicates": skipped,
        "new_instruments": sorted(new_instruments),
    }


def _normalize_ts(ts: str) -> str:
    """Akceptuje datę, datetime-local lub pełny ISO; zwraca ISO 8601."""
    ts = ts.strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(ts, fmt).isoformat()
        except ValueError:
            continue
    return ts


def add_transaction(
    conn: sqlite3.Connection,
    *,
    ts: str,
    isin: str,
    name: str | None,
    tx_type: str,
    quantity: float,
    price_pln: float,
    commission_pln: float = 0.0,
) -> dict:
    """Dodaje pojedynczą transakcję ręcznie. Idempotentne (ten sam hash co import)."""
    ts = _normalize_ts(ts)
    isin = isin.strip()
    tx_type = tx_type.upper()
    if tx_type not in ("BUY", "SELL"):
        raise ValueError("type musi być 'BUY' lub 'SELL'")
    value_pln = round(quantity * price_pln, 2)
    import_hash = hashlib.sha1(
        f"{ts}|{isin}|{tx_type}|{quantity}|{price_pln}".encode()
    ).hexdigest()

    ensure_instrument(conn, isin, (name or isin).strip())
    cur = conn.execute(
        """
        INSERT OR IGNORE INTO transactions
            (ts, isin, type, quantity, price_pln, value_pln, commission_pln, import_hash)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (ts, isin, tx_type, quantity, price_pln, value_pln, commission_pln, import_hash),
    )
    if cur.rowcount == 1:
        cash_mod.record_trade_cash(conn, ts, tx_type, value_pln, import_hash)
        conn.commit()
        return {"created": True, "id": cur.lastrowid}
    conn.commit()
    return {"created": False, "reason": "duplicate"}


def delete_transaction(conn: sqlite3.Connection, tx_id: int) -> bool:
    """Usuwa transakcję i powiązany przepływ gotówki."""
    row = conn.execute("SELECT import_hash FROM transactions WHERE id = ?", (tx_id,)).fetchone()
    if row is None:
        return False
    conn.execute("DELETE FROM transactions WHERE id = ?", (tx_id,))
    cash_mod.remove_trade_cash(conn, row["import_hash"])
    conn.commit()
    return True
