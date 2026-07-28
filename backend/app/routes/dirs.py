import asyncio
import fnmatch
import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models.dirs import (
    DirConfigCreate,
    DirConfigResponse,
    DirConfigUpdate,
    DirListResponse,
)
from app.service import tracker
from app.service.watcher import refresh_watcher
from app.service.scanner import run_full_scan

router = APIRouter(prefix="/api/dirs", tags=["dirs"])


@router.get("", response_model=DirListResponse)
async def list_dirs():
    excludes = _load_exclude_patterns()
    conn = tracker.get_db()
    dirs = tracker.list_dirs()
    items: list[DirConfigResponse] = []
    for d in dirs:
        total = 0
        indexed = 0
        failed = 0
        processing = 0
        if excludes:
            rows = conn.execute(
                "SELECT path, indexed FROM file_tracking WHERE dir_id = ? AND status = 'active'",
                (d["id"],),
            ).fetchall()
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
            total = counts["total"]
            indexed = counts["indexed"]
            failed = counts["failed"]
            processing = counts["processing"]

        items.append(DirConfigResponse(
            id=d["id"],
            path=d["path"],
            alias=d.get("alias") or "",
            ocr_lang=d.get("ocr_lang") or "ch",
            exclude_patterns=d.get("exclude_patterns") or "",
            include_exts=d.get("include_exts") or "",
            file_count=total,
            indexed_count=indexed,
            failed_count=failed,
            processing_count=processing,
            status="watching" if os.path.isdir(d["path"]) else "unavailable",
        ))
    conn.close()
    return DirListResponse(dirs=items)


@router.post("", status_code=201)
async def add_dir(cfg: DirConfigCreate):
    if not os.path.isdir(cfg.path):
        raise HTTPException(400, f"Directory does not exist: {cfg.path}")
    dir_id = tracker.add_dir(
        path=cfg.path,
        alias=cfg.alias,
        ocr_lang=cfg.ocr_lang,
        exclude_patterns=cfg.exclude_patterns,
        include_exts=cfg.include_exts,
    )
    await refresh_watcher()
    # Kick off a scan for the new directory
    import asyncio
    asyncio.create_task(run_full_scan())
    return {"id": dir_id}


@router.put("/{dir_id}")
async def update_dir(dir_id: str, cfg: DirConfigUpdate):
    # TODO: implement update in tracker
    raise HTTPException(501, "Not yet implemented")


@router.delete("/{dir_id}")
async def delete_dir(dir_id: str):
    tracker.delete_dir(dir_id)
    await refresh_watcher()
    return {"status": "deleted"}


def _load_exclude_patterns() -> list[str]:
    """Load exclude patterns from settings."""
    import json
    from app.config import settings
    p = os.path.join(settings.data_dir, "settings.json")
    if os.path.isfile(p):
        try:
            data = json.load(open(p))
            raw = data.get("exclude_patterns", "")
            return [line.strip() for line in raw.split("\n") if line.strip()]
        except Exception:
            pass
    return []


def _matches_exclude(path: str, patterns: list[str]) -> bool:
    """Check if a path matches any exclude pattern."""
    fname = os.path.basename(path)
    for pat in patterns:
        if fnmatch.fnmatch(fname, pat) or fnmatch.fnmatch(path, pat):
            return True
    return False


@router.get("/{dir_id}/files")
async def list_dir_files(dir_id: str, status_filter: str = "all"):
    from app.service.scanner import scan_state
    status = scan_state

    excludes = _load_exclude_patterns()
    conn = tracker.get_db()
    where = ["dir_id = ?", "status = 'active'"]
    params: list = [dir_id]
    if status_filter == "indexed":
        where.append("indexed = 1")
    elif status_filter == "pending":
        where.append("indexed = 0")
    elif status_filter == "processing":
        where.append("indexed = 3")
    elif status_filter == "failed":
        where.append("indexed = 2")
    rows = conn.execute(
        f"""SELECT id, path, status, indexed, error_msg, mtime, size
           FROM file_tracking WHERE {' AND '.join(where)}
           ORDER BY path""",
        params,
    ).fetchall()
    conn.close()
    files = []
    for r in rows:
        d = dict(r)
        if excludes and _matches_exclude(d["path"], excludes):
            continue
        d["mtime"] = d["mtime"]
        files.append(d)
    return {"files": files, "scanner_status": status.get("status", "idle")}


class IndexFilesRequest(BaseModel):
    file_ids: list[str]


@router.post("/{dir_id}/index")
async def index_files(dir_id: str, req: IndexFilesRequest):
    """Trigger indexing for specific files in a directory."""
    from app.service.scanner import process_single_file

    results = []
    for fid in req.file_ids:
        entry = tracker.get_file_by_id(fid)
        if not entry or entry["dir_id"] != dir_id:
            results.append({"id": fid, "status": "skipped"})
            continue
        ok = await process_single_file(entry["path"], dir_id)
        results.append({"id": fid, "status": "ok" if ok else "failed"})
    return {"results": results}
