from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Data dirs (read-only mounts in Docker)
    data_dirs: list[str] = []

    # Index persistence
    index_dir: str = "index_data"
    data_dir: str = "data"

    # OCR
    ocr_lang: str = "ch"
    ocr_concurrent: int = 2
    ocr_fallback_tesseract: bool = True
    ocr_dpi: int = 100
    ocr_engine: str = "onnxruntime"

    # Scanner
    scheduled_scan_time: str = "00:00"
    scan_debounce_seconds: int = 3

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Tantivy
    tantivy_index_memory: int = 256  # MB

    model_config = {"env_prefix": "", "env_file": ".env", "extra": "ignore"}


settings = Settings()
