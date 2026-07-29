"""
OCR pipeline: PaddleOCR with self-adjusting concurrency.

If OCR fails (likely OOM), automatically reduces concurrency.
"""

import io
import json
import os
import subprocess
import sys
import time

import cv2
import numpy as np
from PIL import Image

from app.config import settings

# Check if PaddlePaddle is available (may crash on CPUs without AVX)
# Lazy check — runs on first use, not at import time
_paddle_checked = False
_paddle_available = False


def _check_paddle() -> bool:
    global _paddle_checked, _paddle_available
    if _paddle_checked:
        return _paddle_available
    _paddle_checked = True
    # Check AVX support first (PaddlePaddle binary requires AVX)
    try:
        with open("/proc/cpuinfo") as f:
            if "avx" not in f.read().lower():
                _paddle_available = False
                return False
    except Exception:
        pass
    # Verify PaddleOCR can actually run (not just import)
    try:
        result = subprocess.run(
            [sys.executable, "-c",
             "from paddleocr import PaddleOCR; ocr = PaddleOCR(lang='ch', use_doc_orientation_classify=False, use_doc_unwarping=False, use_textline_orientation=False); print('ok')"],
            capture_output=True, timeout=30,
        )
        _paddle_available = result.returncode == 0 and result.stdout.strip() == b"ok"
    except Exception:
        _paddle_available = False
    return _paddle_available

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
    img = Image.open(io.BytesIO(image_bytes))
    arr = np.array(img)
    if len(arr.shape) == 2:
        arr = cv2.cvtColor(arr, cv2.COLOR_GRAY2RGB)
    elif arr.shape[2] == 4:
        arr = cv2.cvtColor(arr, cv2.COLOR_RGBA2RGB)

    # If PaddleOCR is not available (CPU lacks AVX), use Tesseract
    if not _check_paddle():
        if settings.ocr_fallback_tesseract:
            return _tesseract_fallback(arr)
        return "", 0

    # Check available memory against current effective concurrency
    avail_mb = _available_memory_mb()
    needed_mb = _current_concurrent * 400
    if avail_mb < needed_mb:
        _reduce_concurrency()
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


def _tesseract_fallback(image: np.ndarray) -> tuple[str, int]:
    """Fallback OCR using Tesseract."""
    start = time.time()
    try:
        import pytesseract
        text = pytesseract.image_to_string(image, lang=settings.ocr_lang + "+eng")
        elapsed = int((time.time() - start) * 1000)
        return text.strip(), elapsed
    except Exception:
        return "", int((time.time() - start) * 1000)


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