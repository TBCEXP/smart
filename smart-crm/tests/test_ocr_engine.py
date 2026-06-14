"""OCR engine tests."""

from pathlib import Path

from app.services.ocr_engine import extract_text, tesseract_available
from app.services.prepress import ensure_fixture_images


def test_tesseract_availability_is_bool():
    assert isinstance(tesseract_available(), bool)


def test_extract_missing_file():
    out = extract_text(Path("/nonexistent/prepress.png"))
    assert out["status"] == "skipped"
    assert out["engine"] == "none"


def test_extract_fixture_graceful():
    ref, _ = ensure_fixture_images()
    out = extract_text(ref)
    assert out["status"] in ("pass", "skipped", "error")
    if out["status"] == "pass":
        assert out.get("chars", 0) > 0
