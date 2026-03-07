from __future__ import annotations

from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger


def build_scheduler(job_callable) -> BackgroundScheduler:
    timezone = datetime.now().astimezone().tzinfo
    scheduler = BackgroundScheduler(timezone=timezone)
    scheduler.add_job(
        job_callable,
        trigger=CronTrigger(day_of_week="mon", hour=6, minute=0, timezone=timezone),
        id="generate_weekly_pack",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    return scheduler
