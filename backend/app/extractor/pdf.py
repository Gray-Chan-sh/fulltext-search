"""PDF extraction — per-page: embedded text if available, else raster + OCR."""


def page_info(path: str) -> list[dict]:
    """Return per-page info: text content and whether it needs OCR."""
    try:
        import fitz
        doc = fitz.open(path)
        pages: list[dict] = []
        for page in doc:
            text = page.get_text().strip()
            pages.append({"text": text, "needs_ocr": len(text) < 20})
        doc.close()
        return pages
    except Exception:
        return []


def extract_text_embedded(path: str) -> str:
    """Extract only embedded text from PDF (no OCR)."""
    try:
        import fitz
        doc = fitz.open(path)
        text = "\n".join(page.get_text() for page in doc)
        doc.close()
        return text.strip()
    except Exception:
        return ""


from app.config import settings


def render_page(path: str, page_index: int) -> bytes:
    """Render a single page as PNG bytes."""
    import fitz
    doc = fitz.open(path)
    page = doc[page_index]
    pix = page.get_pixmap(dpi=settings.ocr_dpi)
    data = pix.tobytes("png")
    doc.close()
    return data


def count_pages(path: str) -> int:
    try:
        import fitz
        doc = fitz.open(path)
        n = doc.page_count
        doc.close()
        return n
    except Exception:
        return 0