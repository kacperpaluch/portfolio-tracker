"""Codzienne odświeżanie cen i kursów (APScheduler).

Domyślnie o 21:00 czasu Europe/Warsaw — po zamknięciu sesji giełdowych i publikacji
kursów NBP. Godzinę można zmienić zmienną środowiskową REFRESH_HOUR.
"""
from __future__ import annotations

import logging
import os

from apscheduler.schedulers.background import BackgroundScheduler

from . import backup as backup_mod
from . import history as history_mod
from .db import db_session

log = logging.getLogger("scheduler")

REFRESH_HOUR = int(os.environ.get("REFRESH_HOUR", "21"))
REFRESH_MINUTE = int(os.environ.get("REFRESH_MINUTE", "0"))
BACKUP_HOUR = int(os.environ.get("BACKUP_HOUR", "3"))
BACKUP_MINUTE = int(os.environ.get("BACKUP_MINUTE", "0"))
TIMEZONE = os.environ.get("TZ", "Europe/Warsaw")


def refresh_job() -> dict:
    """Pobiera bieżące ceny i kursy FX + dociąga luki w historii (np. po awarii sieci)."""
    with db_session() as conn:
        result = history_mod.refresh_latest(conn)
    log.info("Odświeżono: ceny=%s, FX=%s, luki(ceny/FX)=%s/%s",
             result["prices"], result["fx"], result["gap_prices"], result["gap_fx"])
    return result


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
