"""
Auto-backup service — periodically backs up app_data and index_data.

Configured via settings.json: backup_interval_days = 0 (disabled) | 1-365
"""

import asyncio
import json
import logging
import os
import shutil
import subprocess
import tarfile
import tempfile
import time
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None
BACKUP_DIR = os.path.join(settings.data_dir, "backups")


def _do_backup():
    """Perform a backup of app_data and index_data."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(BACKUP_DIR, f"backup_{timestamp}.tar.gz")

    # VACUUM SQLite first
    db_path = os.path.join(settings.data_dir, "tracker.db")
    if os.path.isfile(db_path):
        try:
            import sqlite3
            conn = sqlite3.connect(db_path, timeout=30)
            conn.execute("VACUUM")
            conn.close()
        except Exception as e:
            logger.warning("VACUUM failed: %s", e)

    # Create tar.gz
    with tarfile.open(backup_file, "w:gz") as tar:
        if os.path.isdir(settings.data_dir):
            tar.add(settings.data_dir, arcname="app_data")
        if os.path.isdir(settings.index_dir):
            tar.add(settings.index_dir, arcname="index_data")

    # Keep only last 7 backups, delete older ones
    backups = sorted([
        os.path.join(BACKUP_DIR, f)
        for f in os.listdir(BACKUP_DIR)
        if f.startswith("backup_") and f.endswith(".tar.gz")
    ])
    for old in backups[:-7]:
        os.remove(old)

    logger.info("backup created: %s (%s)", backup_file,
                _fmt_size(os.path.getsize(backup_file)))


def _fmt_size(size: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"


async def start_backup_scheduler():
    """Start the backup scheduler with the configured interval."""
    global _scheduler
    if _scheduler:
        return

    _scheduler = AsyncIOScheduler()

    # Read interval from settings
    settings_file = os.path.join(settings.data_dir, "settings.json")
    interval_days = 0
    if os.path.isfile(settings_file):
        try:
            data = json.load(open(settings_file))
            interval_days = int(data.get("backup_interval_days", 0))
        except Exception:
            pass

    if interval_days > 0:
        _scheduler.add_job(
            _do_backup,
            trigger="interval",
            days=interval_days,
            id="auto_backup",
            misfire_grace_time=3600,
        )
        logger.info("backup scheduled every %d days", interval_days)
    else:
        logger.info("auto backup disabled")

    _scheduler.start()


async def stop_backup_scheduler():
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None


def reschedule_backup(interval_days: int):
    """Reschedule backup when settings change."""
    global _scheduler
    if _scheduler is None:
        return

    # Remove existing job
    try:
        _scheduler.remove_job("auto_backup")
    except Exception:
        pass

    if interval_days > 0:
        _scheduler.add_job(
            _do_backup,
            trigger="interval",
            days=interval_days,
            id="auto_backup",
            misfire_grace_time=3600,
        )
        logger.info("backup rescheduled: every %d days", interval_days)
    else:
        logger.info("auto backup disabled")


def list_backups() -> list[dict]:
    """List available backup files."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    backups = []
    for f in sorted(os.listdir(BACKUP_DIR), reverse=True):
        if f.startswith("backup_") and f.endswith(".tar.gz"):
            fpath = os.path.join(BACKUP_DIR, f)
            backups.append({
                "filename": f,
                "size": os.path.getsize(fpath),
                "size_str": _fmt_size(os.path.getsize(fpath)),
                "created_at": os.path.getmtime(fpath),
            })
    return backups
