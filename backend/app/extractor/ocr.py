"""
OCR pipeline: PaddleOCR with self-adjusting concurrency.

If OCR fails (likely OOM), automatically reduces concurrency.
"""

import io
import json
import os
import time

import cv2
import numpy as np
from PIL import Image

from app.config import settings

# Current effective concurrency (may be reduced from the user setting)
_current_concurrent = settings.ocr_concurrent


def _available_memory_mb() -> int:
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if "MemAvailable" in line:
                    return int(line.split()[1]) // 1024
    except Exception:
        pass
    return 9999


def _persist_reduced_concurrency():
    """Save the reduced concurrency to settings.json."""
    path = os.path.join(settings.data_dir, "settings.json")
    try:
        data = {}
        if os.path.isfile(path):
            with open(path) as f:
                data = json.load(f)
        data["ocr_concurrent"] = _current_concurrent
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def get_effective_concurrent() -> int:
    """Return the current effective OCR concurrency (auto-adjusted)."""
    global _current_concurrent
    # Re-read from settings if changed externally
    _current_concurrent = min(_current_concurrent, settings.ocr_concurrent)
    return max(1, _current_concurrent)


def extract_from_image(image_bytes: bytes) -> tuple[str, int]:
    """OCR an image. Returns (text, duration_ms). Auto-reduces concurrency on failure."""
    img = Image.open(io.BytesIO(image_bytes))
    arr = np.array(img)
    if len(arr.shape) == 2:
        arr = cv2.cvtColor(arr, cv2.COLOR_GRAY2RGB)
    elif arr.shape[2] == 4:
        arr = cv2.cvtColor(arr, cv2.COLOR_RGBA2RGB)

    # Check available memory against current effective concurrency
    avail_mb = _available_memory_mb()
    needed_mb = _current_concurrent * 400  # ~400MB per thread
    if avail_mb < needed_mb:
        _reduce_concurrency()
        # Retry with reduced concurrency — the caller must handle this
        from app.service.tracker import add_log
        add_log("WARNING", f"内存不足 ({avail_mb}MB), OCR 并发降至 {_current_concurrent}",
                source="ocr")

    start = time.time()
    try:
        ocr = _get_paddleocr()
        result = ocr.predict(arr)
        lines: list[str] = []
        for res in result:
            data = res.json
            texts = data.get("res", {}).get("rec_texts", [])
            for t in texts:
                if t.strip():
                    lines.append(t.strip())
        text = "\n".join(lines)
        elapsed = int((time.time() - start) * 1000)
        if text.strip():
            return text, elapsed
    except Exception as e:
        _reduce_concurrency()
        raise

    return "", int((time.time() - start) * 1000)


def _reduce_concurrency():
    """Reduce effective concurrency by 1, persist to settings."""
    global _current_concurrent
    if _current_concurrent <= 1:
        return
    _current_concurrent -= 1
    _persist_reduced_concurrency()
    from app.service.tracker import add_log
    add_log("WARNING", f"OCR 失败，并发数自动降至 {_current_concurrent}",
            source="ocr")


def extract_from_pdf_page(page_bytes: bytes) -> tuple[str, int]:
    return extract_from_image(page_bytes)


# Lazy-loaded PaddleOCR instance
_ocr = None


def _get_paddleocr():
    global _ocr
    if _ocr is None:
        from paddleocr import PaddleOCR
        _ocr = PaddleOCR(
            lang=settings.ocr_lang,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            engine=settings.ocr_engine,
        )
    return _ocr