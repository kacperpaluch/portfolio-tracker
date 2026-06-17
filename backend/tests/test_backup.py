"""Testy backupu bazy i eksportu transakcji do CSV."""
from __future__ import annotations

import sqlite3

import pytest

from app import backup as backup_mod
from app.db import SCHEMA
from app.importer import add_transaction


def _mem_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def test_transactions_csv():
    conn = _mem_db()
    add_transaction(conn, ts="2026-06-17T10:00", isin="IE000716YHJ7", name="Invesco",
                    tx_type="BUY", quantity=10, price_pln=30.0)
    csv_text = backup_mod.transactions_csv(conn)
    lines = csv_text.strip().splitlines()
    assert lines[0] == "ts,isin,name,type,quantity,price_pln,value_pln,commission_pln"
    assert "IE000716YHJ7" in lines[1]
    assert "Invesco" in lines[1]
    assert "BUY" in lines[1]


def test_backup_creates_consistent_copy(tmp_path, monkeypatch):
    from app import db

    monkeypatch.setattr(db, "DB_PATH", tmp_path / "src.db")
    monkeypatch.setattr(backup_mod, "BACKUP_DIR", tmp_path / "bk")
    db.init_db()

    conn = db.get_connection()
    add_transaction(conn, ts="2026-06-17T10:00", isin="X", name="X",
                    tx_type="BUY", quantity=5, price_pln=20.0)
    conn.close()

    dest = tmp_path / "backup.db"
    out = backup_mod.backup_database(dest=dest)
    assert out == dest and dest.exists()

    c2 = sqlite3.connect(dest)
    n = c2.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    c2.close()
    assert n == 1


def test_backup_retention(tmp_path, monkeypatch):
    from app import db

    monkeypatch.setattr(db, "DB_PATH", tmp_path / "src.db")
    monkeypatch.setattr(backup_mod, "BACKUP_DIR", tmp_path / "bk")
    monkeypatch.setattr(backup_mod, "BACKUP_KEEP", 3)
    db.init_db()

    # Utwórz 5 „kopii" o różnych datach, potem prune zostawia 3 najnowsze.
    (tmp_path / "bk").mkdir()
    for d in ["2026-06-10", "2026-06-11", "2026-06-12", "2026-06-13", "2026-06-14"]:
        (tmp_path / "bk" / f"portfolio-{d}.db").write_bytes(b"x")
    backup_mod._prune()
    remaining = sorted(p.name for p in (tmp_path / "bk").glob("portfolio-*.db"))
    assert remaining == ["portfolio-2026-06-12.db", "portfolio-2026-06-13.db", "portfolio-2026-06-14.db"]
