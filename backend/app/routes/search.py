from fastapi import APIRouter, Query

from app.models.search import SearchResponse, SuggestResponse
from app.service import searcher
from app.service import tracker

router = APIRouter(prefix="/api", tags=["search"])


@router.get("/search", response_model=SearchResponse)
async def search(
    q: str = Query(..., description="Search query"),
    dir_ids: str = Query("", description="Comma-separated dir IDs"),
    types: str = Query("", description="Comma-separated file extensions"),
    date_from: str = Query("", description="ISO date filter start"),
    date_to: str = Query("", description="ISO date filter end"),
    sort: str = Query("score", description="Sort field: score|date|name"),
    order: str = Query("desc", description="sort order: desc|asc"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Results per page"),
):
    dir_list = [d.strip() for d in dir_ids.split(",") if d.strip()] if dir_ids else None
    type_list = [t.strip() for t in types.split(",") if t.strip()] if types else None

    result = searcher.search(q, dir_ids=dir_list, types=type_list, page=page, size=size, sort=sort, order=order)

    # Record history
    tracker.add_history(
        query=q,
        dir_ids=dir_ids,
        result_count=result.total,
    )

    return result


@router.get("/suggest", response_model=SuggestResponse)
async def suggest(
    q: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=50),
):
    import time
    start = time.time()
    suggestions = searcher.suggest(q, limit=limit)
    took_ms = int((time.time() - start) * 1000)
    return SuggestResponse(suggestions=suggestions, took_ms=took_ms)
