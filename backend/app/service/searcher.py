import time

import tantivy

from app.models.search import Hit, SearchFacets, SearchResponse


def _segment_query(q: str) -> str:
    from app.service.indexer import _segment
    return _segment(q)


def search(
    q: str,
    dir_ids: list[str] | None = None,
    types: list[str] | None = None,
    page: int = 1,
    size: int = 20,
    sort: str = "score",
    order: str = "desc",
) -> SearchResponse:
    from app.service.indexer import get_index
    idx = get_index()
    idx.reload()
    searcher = idx.searcher()

    start = time.time()
    try:
        query = idx.parse_query(_segment_query(q), ["title", "body"])
    except ValueError:
        return SearchResponse(
            total=0, page=page, size=size, took_ms=0, hits=[],
            facets=SearchFacets(types={}, dirs={}),
        )
    top_k = page * size
    result = searcher.search(query, limit=top_k)
    took_ms = int((time.time() - start) * 1000)

    offset = (page - 1) * size
    hits_raw = result.hits[offset:offset + size]

    hits: list[Hit] = []

    for score, doc_address in hits_raw:
        doc = searcher.doc(doc_address)
        if doc is None:
            continue
        doc_dict = _doc_to_dict(doc)
        hit = Hit(
            id=doc_dict.get("file_id", ""),
            filename=doc_dict.get("filename", ""),
            path=doc_dict.get("path", ""),
            dir_id=doc_dict.get("dir_id", ""),
            dir_name=doc_dict.get("dir_name", ""),
            snippet=_make_snippet(doc_dict.get("body", ""), q),
            size=int(doc_dict.get("size", 0)),
            extension=doc_dict.get("extension", ""),
            modified=doc_dict.get("modified", ""),
            score=round(score, 4),
        )
        hits.append(hit)

    if sort == "date":
        hits.sort(key=lambda h: h.modified, reverse=(order == "desc"))
    elif sort == "name":
        hits.sort(key=lambda h: h.filename.lower(), reverse=(order == "desc"))
    elif sort == "size":
        hits.sort(key=lambda h: h.size, reverse=(order == "desc"))
    elif sort == "type":
        hits.sort(key=lambda h: h.extension, reverse=(order == "desc"))

    type_counts: dict[str, int] = {}
    dir_counts: dict[str, dict] = {}
    for hit in hits:
        if hit.extension:
            type_counts[hit.extension] = type_counts.get(hit.extension, 0) + 1
        if hit.dir_id:
            if hit.dir_id not in dir_counts:
                dir_counts[hit.dir_id] = {"name": hit.dir_name, "count": 0}
            dir_counts[hit.dir_id]["count"] += 1

    return SearchResponse(
        total=len(result.hits),
        page=page,
        size=size,
        took_ms=took_ms,
        hits=hits,
        facets=SearchFacets(types=type_counts, dirs=dir_counts),
    )


def _doc_to_dict(doc: tantivy.Document) -> dict:
    result = {}
    for field in ["id", "file_id", "path", "filename", "extension", "dir_id",
                   "dir_name", "md5", "title", "body", "modified", "created_at"]:
        try:
            vals = doc[field]
            if isinstance(vals, list) and len(vals) > 0:
                result[field] = str(vals[0])
            elif vals is not None:
                result[field] = str(vals)
        except (KeyError, TypeError):
            pass
    try:
        size_vals = doc["size"]
        if isinstance(size_vals, list) and len(size_vals) > 0:
            result["size"] = str(size_vals[0])
    except (KeyError, TypeError):
        result["size"] = "0"
    return result


def _make_snippet(text: str, query: str, max_chars: int = 200) -> str:
    if not text:
        return ""
    q = query.lower()
    lower_text = text.lower()
    idx = lower_text.find(q)
    if idx == -1:
        return text[:max_chars] + "..." if len(text) > max_chars else text
    start = max(0, idx - 60)
    end = min(len(text), idx + len(q) + 80)
    snippet = text[start:end]
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."
    return snippet[:max_chars + 6]


def suggest(q: str, limit: int = 10) -> list[str]:
    from app.service.indexer import get_index
    try:
        idx = get_index()
        idx.reload()
        searcher = idx.searcher()
        query = idx.parse_query(_segment_query(q), ["title", "body"])
        result = searcher.search(query, limit=limit)
        suggestions: list[str] = []
        seen: set[str] = set()
        for _, doc_address in result.hits:
            doc = searcher.doc(doc_address)
            if doc is None:
                continue
            doc_dict = _doc_to_dict(doc)
            title = doc_dict.get("title", "").strip()
            if title and title.lower() not in seen:
                suggestions.append(title)
                seen.add(title.lower())
            if len(suggestions) >= limit:
                break
        return suggestions
    except Exception:
        return []