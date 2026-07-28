"""Tests for the file tracker (SQLite layer)."""

from app.service.tracker import (
    init_db, upsert_file, get_file_by_path, mark_deleted,
    get_files_by_md5, store_content, get_content,
    add_dir, list_dirs, delete_dir,
    add_history, list_history,
)


def test_upsert_and_get(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.settings.data_dir", str(tmp_path))
    init_db()

    # Insert
    fid = upsert_file("/tmp/test.txt", "d1", 1000.0, 123, "abc123")
    row = get_file_by_path("/tmp/test.txt")
    assert row is not None
    assert row["path"] == "/tmp/test.txt"
    assert row["md5"] == "abc123"
    assert row["indexed"] == 0

    # Upsert (same path, new md5)
    upsert_file("/tmp/test.txt", "d1", 1001.0, 456, "def456")
    row = get_file_by_path("/tmp/test.txt")
    assert row["md5"] == "def456"


def test_mark_deleted(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.settings.data_dir", str(tmp_path))
    init_db()

    upsert_file("/tmp/doc.pdf", "d1", 1000.0, 999, "md5_1")
    mark_deleted("/tmp/doc.pdf")
    row = get_file_by_path("/tmp/doc.pdf")
    assert row["status"] == "deleted"


def test_content_dedup(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.settings.data_dir", str(tmp_path))
    init_db()

    store_content("md5_dup", "Hello World", ocr_used=False)
    content = get_content("md5_dup")
    assert content is not None
    assert content["text_content"] == "Hello World"

    # Overwrite
    store_content("md5_dup", "Updated", ocr_used=False)
    content = get_content("md5_dup")
    assert content["text_content"] == "Updated"


def test_dir_crud(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.settings.data_dir", str(tmp_path))
    init_db()

    did = add_dir("/data/docs", alias="文档", ocr_lang="ch")
    dirs = list_dirs()
    assert len(dirs) == 1
    assert dirs[0]["alias"] == "文档"

    delete_dir(did)
    dirs = list_dirs()
    assert len(dirs) == 0


def test_history(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.settings.data_dir", str(tmp_path))
    init_db()

    add_history("合同", result_count=42)
    add_history("报告", result_count=10)
    history = list_history()
    assert len(history) >= 2
    assert history[0]["query"] == "报告"  # most recent first
