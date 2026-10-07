"""Testy kont: widok jednego konta, spójny widok łączny przy mieszanej księdze gotówki, podatek."""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from app import accounts, db
from app import cash as cash_mod
from app import history as history_mod
from app import portfolio as portfolio_mod
from app.importer import add_transaction, update_transaction


@pytest.fixture
def two_accounts(tmp_path, monkeypatch):
    """IKE (1): prowadzi gotówkę, 10 szt. A. Zwykłe (2, opodatkowane): bez wpłat, 10 szt. B."""
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "portfolio.db")
    db.init_db()
    with db.db_session() as conn:
        regular = accounts.save(conn, None, "Zwykłe", True)["id"]
        cash_mod.add_flow(conn, "2026-01-02", "deposit", 10_000)
        add_transaction(conn, ts="2026-01-05", isin="A", name="A", tx_type="BUY", quantity=10, price_pln=100)
        add_transaction(conn, ts="2026-01-05", isin="B", name="B", tx_type="BUY", quantity=10, price_pln=100,
                        account_id=regular)
        conn.execute("UPDATE instruments SET currency = 'PLN', ticker = isin, source = 'csv', needs_config = 0")
        today = date.today().isoformat()
        conn.executemany(
            "INSERT INTO prices (isin, date, price, source) VALUES (?, ?, ?, 'csv')",
            [("A", "2026-01-05", 100), ("B", "2026-01-05", 100), ("A", today, 120), ("B", today, 150)],
        )
    return regular


def _totals(account_id):
    with db.read_session(account_id) as conn:
        data = portfolio_mod.value_positions(conn)
        return data, history_mod.portfolio_history(conn)[-1]["value_pln"]


def test_single_account_view_sees_only_its_data(two_accounts):
    ike, ike_last = _totals(1)
    assert [p["isin"] for p in ike["positions"]] == ["A"]
    assert ike["totals"]["cash_pln"] == 9000 and ike["totals"]["portfolio_value_pln"] == 10200
    assert ike_last == pytest.approx(10200)

    regular, regular_last = _totals(two_accounts)
    assert [p["isin"] for p in regular["positions"]] == ["B"]
    # konto bez wpłat nie prowadzi gotówki — sama wycena, bez ujemnego salda
    assert regular["totals"]["cash_pln"] == 0 and regular["totals"]["portfolio_value_pln"] == 1500
    assert regular_last == pytest.approx(1500)


def test_combined_view_is_sum_of_accounts(two_accounts):
    both, last = _totals(None)
    assert {p["isin"] for p in both["positions"]} == {"A", "B"}
    # kupno na koncie bez księgi nie obciąża gotówki IKE; jego koszt liczy się jako wkład
    assert both["totals"]["cash_pln"] == 9000
    assert both["totals"]["net_deposits_pln"] == 11000
    assert both["totals"]["portfolio_value_pln"] == 10200 + 1500
    assert last == pytest.approx(10200 + 1500)
    with db.read_session() as conn:
        assert [f["amount_pln"] for f in cash_mod.list_external(conn)] == [10_000]  # bez syntetycznych


def test_twr_without_cash_ledger_ignores_later_purchases(two_accounts):
    """Dokupienie na koncie bez wpłat to wkład, nie zysk: B stoi na 150 → TWR bez zmian."""
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    with db.db_session() as conn:  # kurs stoi od wczoraj, więc dzisiejszy zakup nie trafia w ruch ceny
        conn.execute("INSERT INTO prices (isin, date, price, source) VALUES ('B', ?, 150, 'csv')", (yesterday,))
    with db.read_session(two_accounts) as conn:
        before = history_mod.portfolio_twr(conn)
    with db.db_session() as conn:
        add_transaction(conn, ts=date.today().isoformat(), isin="B", name="B", tx_type="BUY",
                        quantity=100, price_pln=150, account_id=two_accounts)
    with db.read_session(two_accounts) as conn:
        assert history_mod.portfolio_twr(conn) == pytest.approx(before)


def test_tax_estimate_only_for_taxed_accounts(two_accounts):
    with db.read_session() as conn:
        accs = accounts.list_accounts(conn)
    both, _ = _totals(None)
    regular, _ = _totals(two_accounts)
    ike, _ = _totals(1)
    assert accounts.estimate_tax(accs, None, both["positions"]) == 95.0  # 19% × 500
    assert accounts.estimate_tax(accs, two_accounts, regular["positions"]) == 95.0
    assert regular["positions"][0]["tax_pln"] == 95.0
    assert accounts.estimate_tax(accs, 1, ike["positions"]) == 0.0


def test_moving_transaction_moves_its_cash_flow(two_accounts):
    with db.db_session() as conn:
        tx = conn.execute("SELECT * FROM transactions WHERE isin = 'A'").fetchone()
        update_transaction(conn, tx["id"], ts=tx["ts"], isin="A", name=None, tx_type="BUY",
                           quantity=10, price_pln=100, account_id=two_accounts)
    with db.read_session(1) as conn:
        ike = portfolio_mod.value_positions(conn)
    assert ike["positions"] == [] and ike["totals"]["cash_pln"] == 10_000


def test_accounts_validation(two_accounts):
    with db.db_session() as conn:
        with pytest.raises(ValueError):
            accounts.save(conn, None, "IKE", False)  # duplikat nazwy
        with pytest.raises(ValueError):
            accounts.require(conn, 999)
        assert accounts.require(conn, None) == accounts.DEFAULT_ID
