import os
import re
from functools import lru_cache

import jieba
import tantivy

from app.config import settings

_INDEX_DIR = settings.index_dir


def _schema() -> tantivy.Schema:
    builder = tantivy.SchemaBuilder()
    builder.add_text_field("id", stored=True, tokenizer_name="raw")
    builder.add_text_field("file_id", stored=True, tokenizer_name="raw")
    builder.add_text_field("path", stored=True, tokenizer_name="raw")
    builder.add_text_field("filename", stored=True)
    builder.add_text_field("extension", stored=True, tokenizer_name="raw")
    builder.add_text_field("dir_id", stored=True, tokenizer_name="raw")
    builder.add_text_field("dir_name", stored=True)
    builder.add_text_field("md5", stored=True, tokenizer_name="raw")
    builder.add_text_field("title", stored=True)
    builder.add_text_field("body", stored=True)
    builder.add_text_field("modified", stored=True)
    builder.add_integer_field("size", stored=True, fast=True)
    builder.add_text_field("created_at", stored=True)
    return builder.build()


def get_index() -> tantivy.Index:
    os.makedirs(_INDEX_DIR, exist_ok=True)
    return tantivy.Index(_schema(), path=_INDEX_DIR)


def get_writer() -> tantivy.IndexWriter:
    idx = get_index()
    return idx.writer(settings.tantivy_index_memory * 1_000_000)


_RE_CJK = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]+")


def _segment(text: str) -> str:
    """Insert spaces between CJK words for better Tantivy indexing."""
    def _replace(m):
        return " " + " ".join(jieba.cut_for_search(m.group())) + " "
    return _RE_CJK.sub(_replace, text).strip()


def doc_from_dict(data: dict) -> tantivy.Document:
    doc = tantivy.Document()
    for key, value in data.items():
        if value is None:
            continue
        if key == "size":
            doc.add_integer(key, value)
        elif key == "body":
            doc.add_text(key, _segment(str(value)))
        else:
            doc.add_text(key, str(value))
    return doc


def add_document(writer: tantivy.IndexWriter, data: dict):
    doc = doc_from_dict(data)
    writer.add_document(doc)


def delete_document(writer: tantivy.IndexWriter, file_id: str):
    writer.delete_documents("file_id", file_id)


def commit(writer: tantivy.IndexWriter):
    writer.commit()
