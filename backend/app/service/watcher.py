"""
Watchdog-based real-time file monitoring.

Processes files directly in the event loop (never blocks because OCR
runs in a dedicated thread pool).
"""

import asyncio
import os
import time

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from app.config import settings
from app.service.scanner import process_single_file, scanner_lock
from app.service import tracker
from app.service.tracker import add_log

_debounce: dict[str, float] = {}
_debounce_seconds = settings.scan_debounce_seconds
_watcher_observer: Observer | None = None
_watcher_dirs: set[str] = set()
_event_loop: asyncio.AbstractEventLoop | None = None
_ghost_cleanup_task: asyncio.Task | None = None


def set_event_loop(loop: asyncio.AbstractEventLoop):
    global _event_loop
    _event_loop = loop


def _run_async(coro):
    if _event_loop and _event_loop.is_running():
        asyncio.run_coroutine_threadsafe(coro, _event_loop)


class _Handler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory:
            _schedule(event.src_path)

    def on_modified(self, event):
        if not event.is_directory:
            _schedule(event.src_path)

    def on_deleted(self, event):
        if not event.is_directory:
            _handle_delete(event.src_path)

    def on_moved(self, event):
        if not event.is_directory:
            _handle_delete(event.src_path)
            _schedule(event.dest_path)


def _schedule(path: str):
    now = time.time()
    _debounce[path] = now
    add_log("INFO", f"文件变更: {os.path.basename(path)}", path, source="watcher")

    async def _delayed():
        await asyncio.sleep(_debounce_seconds)
        if _debounce.get(path, 0) != now:
            return
        _debounce.pop(path, None)
        if scanner_lock.locked():
            return
        dir_id = _find_dir_id(path)
        if dir_id:
            await process_single_file(path, dir_id)

    _run_async(_delayed())


def _handle_delete(path: str):
    entry = tracker.get_file_by_path(path)
    if entry:
        tracker.mark_deleted(path)
        add_log("INFO", f"文件删除: {os.path.basename(path)}", path, source="watcher")
        try:
            from app.service.indexer import get_writer, commit, delete_document
            writer = get_writer()
            delete_document(writer, entry["id"])
            commit(writer)
        except Exception:
            pass


def _find_dir_id(path: str) -> str | None:
    dirs = tracker.list_dirs()
    for d in dirs:
        d_path = os.path.normpath(d["path"])
        if path.startswith(d_path):
            return d["id"]
    return None


async def start_watcher():
    global _watcher_observer, _watcher_dirs, _ghost_cleanup_task
    if _watcher_observer:
        return
    dirs = tracker.list_dirs()
    paths = [d["path"] for d in dirs if os.path.isdir(d["path"])]
    if not paths:
        return
    _watcher_observer = Observer()
    handler = _Handler()
    for p in paths:
        _watcher_observer.schedule(handler, p, recursive=True)
        _watcher_dirs.add(p)
    _watcher_observer.start()

    # Start periodic ghost cleanup (catch deletions watchdog might miss on macOS Docker)
    async def _periodic_cleanup():
        while True:
            await asyncio.sleep(60)
            try:
                _cleanup_ghost_entries()
            except Exception:
                pass
    _ghost_cleanup_task = asyncio.create_task(_periodic_cleanup())


def _cleanup_ghost_entries():
    """Check tracked files still exist on disk; mark missing as deleted."""
    import os as _os
    dirs = tracker.list_dirs()
    count = 0
    for d in dirs:
        conn = tracker.get_db()
        rows = conn.execute(
            "SELECT id, path FROM file_tracking WHERE dir_id = ? AND status = 'active'",
            (d["id"],),
        ).fetchall()
        conn.close()
        for r in rows:
            if not _os.path.isfile(r["path"]):
                tracker.mark_deleted(r["path"])
                count += 1
    if count:
        add_log("INFO", f"看门狗清理了 {count} 个已删除文件", source="watcher")


async def stop_watcher():
    global _watcher_observer, _ghost_cleanup_task
    if _ghost_cleanup_task:
        _ghost_cleanup_task.cancel()
        _ghost_cleanup_task = None
    if _watcher_observer:
        _watcher_observer.stop()
        _watcher_observer.join()
        _watcher_observer = None
        _watcher_dirs.clear()


async def refresh_watcher():
    await stop_watcher()
    await start_watcher()