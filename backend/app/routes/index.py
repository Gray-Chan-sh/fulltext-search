import asyncio

from fastapi import APIRouter

from app.models.index import IndexStatusResponse, TriggerResponse
from app.service import tracker
from app.service import scanner as scanner_mod
from app.config import settings

router = APIRouter(prefix="/api/index", tags=["index"])


@router.get("/status", response_model=IndexStatusResponse)
async def index_status():
    # Count files across all dirs, respecting exclude patterns
    from app.routes.dirs import _load_exclude_patterns, _matches_exclude
    excludes = _load_exclude_patterns()
    total = 0
    indexed = 0
    failed = 0
    processing = 0
    for d in tracker.list_dirs():
        if excludes:
            conn = tracker.get_db()
            rows = conn.execute(
                "SELECT path, indexed FROM file_tracking WHERE dir_id = ? AND status = 'active'",
                (d["id"],),
            ).fetchall()
            conn.close()
            for r in rows:
                if _matches_exclude(r["path"], excludes):
                    continue
                total += 1
                if r["indexed"] == 1:
                    indexed += 1
                elif r["indexed"] == 2:
                    failed += 1
                elif r["indexed"] == 3:
                    processing += 1
        else:
            counts = tracker.count_files(d["id"])
            total += counts["total"]
            indexed += counts["indexed"]
            failed += counts["failed"]
            processing += counts["processing"]

    pending = total - indexed - failed - processing
    progress = (indexed / max(total, 1)) * 100

    return IndexStatusResponse(
        total_files=total,
        indexed=indexed,
        pending=max(0, pending),
        failed=failed,
        scanner_status=scanner_mod.scan_state.get("status", "idle"),
        progress_percent=round(progress, 1),
        last_full_scan="",
        next_scheduled_scan=scanner_mod.scan_state.get("next_scheduled_scan",
                                                          f"daily {settings.scheduled_scan_time}"),
        processing_file=scanner_mod.scan_state.get("processing_file", ""),
        processing_progress=scanner_mod.scan_state.get("processing_progress", ""),
    )


@router.post("/trigger", response_model=TriggerResponse)
async def trigger_scan():
    if scanner_mod.scan_state.get("status") == "scanning":
        return TriggerResponse(status="busy", message="扫描已在运行中")

    # Reset stuck processing files, then start scan
    tracker.reset_stuck_processing()
    scanner_mod.scan_state["status"] = "scanning"
    asyncio.create_task(_run_scan())
    return TriggerResponse(status="accepted", message="全量扫描已触发")


async def _run_scan():
    """Run full scan in a background task."""
    try:
        await scanner_mod.run_full_scan()
    except Exception as e:
        scanner_mod.scan_state["status"] = "idle"
        scanner_mod.scan_state["processing_file"] = ""
        tracker.add_log("ERROR", f"全量扫描失败: {e}", source="indexer")


@router.post("/exclude")
async def set_exclude(patterns: list[str]):
    return {"patterns": patterns}


@router.get("/backups")
async def list_backups():
    from app.service.backup import list_backups
    return {"backups": list_backups()}


@router.post("/backup")
async def trigger_backup():
    from app.service.backup import _do_backup
    import asyncio
    asyncio.create_task(asyncio.to_thread(_do_backup))
    return {"status": "started"}