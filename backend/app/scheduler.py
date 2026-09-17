"""Background monitoring.

APScheduler keeps the MVP to one process.  Swap in Celery + Redis by pointing
the same `monitor_job` at a task queue -- nothing else changes.
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from .config import settings
from .db import session_scope
from .services import run_monitoring

log = logging.getLogger("mosaic.scheduler")
_scheduler: BackgroundScheduler | None = None


def monitor_job() -> None:
    try:
        with session_scope() as db:
            summary = run_monitoring(db)
        log.info(
            "monitor cycle: %s items, %s alerts, %s suppressed",
            summary["polled_items"], summary["alerts"], summary["suppressed"],
        )
    except Exception:  # noqa: BLE001
        log.exception("monitor cycle failed")


def start_scheduler() -> BackgroundScheduler | None:
    global _scheduler
    if not settings.enable_scheduler or _scheduler is not None:
        return _scheduler
    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.add_job(
        monitor_job,
        "interval",
        minutes=settings.monitor_interval_minutes,
        id="mosaic-monitor",
        max_instances=1,
        coalesce=True,
    )
    _scheduler.start()
    log.info("scheduler started (every %s minutes)", settings.monitor_interval_minutes)
    return _scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
