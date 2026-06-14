"""Photo alignment tests."""

from pathlib import Path

from app.services.photo_align import align_and_compare
from app.services.production_inspect import ensure_inspection_fixtures


def test_align_and_compare_runs():
    approved, photo = ensure_inspection_fixtures()
    out = align_and_compare(approved, photo)
    assert out.get("alignment") in ("orb_homography", "resize_fallback")
    assert out.get("diff_pct") is not None
