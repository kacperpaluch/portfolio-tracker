"""Backup bazy SQLite: spójna kopia przez API sqlite3 + retencja. Eksport transakcji do CSV."""
from __future__ import annotations

import csv
import io
import os
import sqlite3
from datetime import datetime
from pathlib import Path

from .db import DB_PATH, get_connection

# Domyślnie podfolder backup obok bazy; nadpisywalne env.
BACKUP_DIR = Path(os.environ.get("BACKUP_DIR", DB_PATH.parent / "backup"))
# Ile ostatnich kopii trzymać (retencja).
BACKUP_KEEP = int(os.environ.get("BACKUP_KEEP", "14"))


def backup_database(dest: Path | None = None) -> Path:
    """Tworzy spójną kopię bazy (online backup API). Domyślnie do BACKUP_DIR/portfolio-<data>.db."""
    if dest is None:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")  # z czasem — kilka kopii dziennie
        dest = BACKUP_DIR / f"portfolio-{stamp}.db"
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)

    src = get_connection()
    try:
        dst = sqlite3.connect(dest)
        try:
            src.backup(dst)  # spójna kopia nawet przy równoległym zapisie
        finally:
            dst.close()
    finally:
        src.close()

    _prune()
    return dest


def _prune() -> None:
    """Zostawia tylko BACKUP_KEEP najnowszych kopii."""
    backups = sorted(BACKUP_DIR.glob("portfolio-*.db"))
    for old in backups[:-BACKUP_KEEP] if BACKUP_KEEP > 0 else []:
        old.unlink(missing_ok=True)


def list_backups() -> list[dict]:
    if not BACKUP_DIR.is_dir():
        return []
    out = []
    for p in sorted(BACKUP_DIR.glob("portfolio-*.db"), reverse=True):
        st = p.stat()
        out.append({"file": p.name, "size_kb": round(st.st_size / 1024, 1),
                    "modified": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds")})
    return out


def transactions_csv(conn: sqlite3.Connection) -> str:
    """Eksport transakcji do czytelnego CSV (UTF-8, przecinek)."""
    rows = conn.execute(
        """
        SELECT t.ts, t.isin, i.name, t.type, t.quantity, t.price_pln, t.value_pln, t.commission_pln
          FROM transactions t
          LEFT JOIN instruments i ON i.isin = t.isin
         ORDER BY t.ts ASC
        """
    ).fetchall()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["ts", "isin", "name", "type", "quantity", "price_pln", "value_pln", "commission_pln"])
    for r in rows:
        w.writerow([r["ts"], r["isin"], r["name"], r["type"], r["quantity"],
                    r["price_pln"], r["value_pln"], r["commission_pln"]])
    return buf.getvalue()
