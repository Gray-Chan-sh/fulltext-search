"""APScheduler for daily scheduled full scans.

Runs scans in-process via background task (never blocks the API).
"""

import asyncio
import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.service.scanner import run_full_scan, scan_state
from app.service import tracker

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None
_INITIAL_SCAN_DELAY = 10


async def _run_scan_task():
    tracker.reset_stuck_processing()
    scan_state["status"] = "scanning"
    try:
        await run_full_scan()
    except Exception as e:
        logger.error("scan failed: %s", e)
        tracker.add_log("ERROR", f"扫描失败: {e}", source="indexer")
    finally:
        scan_state["status"] = "idle"
        scan_state["processing_file"] = ""


async def start_scheduler():
    global _scheduler
    if _scheduler:
        return
    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(_run_initial_scan, trigger="date", run_date=None, id="_initial_scan", misfire_grace_time=60)
    hour, minute = _parse_time(settings.scheduled_scan_time)
    _scheduler.add_job(_run_scheduled_scan, trigger="cron", hour=hour, minute=minute, id="daily_scan", misfire_grace_time=3600)
    _scheduler.start()
    _update_next_scan_time()
    logger.info("scheduler started")


async def stop_scheduler():
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None


async def _run_initial_scan():
    await asyncio.sleep(_INITIAL_SCAN_DELAY)
    logger.info("starting initial full scan")
    asyncio.create_task(_run_scan_task())
    from app.service.watcher import start_watcher
    await start_watcher()


async def _run_scheduled_scan():
    logger.info("starting scheduled full scan")
    asyncio.create_task(_run_scan_task())


async def _update_schedule(time_str: str):
    global _scheduler
    if _scheduler is None:
        return
    hour, minute = _parse_time(time_str)
    _scheduler.reschedule_job("daily_scan", trigger="cron", hour=hour, minute=minute)
    _update_next_scan_time()
    logger.info("scheduled scan updated to %s", time_str)


def _update_next_scan_time():
    from app.service.scanner import scan_state
    if _scheduler is None:
        return
    daily = _scheduler.get_job("daily_scan")
    if daily and daily.next_run_time:
        scan_state["next_scheduled_scan"] = daily.next_run_time.strftime("%Y-%m-%d %H:%M")


def _parse_time(time_str: str) -> tuple[int, int]:
    try:
        parts = time_str.split(":")
        return int(parts[0]), int(parts[1])
    except Exception:
        return 0, 0