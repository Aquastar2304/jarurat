"""Bonus: in-process scheduled trigger.

``python main.py --schedule 09:00`` runs the pipeline every day at 09:00
(local time) until stopped with Ctrl+C. For unattended runs see
``scripts/register_windows_task.ps1`` (Task Scheduler) and
``.github/workflows/scheduled-run.yml`` (GitHub Actions cron).
"""

from __future__ import annotations

import logging
import time
from typing import Callable

import schedule

log = logging.getLogger(__name__)


def run_daily(job: Callable[[], object], at_time: str, run_immediately: bool = True) -> None:
    def safe_job() -> None:
        try:
            job()
        except Exception:  # noqa: BLE001 - a failed run must not kill the scheduler
            log.exception("Scheduled run failed")

    schedule.every().day.at(at_time).do(safe_job)
    log.info("Scheduler started - pipeline will run daily at %s (Ctrl+C to stop)", at_time)
    if run_immediately:
        safe_job()
    while True:
        schedule.run_pending()
        time.sleep(30)
