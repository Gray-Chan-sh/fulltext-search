from pydantic import BaseModel


class DirConfigCreate(BaseModel):
    path: str
    alias: str = ""
    ocr_lang: str = "ch"
    exclude_patterns: str = ""
    include_exts: str = ""


class DirConfigUpdate(BaseModel):
    alias: str | None = None
    ocr_lang: str | None = None
    exclude_patterns: str | None = None
    include_exts: str | None = None


class DirConfigResponse(BaseModel):
    id: str
    path: str
    alias: str = ""
    ocr_lang: str = "ch"
    exclude_patterns: str = ""
    include_exts: str = ""
    file_count: int = 0
    indexed_count: int = 0
    failed_count: int = 0
    processing_count: int = 0
    status: str = "idle"


class DirListResponse(BaseModel):
    dirs: list[DirConfigResponse] = []
