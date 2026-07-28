"""Tests for text extractors."""

from app.extractor import text as text_extractor
from app.extractor import office as office_extractor


def test_text_extraction(tmp_path):
    f = tmp_path / "hello.txt"
    f.write_text("Hello World 中文测试", encoding="utf-8")
    assert text_extractor.is_text_file(str(f))
    result = text_extractor.extract(str(f))
    assert "Hello World" in result
    assert "中文测试" in result


def test_text_extensions():
    assert text_extractor.is_text_file("foo.py")
    assert text_extractor.is_text_file("bar.md")
    assert text_extractor.is_text_file("config.json")
    assert not text_extractor.is_text_file("archive.zip")
    assert not text_extractor.is_text_file("image.png")


def test_empty_text_file(tmp_path):
    f = tmp_path / "empty.txt"
    f.write_text("", encoding="utf-8")
    result = text_extractor.extract(str(f))
    assert result == ""


def test_office_unsupported():
    """Unsupported extensions return empty."""
    result = office_extractor.extract("archive.zip")
    assert result == ""
