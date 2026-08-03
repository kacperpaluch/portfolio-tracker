"""Import historii transakcji z CSV i potwierdzeń PDF biur maklerskich.

Obsługiwane formaty:
- GPW „historia PW” (10 kolumn, w tym ISIN),
- eMAKLER „Transakcje bieżące” (preambuła i 9-kolumnowa tabela bez ISIN-u).
- mBank „Potwierdzenie wykonania zleceń” (PDF z tekstową warstwą tabel).
"""
from __future__ import annotations

import hashlib
import io
import re
import sqlite3
import unicodedata
from datetime import datetime

from . import cash as cash_mod
from .instruments import SEED, ensure_instrument, resolve_broker_instrument

ENCODING = "cp1250"
# Kolejność kolumn (po pozycji — nagłówek bywa zniekształcony przez kodowanie):
# data; papier; isin; ilość; [K/S]; cena; wartość; prowizja; po prowizji; waluta
LEGACY_COL_COUNT = 10
EMAKLER_HEADER = ("czas transakcji", "papier", "giełda", "k/s", "liczba", "kurs", "waluta", "wartość", "waluta")
PDF_FORMAT = "mbank_confirmation_pdf"
PDF_REQUIRED_HEADERS = {
    "RYNEK", "WALOR", "OFERTA", "LICZBA", "CENAREALIZACJI", "WARTOSC",
    "PROWIZJA", "KURSWALUTY", "CZASZAWARCIATRANSAKCJI", "DATAROZLICZENIA",
}
ISIN_RE = re.compile(r"\b[A-Z]{2}[A-Z0-9]{9}[0-9]\b")


class BrokerMappingRequired(ValueError):
    """Import zawiera symbole brokera, których nie da się jeszcze przypisać do ISIN-u."""

    def __init__(self, instruments: list[dict]):
        self.instruments = instruments
        details = ", ".join(
            f"{item['symbol']} ({item['exchange']})" for item in instruments
        )
        super().__init__(f"Brak mapowania ISIN dla: {details}")


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


def _normalise_header(raw: str | None) -> str:
    text = unicodedata.normalize("NFKD", raw or "")
    return re.sub(r"[^A-Z0-9]", "", text.encode("ascii", "ignore").decode().upper())


def _pdf_amount(raw: str | None, field: str) -> tuple[float, str | None]:
    match = re.fullmatch(r"\s*([0-9\s.,]+)\s*([A-Z]{3})?\s*", raw or "")
    if match is None:
        raise ValueError(f"Nieprawidłowa wartość pola {field} w PDF: {raw or 'brak'}")
    number = match.group(1).replace(" ", "")
    if "," in number and "." in number:
        if number.rfind(",") > number.rfind("."):
            number = number.replace(".", "").replace(",", ".")
        else:
            number = number.replace(",", "")
    else:
        number = number.replace(",", ".")
    return float(number), match.group(2)


def _pdf_transaction_tables(content: bytes) -> list[tuple[list[list[str | None]], str | None]]:
    try:
        import pdfplumber
    except ImportError as exc:  # pragma: no cover - zależność obrazu produkcyjnego
        raise ValueError("Obsługa PDF jest niedostępna na serwerze") from exc

    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            result: list[tuple[list[list[str | None]], str | None]] = []
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                order_ids = iter(re.findall(
                    r"^\s*Zlecenie\s*numer\s*(\d+)", page_text, re.IGNORECASE | re.MULTILINE,
                ))
                current_order_id: str | None = None
                for table in page.extract_tables():
                    if not table or not table[0]:
                        continue
                    headers = {_normalise_header(cell) for cell in table[0]}
                    if "LIMITZLECENIA" in headers:
                        current_order_id = next(order_ids, current_order_id)
                    if PDF_REQUIRED_HEADERS.issubset(headers):
                        if current_order_id is None:
                            current_order_id = next(order_ids, None)
                        result.append((table, current_order_id))
                        current_order_id = None
            return result
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("Nie udało się odczytać tabel z pliku PDF") from exc


def _parse_mbank_pdf(content: bytes) -> list[dict]:
    """Parsuje cyfrowe potwierdzenie wykonania zleceń mBanku (bez OCR)."""
    rows: list[dict] = []
    tables = _pdf_transaction_tables(content)
    if not tables:
        raise ValueError("PDF nie zawiera tabeli „Transakcje do zlecenia” mBanku")

    for table, order_id in tables:
        header_indexes = {_normalise_header(value): index for index, value in enumerate(table[0])}
        for values in table[1:]:
            if not values or _normalise_header(values[0]) == "RAZEM":
                continue

            def field(header: str) -> str:
                index = header_indexes[header]
                return (values[index] or "").strip() if index < len(values) else ""

            isin_match = ISIN_RE.search(field("WALOR").replace("\n", " "))
            if isin_match is None:
                raise ValueError("Brak poprawnego ISIN-u w tabeli transakcji PDF")
            isin = isin_match.group(0)
            offer = _normalise_header(field("OFERTA"))
            tx_type = {"KUPNO": "BUY", "K": "BUY", "SPRZEDAZ": "SELL", "S": "SELL"}.get(offer)
            if tx_type is None:
                raise ValueError(f"Nieznany typ transakcji w PDF: {field('OFERTA')}")

            quantity, _ = _pdf_amount(field("LICZBA"), "liczba")
            native_price, native_currency = _pdf_amount(field("CENAREALIZACJI"), "cena realizacji")
            value_pln, value_currency = _pdf_amount(field("WARTOSC"), "wartość")
            commission_pln, commission_currency = _pdf_amount(field("PROWIZJA"), "prowizja")
            if value_currency != "PLN" or commission_currency not in {None, "PLN"}:
                raise ValueError("Wartość lub prowizja transakcji PDF nie jest w PLN")
            if quantity <= 0 or native_price <= 0 or value_pln <= 0 or commission_pln < 0:
                raise ValueError("Liczba, cena i wartość w PDF muszą być dodatnie, a prowizja nieujemna")

            raw_ts = re.sub(r"\s+", " ", field("CZASZAWARCIATRANSAKCJI")).strip()
            try:
                ts = datetime.strptime(raw_ts, "%Y-%m-%d %H:%M:%S.%f")
            except ValueError:
                try:
                    ts = datetime.strptime(raw_ts, "%Y-%m-%d %H:%M:%S")
                except ValueError as exc:
                    raise ValueError(f"Nieprawidłowy czas transakcji w PDF: {raw_ts}") from exc

            fx_raw = field("KURSWALUTY")
            fx_rate = _pdf_amount(fx_raw, "kurs waluty")[0] if fx_raw else (1.0 if native_currency == "PLN" else None)
            settlement_date = field("DATAROZLICZENIA").rstrip("*").strip()
            try:
                datetime.strptime(settlement_date, "%Y-%m-%d")
            except ValueError as exc:
                raise ValueError(f"Nieprawidłowa data rozliczenia w PDF: {settlement_date}") from exc

            raw_name = ISIN_RE.sub("", field("WALOR").replace("\n", " "))
            raw_name = re.sub(r"\s*[–—-]\s*$", "", raw_name).strip()
            name = SEED.get(isin, {}).get("name") or raw_name or isin
            price_pln = round(value_pln / quantity, 4)
            rows.append({
                "ts": ts.isoformat(),
                "isin": isin,
                "name": name,
                "type": tx_type,
                "quantity": quantity,
                "price_pln": price_pln,
                "value_pln": value_pln,
                "commission_pln": commission_pln,
                "native_price": native_price,
                "native_currency": native_currency,
                "fx_rate": fx_rate,
                "settlement_date": settlement_date,
                "market": field("RYNEK"),
                "broker_order_id": order_id,
                "source_format": PDF_FORMAT,
                "import_hash": _transaction_hash(ts, isin, tx_type, quantity, price_pln),
            })
    if not rows:
        raise ValueError("PDF nie zawiera wykonanych transakcji")
    return rows


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


def _parse_emakler(text: str, conn: sqlite3.Connection | None = None) -> list[dict]:
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
    unresolved: dict[tuple[str, str], dict] = {}
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
        isin = resolve_broker_instrument("emakler", symbol, exchange, conn)
        if isin is None:
            key = (symbol.strip().upper(), exchange.strip().upper())
            unresolved[key] = {
                "broker": "emakler",
                "symbol": symbol,
                "exchange": exchange,
                "currency": parts[6].upper(),
            }
            continue
        instrument = None
        if conn is not None:
            instrument = conn.execute(
                "SELECT name, currency FROM instruments WHERE isin = ?", (isin,)
            ).fetchone()
        expected_currency = (
            (instrument["currency"] if instrument else None)
            or SEED.get(isin, {}).get("currency")
        )
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
                "name": (
                    (instrument["name"] if instrument else None)
                    or SEED.get(isin, {}).get("name", symbol)
                ),
                "type": tx_type,
                "quantity": quantity,
                "price_pln": price_pln,
                "value_pln": value_pln,
                "commission_pln": 0.0,
                "import_hash": _transaction_hash(ts, isin, tx_type, quantity, price_pln),
            }
        )

    if unresolved:
        raise BrokerMappingRequired([unresolved[key] for key in sorted(unresolved)])
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


def detect_import_format(content: bytes) -> str:
    if content.lstrip().startswith(b"%PDF-"):
        return PDF_FORMAT
    return detect_csv_format(content)


def parse_import(content: bytes) -> list[dict]:
    import_format = detect_import_format(content)
    return _parse_mbank_pdf(content) if import_format == PDF_FORMAT else parse_csv(content)


def import_transactions(conn: sqlite3.Connection, content: bytes) -> dict:
    """Importuje transakcje do bazy. Idempotentny — duplikaty (import_hash) pomijane."""
    import_format = detect_import_format(content)
    if import_format == PDF_FORMAT:
        rows = _parse_mbank_pdf(content)
    elif import_format == "emakler_current":
        rows = _parse_emakler(_decode(content), conn)
    else:
        rows = _parse_legacy(_decode(content))
    imported = 0
    skipped = 0
    enriched = 0
    new_instruments: set[str] = set()

    for r in rows:
        for key in (
            "native_price", "native_currency", "fx_rate", "settlement_date", "market",
            "broker_order_id", "source_format",
        ):
            r.setdefault(key, None)
        r["source_format"] = r["source_format"] or import_format
        before = conn.execute(
            "SELECT 1 FROM instruments WHERE isin = ?", (r["isin"],)
        ).fetchone()
        ensure_instrument(conn, r["isin"], r["name"])
        if before is None:
            new_instruments.add(r["isin"])

        cur = conn.execute(
            """
            INSERT OR IGNORE INTO transactions
                (ts, isin, type, quantity, price_pln, value_pln, commission_pln,
                 native_price, native_currency, fx_rate, settlement_date, market,
                 broker_order_id, source_format, import_hash)
            VALUES (:ts, :isin, :type, :quantity, :price_pln, :value_pln, :commission_pln,
                    :native_price, :native_currency, :fx_rate, :settlement_date, :market,
                    :broker_order_id, :source_format, :import_hash)
            """,
            r,
        )
        if cur.rowcount == 1:
            imported += 1
        else:
            skipped += 1
            if import_format == PDF_FORMAT:
                updated = conn.execute(
                    """
                    UPDATE transactions
                       SET commission_pln = :commission_pln,
                           native_price = COALESCE(:native_price, native_price),
                           native_currency = COALESCE(:native_currency, native_currency),
                           fx_rate = COALESCE(:fx_rate, fx_rate),
                           settlement_date = COALESCE(:settlement_date, settlement_date),
                           market = COALESCE(:market, market),
                           broker_order_id = COALESCE(:broker_order_id, broker_order_id),
                           source_format = :source_format
                     WHERE import_hash = :import_hash
                       AND (native_price IS NULL OR source_format != :source_format)
                    """,
                    r,
                )
                enriched += updated.rowcount

        # Wpływ transakcji na gotówkę (idempotentny po import_hash).
        cash_mod.record_trade_cash(conn, r["ts"], r["type"], r["value_pln"], r["import_hash"])

    conn.commit()
    return {
        "format": import_format,
        "parsed": len(rows),
        "imported": imported,
        "skipped_duplicates": skipped,
        "enriched": enriched,
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
