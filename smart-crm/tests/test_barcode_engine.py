"""Barcode engine tests."""

from app.services.barcode_engine import generate_barcode_svg, validate_barcode, validate_ean13


def test_ean13_valid():
    out = validate_ean13("5901234123457")
    assert out["valid"] is True


def test_ean13_invalid_checksum():
    out = validate_ean13("5901234123458")
    assert out["valid"] is False


def test_generate_barcode_svg():
    out = generate_barcode_svg("5901234123457", "ean13")
    assert out["ok"] is True
    assert "<svg" in out["svg"]
