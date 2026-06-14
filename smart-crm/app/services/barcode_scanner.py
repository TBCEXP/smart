"""ZBar barcode scanning from images — optional prepress check."""

from __future__ import annotations

from pathlib import Path
from typing import Any

_CACHED_AVAILABLE: bool | None = None


def zbar_available() -> bool:
    """Return True when pyzbar and libzbar are usable."""
    global _CACHED_AVAILABLE
    if _CACHED_AVAILABLE is not None:
        return _CACHED_AVAILABLE
    try:
        from pyzbar.pyzbar import decode  # noqa: F401

        _CACHED_AVAILABLE = True
    except Exception:
        _CACHED_AVAILABLE = False
    return _CACHED_AVAILABLE


def decode_barcodes(image_path: Path) -> dict[str, Any]:
    """Decode barcodes from an image; skips gracefully when zbar is unavailable."""
    if not image_path.exists():
        return {
            "status": "skipped",
            "detail": "file not found",
            "values": [],
            "engine": "none",
        }
    if not zbar_available():
        return {
            "status": "skipped",
            "detail": "pyzbar/zbar not installed",
            "values": [],
            "engine": "none",
        }
    try:
        from PIL import Image
        from pyzbar.pyzbar import decode

        results = decode(Image.open(image_path))
        values = [
            {
                "type": item.type,
                "value": item.data.decode("utf-8", errors="replace"),
            }
            for item in results
        ]
        return {
            "status": "pass" if values else "warn",
            "detail": "no barcode detected" if not values else f"{len(values)} barcode(s)",
            "values": values,
            "engine": "zbar",
            "count": len(values),
        }
    except Exception as exc:
        return {
            "status": "error",
            "detail": str(exc)[:200],
            "values": [],
            "engine": "zbar",
        }


def compare_scanned_barcode(
    scan: dict[str, Any], expected: str, symbology: str = "ean13"
) -> dict[str, Any]:
    """Compare zbar scan results against expected barcode value."""
    from app.services.barcode_engine import validate_barcode

    if scan.get("status") == "skipped":
        return {
            "check": "barcode_scan",
            "status": "skipped",
            "detail": scan.get("detail", "scan skipped"),
            "engine_available": zbar_available(),
        }
    if scan.get("status") == "error":
        return {
            "check": "barcode_scan",
            "status": "fail",
            "detail": scan.get("detail", "scan error"),
        }

    values = scan.get("values") or []
    if not values:
        return {
            "check": "barcode_scan",
            "status": "warn",
            "detail": "图片中未识别到条码",
            "expected": expected,
        }

    found = values[0].get("value", "")
    expected_norm = validate_barcode(expected, symbology).get("value", expected)
    found_norm = validate_barcode(found, symbology).get("value", found)
    match = bool(expected_norm and found_norm and expected_norm == found_norm)
    return {
        "check": "barcode_scan",
        "status": "pass" if match else "fail",
        "expected": expected_norm or expected,
        "found": found_norm or found,
        "symbology": symbology,
        "detail": "扫码与期望值一致" if match else f"扫码 {found_norm or found} ≠ 期望 {expected_norm or expected}",
        "all_values": values,
    }
