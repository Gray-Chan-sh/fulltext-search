import csv
import io

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.service import tracker

router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get("")
async def get_logs(
    level: str = Query("", description="Filter by level: INFO/WARNING/ERROR"),
    source: str = Query("", description="Filter by source: server/indexer/ocr/extractor/watcher"),
    q: str = Query("", description="Keyword search"),
    limit: int = Query(200, le=5000),
    offset: int = Query(0),
):
    logs = tracker.query_logs(
        level=level if level else None,
        source=source if source else None,
        q=q if q else None,
        limit=limit,
        offset=offset,
    )
    return {"logs": logs, "total": len(logs)}


@router.get("/export")
async def export_logs(
    level: str = Query(""),
    source: str = Query(""),
    q: str = Query(""),
):
    logs = tracker.query_logs(
        level=level if level else None,
        source=source if source else None,
        q=q if q else None,
        limit=5000,
        offset=0,
    )
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["时间", "级别", "来源", "消息", "文件", "耗时(ms)"])
    import time as tmod
    for log in logs:
        ts = tmod.strftime("%Y-%m-%d %H:%M:%S", tmod.localtime(log["created_at"]))
        writer.writerow([
            ts, log["level"], log.get("source", ""),
            log["message"], log.get("file_path", ""),
            log.get("duration_ms", ""),
        ])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=logs.csv"},
    )