"""
SQLite file tracking + content index.

Two tables:
  file_tracking  — per-path: (path, mtime, size, md5, status)
  content_index  — per-md5:  (md5, text_content, ocr_used, indexed_at)
  dir_config     — managed search directories
  search_history — recent queries
"""

import sqlite3
import time
import uuid
from pathlib import Path

from app.config import settings


def get_db() -> sqlite3.Connection:
    db_path = Path(settings.data_dir) / "tracker.db"
    conn = sqlite3.connect(str(db_path), timeout=60)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS file_tracking (
            id          TEXT PRIMARY KEY,
            path        TEXT NOT NULL UNIQUE,
            dir_id      TEXT NOT NULL,
            mtime       REAL NOT NULL,
            size        INTEGER NOT NULL,
            md5         TEXT,
            status      TEXT NOT NULL DEFAULT 'active',
            indexed     INTEGER NOT NULL DEFAULT 0,
            error_msg   TEXT,
            created_at  REAL NOT NULL,
            updated_at  REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_ft_dir_id ON file_tracking(dir_id);
        CREATE INDEX IF NOT EXISTS idx_ft_status ON file_tracking(status);
        CREATE INDEX IF NOT EXISTS idx_ft_md5    ON file_tracking(md5);

        CREATE TABLE IF NOT EXISTS content_index (
            md5             TEXT PRIMARY KEY,
            text_content    TEXT NOT NULL,
            indexed_at      REAL NOT NULL,
            char_count      INTEGER NOT NULL DEFAULT 0,
            ocr_used        INTEGER NOT NULL DEFAULT 0,
            ocr_duration_ms INTEGER
        );

        CREATE TABLE IF NOT EXISTS dir_config (
            id              TEXT PRIMARY KEY,
            path            TEXT NOT NULL UNIQUE,
            alias           TEXT,
            ocr_lang        TEXT NOT NULL DEFAULT 'ch',
            exclude_patterns TEXT,
            include_exts    TEXT,
            created_at      REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS search_history (
            id           TEXT PRIMARY KEY,
            query        TEXT NOT NULL,
            dir_ids      TEXT,
            filters      TEXT,
            result_count INTEGER,
            pinned       INTEGER NOT NULL DEFAULT 0,
            created_at   REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS scan_log (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            level     TEXT NOT NULL DEFAULT 'INFO',
            message   TEXT NOT NULL,
            source    TEXT NOT NULL DEFAULT '',
            file_path TEXT,
            duration_ms INTEGER,
            created_at REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_scan_log_level ON scan_log(level);
        CREATE INDEX IF NOT EXISTS idx_scan_log_time ON scan_log(created_at);
    """)
    conn.commit()
    conn.close()


# ─── file_tracking ───


def upsert_file(
    path: str, dir_id: str, mtime: float, size: int, md5: str | None = None,
) -> str:
    conn = get_db()
    now = time.time()
    existing = conn.execute(
        "SELECT id FROM file_tracking WHERE path = ?", (path,)
    ).fetchone()
    if existing:
        file_id = existing["id"]
        conn.execute(
            """UPDATE file_tracking SET mtime=?, size=?, md5=COALESCE(?,md5),
               status='active', updated_at=? WHERE id=?""",
            (mtime, size, md5, now, file_id),
        )
    else:
        file_id = str(uuid.uuid4())
        conn.execute(
            """INSERT INTO file_tracking (id,path,dir_id,mtime,size,md5,status,indexed,created_at,updated_at)
               VALUES (?,?,?,?,?,?,'active',0,?,?)""",
            (file_id, path, dir_id, mtime, size, md5, now, now),
        )
    conn.commit()
    conn.close()
    return file_id


def mark_deleted(path: str):
    conn = get_db()
    conn.execute("UPDATE file_tracking SET status='deleted', updated_at=? WHERE path=?",
                 (time.time(), path))
    conn.commit()
    conn.close()


def mark_processing(file_id: str):
    conn = get_db()
    conn.execute("UPDATE file_tracking SET indexed=3, error_msg=NULL, updated_at=? WHERE id=?",
                 (time.time(), file_id))
    conn.commit()
    conn.close()


def get_file_by_path(path: str) -> dict | None:
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM file_tracking WHERE path = ?", (path,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_file_by_id(file_id: str) -> dict | None:
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM file_tracking WHERE id = ?", (file_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_files_by_md5(md5: str) -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM file_tracking WHERE md5 = ? AND status = 'active'", (md5,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def unmark_deleted(path: str):
    """Re-activate a previously deleted path (same content restored)."""
    conn = get_db()
    conn.execute("UPDATE file_tracking SET status='active', updated_at=? WHERE path=?",
                 (time.time(), path))
    conn.commit()
    conn.close()


def remove_path(path: str):
    """Hard-delete a file_tracking row (file truly gone)."""
    conn = get_db()
    conn.execute("DELETE FROM file_tracking WHERE path = ?", (path,))
    conn.commit()
    conn.close()


def update_indexed(file_id: str, md5: str | None = None):
    conn = get_db()
    conn.execute(
        "UPDATE file_tracking SET indexed=1, md5=COALESCE(?,md5), updated_at=? WHERE id=?",
        (md5, time.time(), file_id),
    )
    conn.commit()
    conn.close()


def mark_failed(file_id: str, error: str):
    conn = get_db()
    conn.execute(
        "UPDATE file_tracking SET indexed=2, error_msg=?, updated_at=? WHERE id=?",
        (error, time.time(), file_id),
    )
    conn.commit()
    conn.close()


def count_files(dir_id: str | None = None) -> dict:
    conn = get_db()
    if dir_id:
        total = conn.execute(
            "SELECT COUNT(*) FROM file_tracking WHERE dir_id = ? AND status = 'active'", (dir_id,)
        ).fetchone()[0]
        indexed = conn.execute(
            "SELECT COUNT(*) FROM file_tracking WHERE indexed=1 AND dir_id = ? AND status = 'active'", (dir_id,)
        ).fetchone()[0]
        failed = conn.execute(
            "SELECT COUNT(*) FROM file_tracking WHERE indexed=2 AND dir_id = ? AND status = 'active'", (dir_id,)
        ).fetchone()[0]
        processing = conn.execute(
            "SELECT COUNT(*) FROM file_tracking WHERE indexed=3 AND dir_id = ? AND status = 'active'", (dir_id,)
        ).fetchone()[0]
    else:
        total = conn.execute("SELECT COUNT(*) FROM file_tracking WHERE status = 'active'").fetchone()[0]
        indexed = conn.execute("SELECT COUNT(*) FROM file_tracking WHERE indexed=1 AND status = 'active'").fetchone()[0]
        failed = conn.execute("SELECT COUNT(*) FROM file_tracking WHERE indexed=2 AND status = 'active'").fetchone()[0]
        processing = conn.execute("SELECT COUNT(*) FROM file_tracking WHERE indexed=3 AND status = 'active'").fetchone()[0]
    conn.close()
    return {"total": total, "indexed": indexed, "failed": failed, "processing": processing}


# ─── content_index ───


def store_content(md5: str, text: str, ocr_used: bool, ocr_ms: int | None = None):
    conn = get_db()
    conn.execute(
        """INSERT OR REPLACE INTO content_index (md5,text_content,indexed_at,char_count,ocr_used,ocr_duration_ms)
           VALUES (?,?,?,?,?,?)""",
        (md5, text, time.time(), len(text), int(ocr_used), ocr_ms),
    )
    conn.commit()
    conn.close()


def get_content(md5: str) -> dict | None:
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM content_index WHERE md5 = ?", (md5,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


# ─── dir_config ───


def add_dir(path: str, alias: str = "", ocr_lang: str = "ch",
            exclude_patterns: str = "", include_exts: str = "") -> str:
    conn = get_db()
    dir_id = str(uuid.uuid4())
    conn.execute(
        """INSERT INTO dir_config (id,path,alias,ocr_lang,exclude_patterns,include_exts,created_at)
           VALUES (?,?,?,?,?,?,?)""",
        (dir_id, path, alias, ocr_lang, exclude_patterns, include_exts, time.time()),
    )
    conn.commit()
    conn.close()
    return dir_id


def list_dirs() -> list[dict]:
    conn = get_db()
    rows = conn.execute("SELECT * FROM dir_config ORDER BY created_at").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_dir(dir_id: str):
    conn = get_db()
    conn.execute("DELETE FROM dir_config WHERE id = ?", (dir_id,))
    conn.execute("UPDATE file_tracking SET status='deleted' WHERE dir_id=?", (dir_id,))
    conn.commit()
    conn.close()


# ─── search_history ───


def add_history(query: str, dir_ids: str = "", filters: str = "",
                result_count: int = 0) -> str:
    conn = get_db()
    hid = str(uuid.uuid4())
    conn.execute(
        """INSERT INTO search_history (id,query,dir_ids,filters,result_count,created_at)
           VALUES (?,?,?,?,?,?)""",
        (hid, query, dir_ids, filters, result_count, time.time()),
    )
    conn.commit()
    conn.close()
    return hid


def list_history(limit: int = 50) -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM search_history ORDER BY pinned DESC, created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_history(hid: str):
    conn = get_db()
    conn.execute("DELETE FROM search_history WHERE id = ?", (hid,))
    conn.commit()
    conn.close()


def pin_result(hid: str):
    conn = get_db()
    conn.execute("UPDATE search_history SET pinned=1 WHERE id=?", (hid,))
    conn.commit()
    conn.close()


# ─── scan_log ───


def add_log(level: str, message: str, file_path: str | None = None,
            duration_ms: int | None = None, source: str = ""):
    for attempt in range(5):
        try:
            conn = get_db()
            conn.execute(
                "INSERT INTO scan_log (level,message,source,file_path,duration_ms,created_at) VALUES (?,?,?,?,?,?)",
                (level, message, source, file_path, duration_ms, time.time()),
            )
            conn.commit()
            conn.close()
            return
        except sqlite3.OperationalError as e:
            if "locked" in str(e) and attempt < 4:
                time.sleep(1)
                continue
            raise


def reset_stuck_processing():
    conn = get_db()
    n = conn.execute("UPDATE file_tracking SET indexed=0, updated_at=? WHERE indexed=3",
                     (time.time(),)).rowcount
    conn.commit()
    conn.close()
    if n:
        c2 = get_db()
        c2.execute("INSERT INTO scan_log (level,message,source,created_at) VALUES (?,?,?,?)",
                   ("INFO", f"重置了 {n} 个卡在\"正在索引\"状态的文件", "server", time.time()))
        c2.commit()
        c2.close()


def query_logs(level: str | None = None, source: str | None = None,
               q: str | None = None, limit: int = 200, offset: int = 0) -> list[dict]:
    conn = get_db()
    where = []
    params: list = []
    if level:
        where.append("level = ?")
        params.append(level)
    if source:
        where.append("source = ?")
        params.append(source)
    if q:
        where.append("(message LIKE ? OR file_path LIKE ?)")
        params.append(f"%{q}%")
        params.append(f"%{q}%")
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    rows = conn.execute(
        f"SELECT * FROM scan_log {clause} ORDER BY created_at DESC LIMIT ? OFFSET ?",
        params + [limit, offset],
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
