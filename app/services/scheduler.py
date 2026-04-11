from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import Settings
from app.db.session import SessionLocal
from app.models import AppSetting
from app.services.sync import SyncService


def build_scheduler(settings: Settings) -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone=settings.scheduler_timezone)

    def scheduled_sync_job() -> None:
        db = SessionLocal()
        try:
            sync_service = SyncService(db)
            sync_service.run_manual_sync()
        finally:
            db.close()

    db = SessionLocal()
    try:
        app_settings = db.query(AppSetting).first()
        interval = app_settings.polling_interval_minutes if app_settings else 30
    finally:
        db.close()

    scheduler.add_job(
        scheduled_sync_job,
        trigger=IntervalTrigger(minutes=interval),
        id="scheduled-sync",
        replace_existing=True,
    )
    return scheduler
