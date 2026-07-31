"""Backup bazy SQLite: spójna kopia przez API sqlite3 + retencja. Eksport transakcji do CSV."""
from __future__ import annotations

import csv
import hashlib
import io
import os
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

from . import db as db_mod

# Domyślnie podfolder backup obok bazy; nadpisywalne env.
BACKUP_DIR = Path(os.environ.get("BACKUP_DIR", db_mod.DB_PATH.parent / "backup"))
# Ile ostatnich kopii trzymać (retencja).
BACKUP_KEEP = int(os.environ.get("BACKUP_KEEP", "14"))
BACKUP_STALE_HOURS = int(os.environ.get("BACKUP_STALE_HOURS", "36"))
BACKUP_HOUR = int(os.environ.get("BACKUP_HOUR", "3"))
BACKUP_MINUTE = int(os.environ.get("BACKUP_MINUTE", "0"))
TIMEZONE = os.environ.get("TZ", "Europe/Warsaw")
REQUIRED_TABLES = {
    "instruments", "target_allocation", "transactions", "prices",
    "fx_rates", "cpi_index", "cash_flows",
}
_LOCK = threading.RLock()


def backup_database(dest: Path | None = None, *, prune: bool = True) -> Path:
    """Tworzy spójną kopię bazy (online backup API). Domyślnie do BACKUP_DIR/portfolio-<data>.db."""
    with _LOCK:
        if dest is None:
            BACKUP_DIR.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            dest = BACKUP_DIR / f"portfolio-{stamp}.db"
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)

        src = db_mod.get_connection()
        try:
            dst = sqlite3.connect(dest)
            try:
                src.backup(dst)
            finally:
                dst.close()
        finally:
            src.close()

        validation = validate_database(dest)
        if not validation["valid"]:
            dest.unlink(missing_ok=True)
            raise ValueError(f"Utworzony backup jest nieprawidłowy: {validation['error']}")
        if prune:
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
        modified = datetime.fromtimestamp(st.st_mtime)
        out.append({
            "file": p.name,
            "size_kb": round(st.st_size / 1024, 1),
            "modified": modified.isoformat(timespec="seconds"),
            "age_hours": round((datetime.now() - modified).total_seconds() / 3600, 1),
            "kind": "pre_restore" if p.name.startswith("portfolio-pre-restore-") else "scheduled",
        })
    return out


def backup_status() -> dict:
    backups = list_backups()
    latest = backups[0] if backups else None
    validation = validate_database(resolve_backup(latest["file"])) if latest else None
    stale = latest is None or latest["age_hours"] > BACKUP_STALE_HOURS
    healthy = bool(latest and validation and validation["valid"] and not stale)
    return {
        "healthy": healthy,
        "stale": stale,
        "stale_after_hours": BACKUP_STALE_HOURS,
        "keep": BACKUP_KEEP,
        "schedule": {
            "hour": BACKUP_HOUR,
            "minute": BACKUP_MINUTE,
            "timezone": TIMEZONE,
        },
        "latest": latest,
        "latest_validation": validation,
        "backups": backups,
        "dir": str(BACKUP_DIR),
    }


def resolve_backup(filename: str) -> Path:
    """Zwraca bezpieczną ścieżkę kopii, bez możliwości wyjścia poza BACKUP_DIR."""
    if not filename or Path(filename).name != filename or not filename.startswith("portfolio-") or not filename.endswith(".db"):
        raise ValueError("Nieprawidłowa nazwa pliku backupu")
    path = BACKUP_DIR / filename
    if not path.is_file():
        raise FileNotFoundError(filename)
    return path


def validate_database(path: Path) -> dict:
    """Sprawdza nagłówek SQLite, integralność, schemat i podstawowe liczności."""
    try:
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError("Plik nie istnieje lub jest pusty")
        with path.open("rb") as handle:
            if handle.read(16) != b"SQLite format 3\x00":
                raise ValueError("Plik nie jest bazą SQLite")
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                raise ValueError(f"integrity_check: {integrity}")
            tables = {
                r["name"] for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            missing = sorted(REQUIRED_TABLES - tables)
            if missing:
                raise ValueError(f"Brak tabel: {', '.join(missing)}")
            counts = {
                table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in ("instruments", "transactions", "prices", "cash_flows")
            }
        finally:
            conn.close()
        hasher = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                hasher.update(chunk)
        return {
            "valid": True,
            "error": None,
            "integrity": "ok",
            "size_kb": round(path.stat().st_size / 1024, 1),
            "sha256": hasher.hexdigest(),
            "counts": counts,
        }
    except (OSError, sqlite3.DatabaseError, ValueError) as exc:
        return {
            "valid": False, "error": str(exc), "integrity": None,
            "size_kb": round(path.stat().st_size / 1024, 1) if path.exists() else 0,
            "sha256": None, "counts": None,
        }


def restore_database(source: Path) -> dict:
    """Waliduje kopię, tworzy safety backup i odtwarza bieżącą bazę."""
    with _LOCK:
        validation = validate_database(source)
        if not validation["valid"]:
            raise ValueError(f"Nie można przywrócić kopii: {validation['error']}")

        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        safety = BACKUP_DIR / f"portfolio-pre-restore-{stamp}.db"
        backup_database(dest=safety, prune=False)

        src = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
        dst = db_mod.get_connection()
        try:
            src.backup(dst)
            dst.commit()
        finally:
            dst.close()
            src.close()

        db_mod.init_db()
        restored = validate_database(db_mod.DB_PATH)
        if not restored["valid"]:
            raise RuntimeError(f"Przywrócona baza nie przeszła kontroli: {restored['error']}")
        _prune()
        return {
            "restored_from": source.name,
            "safety_backup": safety.name,
            "validation": restored,
        }


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


def daily_changes_csv(conn: sqlite3.Connection) -> str:
    """Eksport dziennych zmian wartości portfela do CSV (UTF-8, przecinek)."""
    from . import history as history_mod

    rows = history_mod.portfolio_daily_changes(conn)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["date", "value_pln", "flow_pln", "change_pln", "change_pct"])
    for r in rows:
        w.writerow([r["date"], r["value_pln"], r["flow_pln"], r["change_pln"], r["change_pct"]])
    return buf.getvalue()
