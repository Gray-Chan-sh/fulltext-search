"""Enhanced file management features: duplicates, recent activity, OCR quality report."""

import time

from fastapi import APIRouter

from app.service import tracker

router = APIRouter(prefix="/api", tags=["files"])


@router.get("/files/duplicates")
async def list_duplicates():
    """List files with duplicate content (same MD5)."""
    conn = tracker.get_db()
    rows = conn.execute("""
        SELECT ft1.md5, ft1.path as path1, ft2.path as path2,
               ft1.size, ft1.modified as modified1, ft2.modified as modified2
        FROM file_tracking ft1
        JOIN file_tracking ft2 ON ft1.md5 = ft2.md5 AND ft1.md5 IS NOT NULL
        WHERE ft1.id < ft2.id AND ft1.status = 'active' AND ft2.status = 'active'
        ORDER BY ft1.size DESC
    """).fetchall()
    conn.close()
    groups: dict[str, dict] = {}
    for r in rows:
        md5 = r["md5"]
        if md5 not in groups:
            groups[md5] = {"md5": md5, "size": r["size"], "files": []}
        groups[md5]["files"].append(r["path1"])
        groups[md5]["files"].append(r["path2"])
    # Deduplicate file paths per group
    result = []
    for g in groups.values():
        g["files"] = list(set(g["files"]))
        g["count"] = len(g["files"])
        result.append(g)
    return {"duplicates": sorted(result, key=lambda x: -x["size"])}


@router.get("/files/recent")
async def recent_activity(limit: int = 20):
    """Recent file activity (newly indexed, failed)."""
    conn = tracker.get_db()
    recently_indexed = conn.execute("""
        SELECT path, updated_at FROM file_tracking
        WHERE status = 'active' AND indexed = 1
        ORDER BY updated_at DESC LIMIT ?
    """, (limit,)).fetchall()
    failed = conn.execute("""
        SELECT path, error_msg, updated_at FROM file_tracking
        WHERE status = 'active' AND indexed = 2
        ORDER BY updated_at DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return {
        "recently_indexed": [dict(r) for r in recently_indexed],
        "failed": [dict(r) for r in failed],
    }


@router.get("/files/ocr-report")
async def ocr_report():
    """OCR quality report: files with low text count, OCR duration stats."""
    conn = tracker.get_db()
    # Files with OCR used, ordered by character count (lowest first)
    low_text = conn.execute("""
        SELECT ft.path, ci.char_count, ci.ocr_duration_ms, ci.ocr_used
        FROM file_tracking ft
        JOIN content_index ci ON ci.md5 = ft.md5
        WHERE ft.status = 'active' AND ci.ocr_used = 1
        ORDER BY ci.char_count ASC LIMIT 50
    """).fetchall()
    # OCR stats
    stats = conn.execute("""
        SELECT COUNT(*) as total_ocr,
               SUM(ci.char_count) as total_chars,
               AVG(ci.ocr_duration_ms) as avg_duration_ms,
               AVG(ci.char_count) as avg_chars
        FROM file_tracking ft
        JOIN content_index ci ON ci.md5 = ft.md5
        WHERE ft.status = 'active' AND ci.ocr_used = 1
    """).fetchone()
    conn.close()
    return {
        "low_text_files": [dict(r) for r in low_text],
        "stats": dict(stats) if stats else {},
    }
