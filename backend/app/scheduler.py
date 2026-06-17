"""Codzienne odświeżanie cen i kursów (APScheduler).

Domyślnie o 21:00 czasu Europe/Warsaw — po zamknięciu sesji giełdowych i publikacji
kursów NBP. Godzinę można zmienić zmienną środowiskową REFRESH_HOUR.
"""
from __future__ import annotations

import logging
import os

from apscheduler.schedulers.background import BackgroundScheduler

from . import backup as backup_mod
from . import fx as fx_mod
from . import instruments as instruments_mod
from . import prices as prices_mod
from .db import db_session

log = logging.getLogger("scheduler")

REFRESH_HOUR = int(os.environ.get("REFRESH_HOUR", "21"))
REFRESH_MINUTE = int(os.environ.get("REFRESH_MINUTE", "0"))
BACKUP_HOUR = int(os.environ.get("BACKUP_HOUR", "3"))
BACKUP_MINUTE = int(os.environ.get("BACKUP_MINUTE", "0"))
TIMEZONE = os.environ.get("TZ", "Europe/Warsaw")


def refresh_job() -> dict:
    """Pobiera bieżące ceny i kursy FX dla aktywnych, skonfigurowanych instrumentów."""
    with db_session() as conn:
        instruments = [
            i for i in instruments_mod.list_instruments(conn)
            if i["active"] and not i["needs_config"]
        ]
        prices_updated = 0
        for inst in instruments:
            if prices_mod.fetch_latest(conn, inst):
                prices_updated += 1
        currencies = {i["currency"] for i in instruments if i["currency"] and i["currency"] != "PLN"}
        fx_updated = 0
        for cur in currencies:
            try:
                fx_mod.get_rate(conn, cur)
                fx_updated += 1
            except Exception:
                pass
    log.info("Odświeżono: ceny=%s, FX=%s", prices_updated, fx_updated)
    return {"prices": prices_updated, "fx": fx_updated}


def backup_job() -> dict:
    """Nocna kopia bazy do BACKUP_DIR (z retencją)."""
    path = backup_mod.backup_database()
    log.info("Backup bazy: %s", path)
    return {"file": str(path)}


def start_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone=TIMEZONE)
    scheduler.add_job(
        refresh_job, "cron", hour=REFRESH_HOUR, minute=REFRESH_MINUTE,
        id="daily_refresh", replace_existing=True,
    )
    scheduler.add_job(
        backup_job, "cron", hour=BACKUP_HOUR, minute=BACKUP_MINUTE,
        id="nightly_backup", replace_existing=True,
    )
    scheduler.start()
    log.info("Scheduler: odświeżanie %02d:%02d, backup %02d:%02d (%s)",
             REFRESH_HOUR, REFRESH_MINUTE, BACKUP_HOUR, BACKUP_MINUTE, TIMEZONE)
    return scheduler
