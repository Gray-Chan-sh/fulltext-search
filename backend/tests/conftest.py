import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def test_docs_dir():
    """Create a temporary directory with test documents."""
    with tempfile.TemporaryDirectory() as tmp:
        # Plain text
        (Path(tmp) / "hello.txt").write_text("Hello World FullText Search", encoding="utf-8")
        (Path(tmp) / "中文.txt").write_text("中文全文搜索测试", encoding="utf-8")
        # Subdir
        sub = Path(tmp) / "sub"
        sub.mkdir()
        (sub / "nested.txt").write_text("nested file content", encoding="utf-8")
        yield tmp


@pytest.fixture
def in_memory_db():
    """Provide a fresh in-memory SQLite connection for each test."""
    import sqlite3
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()
