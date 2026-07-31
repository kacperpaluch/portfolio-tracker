"""Import historii transakcji z CSV różnych biur maklerskich.

Obsługiwane formaty:
- GPW „historia PW” (10 kolumn, w tym ISIN),
- eMAKLER „Transakcje bieżące” (preambuła i 9-kolumnowa tabela bez ISIN-u).
"""
from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime

from . import cash as cash_mod
from .instruments import SEED, ensure_instrument, resolve_broker_instrument

ENCODING = "cp1250"
# Kolejność kolumn (po pozycji — nagłówek bywa zniekształcony przez kodowanie):
# data; papier; isin; ilość; [K/S]; cena; wartość; prowizja; po prowizji; waluta
LEGACY_COL_COUNT = 10
EMAKLER_HEADER = ("czas transakcji", "papier", "giełda", "k/s", "liczba", "kurs", "waluta", "wartość", "waluta")


def parse_number(raw: str) -> float:
    """'34,3375' / '1 234,56' -> float."""
    return float(raw.replace("\xa0", "").replace(" ", "").replace(",", "."))


def _decode(content: bytes) -> str:
    """Dekoduje eksporty UTF-8 lub Windows-1250."""
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return content.decode(ENCODING)


def _transaction_hash(ts: datetime, isin: str, tx_type: str, quantity: float, price_pln: float) -> str:
    return hashlib.sha1(
        f"{ts.isoformat()}|{isin}|{tx_type}|{quantity}|{price_pln}".encode()
    ).hexdigest()


def _parse_legacy(text: str) -> list[dict]:
    """Parser dotychczasowego eksportu „historia PW”."""
    rows: list[dict] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(";")
        if len(parts) < LEGACY_COL_COUNT:
            continue
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
                "import_hash": _transaction_hash(ts, isin, tx_type, quantity, price_pln),
            }
        )
    return rows


def _find_emakler_header(lines: list[str]) -> int | None:
    for index, line in enumerate(lines):
        columns = tuple(part.strip().casefold() for part in line.split(";"))
        if columns == EMAKLER_HEADER:
            return index
    return None


def _parse_emakler(text: str) -> list[dict]:
    """Parser eMAKLER „Transakcje bieżące”.

    Raport podaje kurs w walucie notowania, ale pełną wartość rozliczenia w PLN.
    Model aplikacji przechowuje koszt jednostkowy w PLN, więc wyliczamy go jako
    wartość PLN / liczba. Prowizja użytkownika jest zawsze zerowa.
    """
    lines = text.splitlines()
    header_index = _find_emakler_header(lines)
    if header_index is None:
        raise ValueError("Nie znaleziono tabeli transakcji eMAKLER")

    rows: list[dict] = []
    unresolved: set[tuple[str, str]] = set()
    for line_number, line in enumerate(lines[header_index + 1 :], header_index + 2):
        if not line.strip():
            continue
        parts = [part.strip() for part in line.split(";")]
        if len(parts) != len(EMAKLER_HEADER):
            raise ValueError(f"Nieprawidłowy wiersz eMAKLER nr {line_number}: oczekiwano 9 kolumn")

        try:
            ts = datetime.strptime(parts[0], "%d.%m.%Y %H:%M:%S")
            quantity = parse_number(parts[4])
            native_price = parse_number(parts[5])  # walidujemy, ale nie zapisujemy jako PLN
            value_pln = parse_number(parts[7])
        except ValueError as exc:
            raise ValueError(f"Nieprawidłowe dane liczbowe lub data w wierszu eMAKLER nr {line_number}") from exc

        tx_type = {"K": "BUY", "S": "SELL"}.get(parts[3].upper())
        if tx_type is None:
            raise ValueError(f"Nieznany typ transakcji „{parts[3]}” w wierszu eMAKLER nr {line_number}")
        if quantity <= 0:
            raise ValueError(f"Liczba jednostek musi być dodatnia w wierszu eMAKLER nr {line_number}")
        if native_price <= 0 or value_pln <= 0:
            raise ValueError(f"Kurs i wartość muszą być dodatnie w wierszu eMAKLER nr {line_number}")
        if parts[8].upper() != "PLN":
            raise ValueError(f"Wartość transakcji w wierszu eMAKLER nr {line_number} nie jest w PLN")

        symbol, exchange = parts[1], parts[2]
        isin = resolve_broker_instrument("emakler", symbol, exchange)
        if isin is None:
            unresolved.add((symbol, exchange))
            continue
        expected_currency = SEED.get(isin, {}).get("currency")
        if expected_currency and parts[6].upper() != expected_currency:
            raise ValueError(
                f"Waluta kursu w wierszu eMAKLER nr {line_number} to {parts[6]}, "
                f"oczekiwano {expected_currency} dla {symbol}"
            )

        price_pln = round(value_pln / quantity, 4)
        rows.append(
            {
                "ts": ts.isoformat(),
                "isin": isin,
                "name": SEED.get(isin, {}).get("name", symbol),
                "type": tx_type,
                "quantity": quantity,
                "price_pln": price_pln,
                "value_pln": value_pln,
                "commission_pln": 0.0,
                "import_hash": _transaction_hash(ts, isin, tx_type, quantity, price_pln),
            }
        )

    if unresolved:
        details = ", ".join(f"{symbol} ({exchange})" for symbol, exchange in sorted(unresolved))
        raise ValueError(f"Brak mapowania ISIN dla: {details}")
    return rows


def detect_csv_format(content: bytes) -> str:
    """Rozpoznaje format po nagłówku tabeli, niezależnie od preambuły."""
    text = _decode(content)
    if _find_emakler_header(text.splitlines()) is not None:
        return "emakler_current"
    for line in text.splitlines():
        parts = line.split(";")
        if len(parts) >= LEGACY_COL_COUNT and parts[2].strip().casefold() == "isin":
            return "legacy_hispw"
        if len(parts) >= LEGACY_COL_COUNT and parts[4].strip().upper() in {"K", "S"}:
            try:
                datetime.strptime(parts[0].strip(), "%d.%m.%Y %H:%M:%S")
                return "legacy_hispw"
            except ValueError:
                pass
    raise ValueError("Nieobsługiwany format CSV transakcji")


def parse_csv(content: bytes) -> list[dict]:
    """Parsuje surowe bajty CSV do listy znormalizowanych transakcji.

    Funkcja czysta (bez DB) i automatycznie wybiera właściwy parser.
    """
    text = _decode(content)
    csv_format = detect_csv_format(content)
    return _parse_emakler(text) if csv_format == "emakler_current" else _parse_legacy(text)


def import_transactions(conn: sqlite3.Connection, content: bytes) -> dict:
    """Importuje transakcje do bazy. Idempotentny — duplikaty (import_hash) pomijane."""
    csv_format = detect_csv_format(content)
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
        "format": csv_format,
        "parsed": len(rows),
        "imported": imported,
        "skipped_duplicates": skipped,
        "new_instruments": sorted(new_instruments),
    }


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
    note: str | None = None,
) -> dict:
    """Dodaje pojedynczą transakcję ręcznie. Idempotentne (ten sam hash co import)."""
    ts = cash_mod.normalize_ts(ts)
    isin = isin.strip()
    tx_type = tx_type.upper()
    if tx_type not in ("BUY", "SELL"):
        raise ValueError("type musi być 'BUY' lub 'SELL'")
    if quantity <= 0:
        raise ValueError("quantity musi być większe od zera")
    if price_pln < 0:
        raise ValueError("price_pln nie może być ujemne")
    value_pln = round(quantity * price_pln, 2)
    import_hash = hashlib.sha1(
        f"{ts}|{isin}|{tx_type}|{quantity}|{price_pln}".encode()
    ).hexdigest()

    ensure_instrument(conn, isin, (name or isin).strip())
    cur = conn.execute(
        """
        INSERT OR IGNORE INTO transactions
            (ts, isin, type, quantity, price_pln, value_pln, commission_pln, note, import_hash)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            ts, isin, tx_type, quantity, price_pln, value_pln, commission_pln,
            (note or "").strip() or None, import_hash,
        ),
    )
    if cur.rowcount == 1:
        cash_mod.record_trade_cash(conn, ts, tx_type, value_pln, import_hash)
        conn.commit()
        return {"created": True, "id": cur.lastrowid}
    conn.commit()
    return {"created": False, "reason": "duplicate"}


def update_transaction(
    conn: sqlite3.Connection,
    tx_id: int,
    *,
    ts: str,
    isin: str,
    name: str | None,
    tx_type: str,
    quantity: float,
    price_pln: float,
    commission_pln: float = 0.0,
    note: str | None = None,
) -> dict | None:
    """Edytuje transakcję i atomowo odtwarza powiązany ruch gotówkowy."""
    existing = conn.execute(
        "SELECT import_hash FROM transactions WHERE id = ?", (tx_id,)
    ).fetchone()
    if existing is None:
        return None

    ts = cash_mod.normalize_ts(ts)
    isin = isin.strip()
    tx_type = tx_type.upper()
    if tx_type not in ("BUY", "SELL"):
        raise ValueError("type musi być 'BUY' lub 'SELL'")
    if quantity <= 0:
        raise ValueError("quantity musi być większe od zera")
    if price_pln < 0:
        raise ValueError("price_pln nie może być ujemne")
    value_pln = round(quantity * price_pln, 2)
    import_hash = hashlib.sha1(
        f"{ts}|{isin}|{tx_type}|{quantity}|{price_pln}".encode()
    ).hexdigest()
    duplicate = conn.execute(
        "SELECT 1 FROM transactions WHERE import_hash = ? AND id != ?",
        (import_hash, tx_id),
    ).fetchone()
    if duplicate:
        raise ValueError("Taka transakcja już istnieje")

    ensure_instrument(conn, isin, (name or isin).strip())
    cash_mod.remove_trade_cash(conn, existing["import_hash"])
    conn.execute(
        """
        UPDATE transactions
           SET ts = ?, isin = ?, type = ?, quantity = ?, price_pln = ?,
               value_pln = ?, commission_pln = ?, note = ?, import_hash = ?
         WHERE id = ?
        """,
        (
            ts, isin, tx_type, quantity, price_pln, value_pln, commission_pln,
            (note or "").strip() or None, import_hash, tx_id,
        ),
    )
    cash_mod.record_trade_cash(conn, ts, tx_type, value_pln, import_hash)
    conn.commit()
    return dict(conn.execute("SELECT * FROM transactions WHERE id = ?", (tx_id,)).fetchone())


def delete_transaction(conn: sqlite3.Connection, tx_id: int) -> bool:
    """Usuwa transakcję i powiązany przepływ gotówki."""
    row = conn.execute("SELECT import_hash FROM transactions WHERE id = ?", (tx_id,)).fetchone()
    if row is None:
        return False
    conn.execute("DELETE FROM transactions WHERE id = ?", (tx_id,))
    cash_mod.remove_trade_cash(conn, row["import_hash"])
    conn.commit()
    return True
