from __future__ import annotations

import re
from io import BytesIO
from typing import Any


def _ean13_checksum(digits: str) -> int:
    total = 0
    for i, ch in enumerate(digits[:12]):
        n = int(ch)
        total += n * (1 if i % 2 == 0 else 3)
    return (10 - (total % 10)) % 10


def validate_ean13(value: str) -> dict[str, Any]:
    cleaned = re.sub(r"\D", "", value)
    if len(cleaned) != 13:
        return {"valid": False, "symbology": "ean13", "detail": "EAN-13 须为 13 位数字"}
    expected = _ean13_checksum(cleaned)
    actual = int(cleaned[12])
    ok = expected == actual
    return {
        "valid": ok,
        "symbology": "ean13",
        "value": cleaned,
        "checksum_expected": expected,
        "checksum_actual": actual,
        "detail": "校验通过" if ok else f"校验位错误（期望 {expected}，实际 {actual}）",
    }


def validate_code128(value: str) -> dict[str, Any]:
    if not value or len(value) > 80:
        return {"valid": False, "symbology": "code128", "detail": "Code128 长度 1–80"}
    if not re.fullmatch(r"[\x20-\x7E]+", value):
        return {"valid": False, "symbology": "code128", "detail": "含不可编码字符"}
    return {"valid": True, "symbology": "code128", "value": value, "detail": "字符集合法"}


def validate_barcode(value: str, symbology: str = "ean13") -> dict[str, Any]:
    sym = (symbology or "ean13").lower()
    if sym in ("ean13", "ean-13", "gtin13"):
        return validate_ean13(value)
    if sym in ("code128", "code-128"):
        return validate_code128(value)
    return {"valid": False, "symbology": sym, "detail": f"不支持的条码类型: {symbology}"}


def generate_barcode_svg(value: str, symbology: str = "ean13") -> dict[str, Any]:
    check = validate_barcode(value, symbology)
    if not check.get("valid"):
        return {"ok": False, "detail": check.get("detail"), "validation": check}
    sym = (symbology or "ean13").lower()
    try:
        import barcode
        from barcode.writer import SVGWriter

        code_cls = "ean13" if sym.startswith("ean") else "code128"
        code_value = check.get("value", value)
        if code_cls == "ean13":
            code_value = code_value[:12]
        writer = SVGWriter()
        code = barcode.get(code_cls, code_value, writer=writer)
        buf = BytesIO()
        code.write(buf, options={"write_text": True})
        svg = buf.getvalue().decode("utf-8")
        return {
            "ok": True,
            "symbology": code_cls,
            "value": check.get("value", value),
            "svg": svg,
            "validation": check,
        }
    except Exception as exc:
        return {"ok": False, "detail": str(exc)[:200], "validation": check}
