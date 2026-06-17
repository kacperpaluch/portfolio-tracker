"""Testy ręcznego dodawania/usuwania transakcji, dedupu importu i historii waloru."""
from __future__ import annotations

import sqlite3

import pytest

from app import cash as cash_mod
from app import history as history_mod
from app.db import SCHEMA
from app.importer import add_transaction, delete_transaction, import_transactions


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def _count(conn, table):
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_manual_add_creates_tx_and_cashflow():
    conn = _db()
    r = add_transaction(conn, ts="2026-06-17T10:00", isin="IE000716YHJ7", name="Invesco",
                        tx_type="BUY", quantity=10, price_pln=30.0)
    assert r["created"] is True
    assert _count(conn, "transactions") == 1
    # Kupno -> przepływ gotówki −300.
    cf = conn.execute("SELECT amount_pln FROM cash_flows WHERE kind = 'buy'").fetchone()
    assert cf["amount_pln"] == pytest.approx(-300.0)


def test_manual_add_is_idempotent():
    conn = _db()
    kw = dict(ts="2026-06-17T10:00", isin="X", name="X", tx_type="BUY", quantity=10, price_pln=30.0)
    assert add_transaction(conn, **kw)["created"] is True
    assert add_transaction(conn, **kw)["created"] is False  # ten sam hash
    assert _count(conn, "transactions") == 1


def test_delete_removes_tx_and_cashflow():
    conn = _db()
    r = add_transaction(conn, ts="2026-06-17T10:00", isin="X", name="X",
                        tx_type="BUY", quantity=10, price_pln=30.0)
    assert delete_transaction(conn, r["id"]) is True
    assert _count(conn, "transactions") == 0
    assert _count(conn, "cash_flows") == 0
    # Usunięcie nieistniejącej -> False.
    assert delete_transaction(conn, 999) is False


def test_import_only_new_when_mixed_old_and_new():
    conn = _db()
    header = "data;papier;isin;ilosc;-;cena;wartosc;prowizja;po prowizji;waluta"
    old = "01.04.2026 10:00:00;ETF A;ISINAAA;10;K;30,00;300,00;0,00;300,00;PLN"
    new1 = "02.04.2026 10:00:00;ETF A;ISINAAA;5;K;31,00;155,00;0,00;155,00;PLN"
    new2 = "03.04.2026 10:00:00;ETF A;ISINAAA;2;S;32,00;64,00;0,00;64,00;PLN"

    first = import_transactions(conn, (header + "\n" + old + "\n").encode("cp1250"))
    assert first["imported"] == 1
    # Drugi plik: stary wiersz + dwa nowe -> tylko 2 nowe importowane, stary pominięty.
    second = import_transactions(conn, (header + "\n" + old + "\n" + new1 + "\n" + new2 + "\n").encode("cp1250"))
    assert second["imported"] == 2
    assert second["skipped_duplicates"] == 1
    assert _count(conn, "transactions") == 3


def test_instrument_history():
    conn = _db()
    add_transaction(conn, ts="2026-06-10", isin="EUR1", name="Euro ETF", tx_type="BUY", quantity=10, price_pln=80.0)
    # Instrument utworzony jako needs_config; ustaw walutę EUR ręcznie.
    conn.execute("UPDATE instruments SET currency = 'EUR' WHERE isin = 'EUR1'")
    conn.execute("INSERT INTO prices (isin, date, price, source) VALUES ('EUR1','2026-06-16',20.0,'yfinance')")
    conn.execute("INSERT INTO fx_rates (date, currency, rate_to_pln) VALUES ('2026-06-15','EUR',4.30)")
    conn.commit()

    h = history_mod.instrument_history(conn, "EUR1")
    assert h["currency"] == "EUR"
    row = h["rows"][0]
    assert row["price_native"] == pytest.approx(20.0)
    # FX z 2026-06-15 (forward-fill na 06-16) -> cena PLN = 20 * 4.30 = 86.
    assert row["fx_rate"] == pytest.approx(4.30)
    assert row["price_pln"] == pytest.approx(86.0)
    assert row["quantity"] == pytest.approx(10.0)
    assert row["value_pln"] == pytest.approx(860.0)


def test_instrument_history_missing():
    conn = _db()
    assert history_mod.instrument_history(conn, "NOPE") is None
