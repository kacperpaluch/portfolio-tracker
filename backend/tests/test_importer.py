"""Testy parsowania i importu CSV/PDF (wyłącznie fikcyjne dane)."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.db import SCHEMA
from app import importer as importer_mod
from app.importer import (
    BrokerMappingRequired,
    detect_csv_format,
    detect_import_format,
    import_transactions,
    parse_csv,
    parse_import,
    parse_number,
)
from app.instruments import save_broker_instrument

# Fikcyjny plik przykładowy commitowany do repo (prawdziwe dane brokera są gitignorowane).
CSV_PATH = Path(__file__).resolve().parent / "sample_hisPW.csv"

EMAKLER_CSV = """mBank S.A. Bankowość Detaliczna
#Imię i nazwisko
Jan Kowalski

eMAKLER - Transakcje bieżące
Czas transakcji;Papier;Giełda;K/S;Liczba;Kurs;Waluta;Wartość;Waluta
31.07.2026 11:38:55;WEBN GR ETF;DEU-XETRA;K;1;12,6440;EUR;54,57;PLN
31.07.2026 11:36:26;WEBN GR ETF;DEU-XETRA;K;8;12,6480;EUR;436,80;PLN
""".encode("cp1250")

PDF_HEADER = [
    "RYNEK", "WALOR", "OFERTA", "LICZBA", "CENA\nREALIZACJI", "WARTOŚĆ",
    "PROWIZJA", "KURS\nWALUTY", "CZAS ZAWARCIA\nTRANSAKCJI", "DATA\nROZLICZENIA *",
]


def _pdf_table(*, offer="Kupno", quantity="1", commission="0.00PLN"):
    return [
        PDF_HEADER,
        [
            "DEU-XETRA", "WEBN GR ETF –\nIE0003XJA0J9", offer, quantity,
            "12.644EUR", "54.57PLN", commission, "4.3156",
            "2026-07-31\n11:38:55.000", "2026-08-04",
        ],
        ["RAZEM", None, None, quantity, "", "54.57PLN", "", "", None, None],
    ]


def _csv_bytes() -> bytes:
    return CSV_PATH.read_bytes()


def _mem_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def _save_webn_mapping(conn: sqlite3.Connection) -> None:
    save_broker_instrument(
        conn,
        broker="emakler",
        symbol="WEBN GR ETF",
        exchange="DEU-XETRA",
        isin="IE0003XJA0J9",
        name="Amundi Prime All Country World UCITS ETF Acc",
        ticker="WEBN.DE",
        currency="EUR",
    )


def test_parse_number():
    assert parse_number("34,3375") == pytest.approx(34.3375)
    assert parse_number("1 234,56") == pytest.approx(1234.56)
    assert parse_number("0,00") == 0.0


def test_parse_csv_basic():
    rows = parse_csv(_csv_bytes())
    assert len(rows) == 5
    first = rows[0]
    assert first["isin"] == "IE000716YHJ7"
    assert first["type"] == "BUY"
    assert first["quantity"] == 10
    assert first["price_pln"] == pytest.approx(30.00)


def test_detects_both_csv_formats():
    assert detect_csv_format(_csv_bytes()) == "legacy_hispw"
    assert detect_csv_format(EMAKLER_CSV) == "emakler_current"


def test_detects_and_parses_mbank_confirmation_pdf(monkeypatch):
    monkeypatch.setattr(importer_mod, "_pdf_transaction_tables", lambda _: [(_pdf_table(), "108362525")])
    content = b"%PDF-fake-test"
    assert detect_import_format(content) == "mbank_confirmation_pdf"
    rows = parse_import(content)
    assert len(rows) == 1
    row = rows[0]
    assert row["isin"] == "IE0003XJA0J9"
    assert row["type"] == "BUY"
    assert row["price_pln"] == pytest.approx(54.57)
    assert row["native_price"] == pytest.approx(12.644)
    assert row["native_currency"] == "EUR"
    assert row["fx_rate"] == pytest.approx(4.3156)
    assert row["settlement_date"] == "2026-08-04"
    assert row["broker_order_id"] == "108362525"


def test_pdf_parser_supports_sell_and_commission(monkeypatch):
    table = _pdf_table(offer="Sprzedaż", commission="1.23PLN")
    monkeypatch.setattr(importer_mod, "_pdf_transaction_tables", lambda _: [(table, "200")])
    row = parse_import(b"%PDF-sell-test")[0]
    assert row["type"] == "SELL"
    assert row["commission_pln"] == pytest.approx(1.23)


def test_pdf_enriches_matching_csv_transaction_without_duplicate(monkeypatch):
    conn = _mem_db()
    _save_webn_mapping(conn)
    import_transactions(conn, EMAKLER_CSV)
    monkeypatch.setattr(importer_mod, "_pdf_transaction_tables", lambda _: [(_pdf_table(), "108362525")])

    result = import_transactions(conn, b"%PDF-enrichment-test")
    assert result["imported"] == 0
    assert result["skipped_duplicates"] == 1
    assert result["enriched"] == 1
    tx = conn.execute(
        "SELECT native_price, native_currency, fx_rate, settlement_date, market, "
        "broker_order_id, source_format FROM transactions WHERE quantity = 1"
    ).fetchone()
    assert tuple(tx) == (
        12.644, "EUR", 4.3156, "2026-08-04", "DEU-XETRA", "108362525",
        "mbank_confirmation_pdf",
    )

    repeated = import_transactions(conn, b"%PDF-enrichment-test")
    assert repeated["imported"] == 0
    assert repeated["enriched"] == 0


def test_parse_emakler_current_transactions():
    conn = _mem_db()
    _save_webn_mapping(conn)
    rows = importer_mod._parse_emakler(EMAKLER_CSV.decode("cp1250"), conn)
    assert len(rows) == 2
    assert rows[0]["isin"] == "IE0003XJA0J9"
    assert rows[0]["type"] == "BUY"
    assert rows[0]["price_pln"] == pytest.approx(54.57)
    assert rows[1]["quantity"] == 8
    assert rows[1]["price_pln"] == pytest.approx(54.60)
    assert rows[1]["value_pln"] == pytest.approx(436.80)
    assert rows[1]["commission_pln"] == 0


def test_emakler_import_is_idempotent():
    conn = _mem_db()
    _save_webn_mapping(conn)
    first = import_transactions(conn, EMAKLER_CSV)
    second = import_transactions(conn, EMAKLER_CSV)
    assert first["format"] == "emakler_current"
    assert first["imported"] == 2
    assert second["imported"] == 0
    assert second["skipped_duplicates"] == 2


def test_emakler_rejects_unknown_instrument_without_partial_import():
    conn = _mem_db()
    with pytest.raises(BrokerMappingRequired, match="Brak mapowania ISIN") as exc_info:
        import_transactions(conn, EMAKLER_CSV)
    assert exc_info.value.instruments == [{
        "broker": "emakler",
        "symbol": "WEBN GR ETF",
        "exchange": "DEU-XETRA",
        "currency": "EUR",
    }]
    assert conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] == 0


def test_emakler_uses_user_mapping_from_database():
    conn = _mem_db()
    save_broker_instrument(
        conn,
        broker="emakler",
        symbol="TSWE GR ETF",
        exchange="DEU-XETRA",
        isin="NL0010408704",
        name="Użytkownika ETF",
        ticker="TSWE.DE",
        currency="EUR",
    )
    content = EMAKLER_CSV.replace(b"WEBN GR ETF", b"TSWE GR ETF")

    result = import_transactions(conn, content)

    assert result["imported"] == 2
    instrument = conn.execute(
        "SELECT name, ticker, currency FROM instruments WHERE isin = ?", ("NL0010408704",)
    ).fetchone()
    assert tuple(instrument) == ("Użytkownika ETF", "TSWE.DE", "EUR")
    alias = conn.execute(
        "SELECT isin FROM broker_instrument_aliases WHERE broker = ? AND symbol = ? AND exchange = ?",
        ("emakler", "TSWE GR ETF", "DEU-XETRA"),
    ).fetchone()
    assert alias["isin"] == "NL0010408704"


def test_parse_handles_sells():
    rows = parse_csv(_csv_bytes())
    sells = [r for r in rows if r["type"] == "SELL"]
    assert len(sells) == 1
    assert sells[0]["isin"] == "IE000716YHJ7"
    assert sells[0]["value_pln"] == pytest.approx(175.00)


def test_import_idempotent():
    conn = _mem_db()
    content = _csv_bytes()
    first = import_transactions(conn, content)
    assert first["imported"] == 5
    assert first["skipped_duplicates"] == 0
    # Ponowny import nie dubluje.
    second = import_transactions(conn, content)
    assert second["imported"] == 0
    assert second["skipped_duplicates"] == 5
    total = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    assert total == 5


def test_instruments_created_with_seed():
    conn = _mem_db()
    import_transactions(conn, _csv_bytes())
    # ETF PZU: zweryfikowany ticker GPW (.WA), PLN, gotowy do wyceny.
    pzu = conn.execute(
        "SELECT ticker, currency, source, needs_config FROM instruments WHERE isin = ?",
        ("PLPZUMW00018",),
    ).fetchone()
    assert pzu["ticker"] == "ETFPZUWORLD.WA"
    assert pzu["currency"] == "PLN"
    assert pzu["source"] == "yfinance"
    assert pzu["needs_config"] == 0

    # ETF w EUR (Invesco FTSE All-World na Xetrze).
    inv = conn.execute(
        "SELECT ticker, currency, needs_config FROM instruments WHERE isin = ?",
        ("IE000716YHJ7",),
    ).fetchone()
    assert inv["ticker"] == "FWIA.DE"
    assert inv["currency"] == "EUR"
    assert inv["needs_config"] == 0

    # Nieznany ISIN -> brak tickera, wymaga konfiguracji.
    unknown = conn.execute(
        "SELECT ticker, needs_config FROM instruments WHERE isin = ?", ("XX0000000000",)
    ).fetchone()
    assert unknown["ticker"] is None
    assert unknown["needs_config"] == 1


def test_position_quantities():
    """Netto Invesco FTSE All-World = 10 + 10 − 5 = 15."""
    conn = _mem_db()
    import_transactions(conn, _csv_bytes())
    rows = conn.execute(
        "SELECT type, quantity FROM transactions WHERE isin = ?", ("IE000716YHJ7",)
    ).fetchall()
    net = sum(r["quantity"] if r["type"] == "BUY" else -r["quantity"] for r in rows)
    assert net == 15


def test_trade_cash_flows_recorded():
    """Import zapisuje wpływ transakcji na gotówkę (kupno −, sprzedaż +)."""
    conn = _mem_db()
    import_transactions(conn, _csv_bytes())
    # Suma przepływów z transakcji = sprzedaże − kupna = 175 − (300+500+320+150) = −1095.
    total = conn.execute(
        "SELECT COALESCE(SUM(amount_pln), 0) FROM cash_flows WHERE kind IN ('buy', 'sell')"
    ).fetchone()[0]
    assert total == pytest.approx(-1095.00)
