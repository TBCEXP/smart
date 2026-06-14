"""Tesseract OCR — optional label text extraction for prepress."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

_CACHED_AVAILABLE: bool | None = None


def tesseract_available() -> bool:
    """Return True when tesseract binary and pytesseract are usable."""
    global _CACHED_AVAILABLE
    if _CACHED_AVAILABLE is not None:
        return _CACHED_AVAILABLE
    if not shutil.which("tesseract"):
        _CACHED_AVAILABLE = False
        return False
    try:
        import pytesseract

        pytesseract.get_tesseract_version()
        _CACHED_AVAILABLE = True
    except Exception:
        _CACHED_AVAILABLE = False
    return _CACHED_AVAILABLE


def extract_text(image_path: Path) -> dict[str, Any]:
    """Extract text from an image; skips gracefully when OCR is unavailable."""
    if not image_path.exists():
        return {
            "status": "skipped",
            "detail": "file not found",
            "text": "",
            "engine": "none",
        }
    if not tesseract_available():
        return {
            "status": "skipped",
            "detail": "Tesseract not installed",
            "text": "",
            "engine": "none",
        }
    try:
        import pytesseract
        from PIL import Image

        text = pytesseract.image_to_string(Image.open(image_path)).strip()
        return {
            "status": "pass",
            "text": text,
            "engine": "tesseract",
            "chars": len(text),
        }
    except Exception as exc:
        return {
            "status": "error",
            "detail": str(exc)[:200],
            "text": "",
            "engine": "tesseract",
        }
