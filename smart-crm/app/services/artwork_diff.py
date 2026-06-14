from __future__ import annotations

import difflib
from pathlib import Path
from typing import Any


def text_diff(reference: str, candidate: str) -> dict[str, Any]:
    ref_lines = (reference or "").splitlines()
    cand_lines = (candidate or "").splitlines()
    diff = list(difflib.unified_diff(ref_lines, cand_lines, lineterm=""))
    changed = [ln for ln in diff if ln.startswith(("+", "-")) and not ln.startswith(("+++", "---"))]
    total = max(len(ref_lines), len(cand_lines), 1)
    ratio = len(changed) / (total * 2)
    similar = difflib.SequenceMatcher(None, reference or "", candidate or "").ratio()
    status = "pass"
    if similar < 0.95:
        status = "warn"
    if similar < 0.85:
        status = "fail"
    return {
        "status": status,
        "similarity": round(similar, 4),
        "changed_lines": len(changed),
        "diff_preview": "\n".join(diff[:40]),
    }


def image_diff(reference_path: Path, candidate_path: Path) -> dict[str, Any]:
    try:
        from PIL import Image, ImageChops, ImageStat
    except ImportError:
        return {
            "status": "skipped",
            "detail": "Pillow 未安装",
            "pixel_diff_pct": None,
        }

    if not reference_path.exists() or not candidate_path.exists():
        return {
            "status": "skipped",
            "detail": "图片文件不存在",
            "pixel_diff_pct": None,
        }

    ref = Image.open(reference_path).convert("RGB")
    cand = Image.open(candidate_path).convert("RGB")
    size = (min(ref.width, cand.width), min(ref.height, cand.height))
    ref = ref.resize(size)
    cand = cand.resize(size)
    diff_img = ImageChops.difference(ref, cand)
    stat = ImageStat.Stat(diff_img)
    mean_delta = sum(stat.mean) / 3.0
    pixel_diff_pct = round(mean_delta / 255.0 * 100.0, 2)
    status = "pass"
    if pixel_diff_pct > 2.0:
        status = "warn"
    if pixel_diff_pct > 8.0:
        status = "fail"
    return {
        "status": status,
        "pixel_diff_pct": pixel_diff_pct,
        "size": {"width": size[0], "height": size[1]},
        "detail": f"像素差异 {pixel_diff_pct}%",
    }


def combined_verdict(checks: list[dict[str, Any]]) -> str:
    statuses = [c.get("status") for c in checks if c.get("status") not in (None, "skipped")]
    if any(s == "fail" for s in statuses):
        return "failed"
    if any(s == "warn" for s in statuses):
        return "warnings"
    if statuses:
        return "passed"
    return "pending"
