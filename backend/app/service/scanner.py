"""Full directory scanner — orchestrates extraction → index for all files."""

import asyncio
import fnmatch
import hashlib
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from app.service.tracker import add_log

# Dedicated thread pool for CPU-bound OCR work (releases GIL in C extensions)
_ocr_thread_pool = ThreadPoolExecutor(max_workers=4)

from app.config import settings
from app.extractor import text as text_extractor
from app.extractor import office as office_extractor
from app.extractor import pdf as pdf_extractor
from app.extractor import ocr as ocr_extractor
from app.service import tracker
from app.service.indexer import add_document, commit, delete_document, get_writer

# Shared mutex — also checked by watcher and scheduler
scanner_lock = asyncio.Lock()

# Scanner state (for progress tracking)
scan_state: dict = {
    "status": "idle",
    "total": 0,
    "processed": 0,
    "errors": [],
    "started_at": 0.0,
    "processing_file": "",
    "processing_progress": "",
}


def _load_exclude_patterns() -> list[str]:
    """Load exclude patterns from settings."""
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
    fname = os.path.basename(path)
    for pat in patterns:
        if fnmatch.fnmatch(fname, pat) or fnmatch.fnmatch(path, pat):
            return True
    return False


async def run_full_scan():
    global scan_state
    if scanner_lock.locked():
        return

    async with scanner_lock:
        next_scheduled = scan_state.get("next_scheduled_scan", "")
        scan_state = {"status": "scanning", "total": 0, "processed": 0,
                       "errors": [], "started_at": time.time(),
                       "processing_file": "", "processing_progress": "",
                       "next_scheduled_scan": next_scheduled}
        add_log("INFO", "全量扫描开始", source="indexer")

        dirs = tracker.list_dirs()
        if not dirs:
            scan_state["status"] = "idle"
            return

        # Phase -1: clean up ghost entries (tracked files no longer on disk)
        ghost_count = 0
        for d in dirs:
            conn = tracker.get_db()
            rows = conn.execute(
                "SELECT id, path FROM file_tracking WHERE dir_id = ? AND status = 'active'",
                (d["id"],),
            ).fetchall()
            conn.close()
            for r in rows:
                if not os.path.isfile(r["path"]):
                    tracker.mark_deleted(r["path"])
                    ghost_count += 1
        if ghost_count:
            add_log("INFO", f"清理了 {ghost_count} 个已删除文件的追踪记录", source="indexer")

        # Count total files first
        all_files: list[tuple[str, str]] = []  # (path, dir_id)
        for d in dirs:
            d_path = d["path"]
            if not os.path.isdir(d_path):
                continue
            excludes = _load_exclude_patterns()
            for root, _, files in os.walk(d_path):
                for fname in files:
                    fpath = os.path.join(root, fname)
                    if excludes and _matches_exclude(fpath, excludes):
                        continue
                    all_files.append((fpath, d["id"]))

        scan_state["total"] = len(all_files)

        # Phase 0: register all files in tracking (so they appear in file tree immediately)
        for fpath, dir_id in all_files:
            try:
                stat = os.stat(fpath)
                existing = tracker.get_file_by_path(fpath)
                if not existing:
                    tracker.upsert_file(fpath, dir_id, stat.st_mtime, stat.st_size, None)
            except OSError:
                pass
        add_log("INFO", f"已注册 {len(all_files)} 个文件到追踪表", source="indexer")

        # Phase 1: extract all files (no writer, OCR can take time)
        extracted: list[dict] = []
        for fpath, dir_id in all_files:
            data = await _extract_file(fpath, dir_id)
            if data:
                extracted.append(data)
            scan_state["processed"] += 1

        # Phase 2: acquire writer once and batch index all files
        if extracted:
            writer = get_writer()
            try:
                for data in extracted:
                    _add_to_index(writer, **data)
                commit(writer)
            finally:
                pass
        add_log("INFO", f"全量扫描完成: {len(extracted)}/{len(all_files)} 个文件已索引", source="indexer")
        scan_state["status"] = "idle"
        scan_state["started_at"] = 0.0


async def process_single_file(path: str, dir_id: str) -> bool:
    if scanner_lock.locked():
        return False
    try:
        data = await _extract_file(path, dir_id)
        if data is None:
            return False
        from app.service.indexer import get_writer, commit as idx_commit
        writer = get_writer()
        _add_to_index(writer, **data)
        idx_commit(writer)
        return True
    except Exception:
        return False


async def _extract_file(path: str, dir_id: str) -> dict | None:
    global scan_state
    scan_state["processing_file"] = path
    if not os.path.isfile(path):
        scan_state["processing_file"] = ""
        return None
    excludes = _load_exclude_patterns()
    if excludes and _matches_exclude(path, excludes):
        scan_state["processing_file"] = ""
        return None
    try:
        stat = os.stat(path)
        mtime = stat.st_mtime
        size = stat.st_size

        existing = tracker.get_file_by_path(path)
        if existing and existing["mtime"] == mtime and existing["size"] == size:
            if existing["indexed"] == 1:
                return None

        md5 = _compute_md5(path, size)

        file_id = tracker.upsert_file(path, dir_id, mtime, size, md5)
        tracker.mark_processing(file_id)

        content = tracker.get_content(md5)
        if content and content["text_content"]:
            file_id = tracker.upsert_file(path, dir_id, mtime, size, md5)
            tracker.update_indexed(file_id, md5)
            return {
                "path": path, "file_id": file_id, "dir_id": dir_id,
                "md5": md5, "mtime": mtime, "size": size,
                "body": content["text_content"],
            }

        text, ocr_used, ocr_ms = await _extract_text(path)
        if not text.strip():
            tracker.upsert_file(path, dir_id, mtime, size, md5)
            text = ""
            add_log("WARNING", f"文件内容为空", path, source="extractor")

        if ocr_used:
            add_log("INFO", f"OCR 完成: {ocr_ms}ms, {len(text)} 字符", path, ocr_ms, source="ocr")
        else:
            add_log("INFO", f"文字提取完成: {len(text)} 字符", path, source="extractor")

        tracker.store_content(md5, text, ocr_used, ocr_ms)
        file_id = tracker.upsert_file(path, dir_id, mtime, size, md5)
        tracker.update_indexed(file_id, md5)
        scan_state["processing_file"] = ""
        return {
            "path": path, "file_id": file_id, "dir_id": dir_id,
            "md5": md5, "mtime": mtime, "size": size, "body": text,
        }
    except Exception as e:
        existing = tracker.get_file_by_path(path)
        if existing:
            tracker.mark_failed(existing["id"], str(e))
        add_log("ERROR", f"索引失败: {e}", path, source="indexer")
        scan_state["errors"].append(f"{path}: {e}")
        scan_state["processing_file"] = ""
        return None


async def _process_file(path: str, dir_id: str, writer) -> bool:
    """Extract text and index a single file. Returns True on success."""
    if not os.path.isfile(path):
        return False

    try:
        stat = os.stat(path)
        mtime = stat.st_mtime
        size = stat.st_size

        # Quick skip check
        existing = tracker.get_file_by_path(path)
        if existing and existing["mtime"] == mtime and existing["size"] == size:
            # No change, skip if already indexed
            if existing["indexed"] == 1:
                return True

        md5 = _compute_md5(path, size)

        # Check content dedup
        content = tracker.get_content(md5)
        if content and content["text_content"]:
            file_id = tracker.upsert_file(path, dir_id, mtime, size, md5)
            tracker.update_indexed(file_id, md5)
            _add_to_index(writer, path, file_id, dir_id, md5, mtime, size, body=content["text_content"])
            return True

        # Extract text
        text, ocr_used, ocr_ms = await _extract_text(path)

        if not text.strip():
            tracker.upsert_file(path, dir_id, mtime, size, md5)
            # Empty file — still index with empty body to track it
            text = ""

        # Store content
        tracker.store_content(md5, text, ocr_used, ocr_ms)

        # Update file tracking
        file_id = tracker.upsert_file(path, dir_id, mtime, size, md5)
        tracker.update_indexed(file_id, md5)

        # Index into Tantivy
        _add_to_index(writer, path, file_id, dir_id, md5, mtime, size, text)

        return True

    except Exception as e:
        existing = tracker.get_file_by_path(path)
        if existing:
            tracker.mark_failed(existing["id"], str(e))
        scan_state["errors"].append(f"{path}: {e}")
        return False


def _compute_md5(path: str, size: int) -> str:
    """Compute MD5 of file content. For large files >500MB, only hash first+last 64KB."""
    if size > 500 * 1024 * 1024:
        # Large file optimization: hash head + tail
        h = hashlib.md5()
        with open(path, "rb") as f:
            h.update(f.read(65536))
            f.seek(-65536, os.SEEK_END)
            h.update(f.read(65536))
        return h.hexdigest()
    else:
        h = hashlib.md5()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()


async def _extract_text(path: str) -> tuple[str, bool, int]:
    """Route file to correct extractor. Returns (text, ocr_used, duration_ms)."""
    ext = Path(path).suffix.lower()

    # Plain text
    if text_extractor.is_text_file(path):
        text = text_extractor.extract(path)
        return text, False, 0

    # Office
    if ext in office_extractor.SUPPORTED:
        text = office_extractor.extract(path)
        if text.strip():
            return text, False, 0

    # PDF — OCR only for files under 50MB (larger files get embedded text only)
    if ext == ".pdf":
        stat = os.stat(path)
        if stat.st_size > 50 * 1024 * 1024:
            text = await asyncio.get_event_loop().run_in_executor(
                None, pdf_extractor.extract_text_embedded, path
            )
            return text, False, 0
        return await _extract_pdf(path)

    # Image — OCR
    if ext in {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"}:
        with open(path, "rb") as f:
            img_bytes = f.read()
        text, ms = ocr_extractor.extract_from_image(img_bytes)
        return text, True, ms

    # Unknown — try as text, fall back to skip
    try:
        text = text_extractor.extract(path)
        if text.strip():
            return text, False, 0
    except Exception:
        pass
    return "", False, 0


async def _extract_pdf(path: str) -> tuple[str, bool, int]:
    global scan_state
    loop = asyncio.get_event_loop()
    total_pages = await loop.run_in_executor(_ocr_thread_pool, pdf_extractor.count_pages, path)
    from app.extractor.ocr import get_effective_concurrent
    ocr_concurrent = get_effective_concurrent()
    sem = asyncio.Semaphore(ocr_concurrent)
    results: list[str] = []
    total_ms = 0
    any_ocr = False

    for i in range(total_pages):
        scan_state["processing_progress"] = f"第 {i+1}/{total_pages} 页"
        text, needs_ocr = await loop.run_in_executor(
            _ocr_thread_pool, _page_text, path, i
        )
        if not needs_ocr and text.strip():
            results.append(text)
            add_log("INFO", f"第 {i+1}/{total_pages} 页: 直接提取 {len(text)} 字符",
                    os.path.basename(path), source="extractor")
        else:
            any_ocr = True
            async with sem:
                img_bytes = await loop.run_in_executor(
                    _ocr_thread_pool, pdf_extractor.render_page, path, i
                )
                page_text, ms = await loop.run_in_executor(
                    _ocr_thread_pool, ocr_extractor.extract_from_pdf_page, img_bytes
                )
                total_ms += ms
                results.append(page_text)
                if page_text.strip():
                    add_log("INFO", f"第 {i+1}/{total_pages} 页: OCR 完成 {ms}ms {len(page_text)} 字符",
                            os.path.basename(path), ms, source="ocr")

    return "\n".join(results), any_ocr, total_ms


def _page_text(path: str, page_index: int) -> tuple[str, bool]:
    """Extract text from a single page and check if it needs OCR."""
    import fitz
    doc = fitz.open(path)
    page = doc[page_index]
    text = page.get_text().strip()
    doc.close()
    return text, len(text) < 20


def _add_to_index(writer, path: str, file_id: str, dir_id: str, md5: str,
                  mtime: float, size: int, body: str = ""):
    """Add a document to the Tantivy index."""
    from datetime import datetime, timezone
    fname = os.path.basename(path)
    ext = Path(path).suffix.lower()
    doc = {
        "id": file_id,
        "file_id": file_id,
        "path": path,
        "filename": fname,
        "extension": ext,
        "dir_id": dir_id,
        "md5": md5,
        "title": fname,
        "body": body or "",
        "modified": datetime.fromtimestamp(mtime, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "size": size,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    # Delete old entry for this file_id if re-indexing
    add_document(writer, doc)
