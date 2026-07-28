import json
import os

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import settings

router = APIRouter(prefix="/api", tags=["settings"])

SETTINGS_FILE = os.path.join(settings.data_dir, "settings.json")


class AppSettings(BaseModel):
    ocr_lang: str = "ch"
    scheduled_scan_time: str = "00:00"
    exclude_patterns: str = ""
    theme: str = "system"
    ocr_concurrent: int = 2
    backup_interval_days: int = 0  # 0 = disabled


def _load() -> dict:
    if os.path.isfile(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save(data: dict):
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    with open(SETTINGS_FILE, "w") as f:
        json.dump(data, f, indent=2)


@router.get("/settings")
async def get_settings():
    data = _load()
    result = AppSettings(**data).model_dump()
    # Suggest ocr_concurrent based on actual system memory
    result["suggested_ocr_concurrent"] = _suggest_ocr_concurrent()
    return result


def _suggest_ocr_concurrent() -> int:
    """Suggest a safe ocr_concurrent value based on available memory."""
    import os
    try:
        with open("/proc/meminfo") as f:
            meminfo = f.read()
        for line in meminfo.split("\n"):
            if "MemAvailable" in line:
                available_kb = int(line.split()[1])
                available_mb = available_kb / 1024
                if available_mb > 6000:
                    return 3
                elif available_mb > 3000:
                    return 2
                else:
                    return 1
    except Exception:
        pass
    return 2  # safe default


@router.put("/settings")
async def put_settings(body: AppSettings):
    _save(body.model_dump())
    settings.ocr_lang = body.ocr_lang
    settings.ocr_concurrent = body.ocr_concurrent

    from app.service.scheduler import _update_schedule
    await _update_schedule(body.scheduled_scan_time)

    from app.service.backup import reschedule_backup
    reschedule_backup(body.backup_interval_days)

    return {"status": "saved"}
