"""ZBar barcode scanner tests."""

from pathlib import Path

from app.services.barcode_scanner import (
    compare_scanned_barcode,
    decode_barcodes,
    zbar_available,
)
from app.services.prepress import ensure_barcode_fixture


def test_zbar_availability_is_bool():
    assert isinstance(zbar_available(), bool)


def test_decode_missing_file():
    out = decode_barcodes(Path("/nonexistent/barcode.png"))
    assert out["status"] == "skipped"
    assert out["engine"] == "none"


def test_decode_fixture_graceful():
    path = ensure_barcode_fixture()
    out = decode_barcodes(path)
    assert out["status"] in ("pass", "warn", "skipped", "error")
    if out["status"] == "pass" and out.get("count", 0) > 0:
        cmp = compare_scanned_barcode(out, "5901234123457", "ean13")
        assert cmp["check"] == "barcode_scan"
        assert cmp["status"] in ("pass", "fail")
