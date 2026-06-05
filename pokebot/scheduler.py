"""Planification : scan automatique toutes les N minutes (config)."""
from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler

from .config import settings
from .core.scanner import run_scan
from .utils.logging import get_logger

log = get_logger("scheduler")

_scheduler: BackgroundScheduler | None = None


def start_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    sch = BackgroundScheduler(timezone="UTC")
    sch.add_job(
        run_scan,
        trigger="interval",
        minutes=settings.scan_interval_minutes,
        args=["auto"],
        id="scan",
        max_instances=1,
        coalesce=True,
    )
    sch.start()
    _scheduler = sch
    log.info("Planificateur demarre : scan toutes les %s min.", settings.scan_interval_minutes)
    return sch


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
