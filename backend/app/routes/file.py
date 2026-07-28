import io
import os
import zipfile

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from app.models.search import PreviewResponse, ContentResponse
from app.service import tracker

router = APIRouter(prefix="/api/file", tags=["file"])


@router.get("/{file_id}/preview", response_model=PreviewResponse)
async def preview_file(file_id: str):
    entry = tracker.get_file_by_id(file_id)
    if not entry:
        raise HTTPException(404, "File not found")

    content = tracker.get_content(entry["md5"]) if entry.get("md5") else None
    return PreviewResponse(
        id=file_id,
        content=content["text_content"] if content else "",
        char_count=content["char_count"] if content else 0,
        ocr_used=bool(content["ocr_used"]) if content else False,
        pages=0,
    )


@router.get("/{file_id}/download")
async def download_file(file_id: str):
    entry = tracker.get_file_by_id(file_id)
    if not entry:
        raise HTTPException(404, "File not found")
    path = entry["path"]
    if not os.path.isfile(path):
        raise HTTPException(404, "File no longer exists on disk")
    return FileResponse(path, filename=os.path.basename(path))


@router.get("/{file_id}/content", response_model=ContentResponse)
async def file_content(file_id: str):
    entry = tracker.get_file_by_id(file_id)
    if not entry:
        raise HTTPException(404, "File not found")

    content = tracker.get_content(entry["md5"]) if entry.get("md5") else None
    return ContentResponse(
        id=file_id,
        content=content["text_content"] if content else "",
        char_count=content["char_count"] if content else 0,
        ocr_used=bool(content["ocr_used"]) if content else False,
    )


class BatchDownloadRequest(BaseModel):
    file_ids: list[str]


@router.post("/batch-download")
async def batch_download(req: BatchDownloadRequest):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_id in req.file_ids:
            entry = tracker.get_file_by_id(file_id)
            if not entry:
                continue
            path = entry["path"]
            if not os.path.isfile(path):
                continue
            zf.write(path, os.path.basename(path))
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=search-results.zip"},
    )
