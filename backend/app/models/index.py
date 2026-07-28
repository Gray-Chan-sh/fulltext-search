from pydantic import BaseModel


class IndexStatusResponse(BaseModel):
    total_files: int = 0
    indexed: int = 0
    pending: int = 0
    failed: int = 0
    scanner_status: str = "idle"
    progress_percent: float = 0.0
    last_full_scan: str = ""
    next_scheduled_scan: str = ""
    processing_file: str = ""
    processing_progress: str = ""


class TriggerResponse(BaseModel):
    status: str
    message: str = ""


class ExcludeConfig(BaseModel):
    patterns: list[str] = []
