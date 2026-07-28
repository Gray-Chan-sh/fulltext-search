import csv
import io

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.models.search import SearchResponse
from app.service import searcher

router = APIRouter(prefix="/api", tags=["export"])


@router.get("/search/export")
async def export_csv(
    q: str = Query(..., description="Search query"),
    dir_ids: str = Query(""),
    types: str = Query(""),
    date_from: str = Query(""),
    date_to: str = Query(""),
):
    result = searcher.search(q, page=1, size=10000)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["filename", "path", "extension", "size", "score", "snippet"])
    for hit in result.hits:
        writer.writerow([
            hit.filename, hit.path, hit.extension,
            hit.size, hit.score, hit.snippet,
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=search-{q}.csv"},
    )


@router.get("/history")
async def list_history(limit: int = Query(50, le=200)):
    from app.service.tracker import list_history
    return {"history": list_history(limit)}


@router.delete("/history/{hid}")
async def delete_history(hid: str):
    from app.service.tracker import delete_history
    delete_history(hid)
    return {"status": "deleted"}


@router.post("/pin")
async def pin_result(data: dict):
    from app.service.tracker import pin_result
    hid = data.get("history_id", "")
    if hid:
        pin_result(hid)
    return {"status": "pinned"}
