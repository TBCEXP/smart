from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.entities import PrepressReview
from app.services.artwork_diff import combined_verdict, image_diff, text_diff
from app.services.barcode_engine import validate_barcode


FIXTURE_SCHEME = "fixture://"


def fixture_dir() -> Path:
    return settings.data_dir / "fixtures" / "prepress"


def resolve_image_path(url: str) -> Path | None:
    if not url:
        return None
    if url.startswith(FIXTURE_SCHEME):
        return fixture_dir() / url.removeprefix(FIXTURE_SCHEME)
    if url.startswith("/"):
        p = Path(url)
        return p if p.exists() else None
    local = settings.data_dir / url
    if local.exists():
        return local
    return None


def ensure_fixture_images() -> tuple[Path, Path]:
    d = fixture_dir()
    d.mkdir(parents=True, exist_ok=True)
    ref = d / "ref_label.png"
    cand = d / "cand_label.png"
    if ref.exists() and cand.exists():
        return ref, cand
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        ref.touch()
        cand.touch()
        return ref, cand

    def _draw(path: Path, product_line: str, barcode_line: str) -> None:
        img = Image.new("RGB", (400, 200), "white")
        draw = ImageDraw.Draw(img)
        draw.rectangle((10, 10, 390, 190), outline="black", width=2)
        draw.text((20, 30), product_line, fill="black")
        draw.text((20, 80), "SKU: BK-DEMO-01", fill="black")
        draw.text((20, 120), barcode_line, fill="black")
        draw.rectangle((20, 150, 200, 180), fill="black")
        img.save(path)

    _draw(ref, "Commercial Bakeware Set", "EAN: 5901234123457")
    _draw(cand, "Commercial Bakeware Set", "EAN: 5901234123458")
    return ref, cand


def review_dict(review: PrepressReview) -> dict[str, Any]:
    result = review.result_json if isinstance(review.result_json, dict) else {}
    return {
        "id": review.id,
        "title": review.title,
        "order_id": review.order_id,
        "reference_image": review.reference_image,
        "candidate_image": review.candidate_image,
        "barcode_expected": review.barcode_expected,
        "barcode_symbology": review.barcode_symbology,
        "reference_text": review.reference_text,
        "candidate_text": review.candidate_text,
        "status": review.status,
        "verdict": review.verdict,
        "result": result,
        "created_by": review.created_by,
        "notes": review.notes,
        "created_at": review.created_at.isoformat() if review.created_at else None,
        "ran_at": review.ran_at.isoformat() if review.ran_at else None,
    }


def run_prepress_analysis(review: PrepressReview) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    barcode_check = validate_barcode(review.barcode_expected, review.barcode_symbology)
    barcode_check["check"] = "barcode"
    barcode_check["status"] = "pass" if barcode_check.get("valid") else "fail"
    checks.append(barcode_check)

    text_check = text_diff(review.reference_text, review.candidate_text)
    text_check["check"] = "text_diff"
    checks.append(text_check)

    ref_path = resolve_image_path(review.reference_image)
    cand_path = resolve_image_path(review.candidate_image)
    if ref_path and cand_path:
        img_check = image_diff(ref_path, cand_path)
    else:
        img_check = {"check": "image_diff", "status": "skipped", "detail": "无本地图片"}
    img_check["check"] = "image_diff"
    checks.append(img_check)

    verdict = combined_verdict(checks)
    return {
        "verdict": verdict,
        "checks": checks,
        "summary": {
            "barcode_ok": barcode_check.get("valid"),
            "text_similarity": text_check.get("similarity"),
            "pixel_diff_pct": img_check.get("pixel_diff_pct"),
        },
        "engine": "rule_based",
        "note": "规则引擎判定（非 LLM 一票否决）",
    }


async def seed_prepress_reviews(db: AsyncSession) -> int:
    existing = await db.execute(select(PrepressReview).limit(1))
    if existing.scalar_one_or_none():
        return 0
    ref, cand = ensure_fixture_images()
    db.add(
        PrepressReview(
            title="包装标签前稿比对 (演示)",
            barcode_expected="5901234123457",
            barcode_symbology="ean13",
            reference_text="Commercial Bakeware Set\nSKU: BK-DEMO-01\nMade in China",
            candidate_text="Commercial Bakeware Set\nSKU: BK-DEMO-01\nMade in Ch1na",
            reference_image=f"{FIXTURE_SCHEME}ref_label.png",
            candidate_image=f"{FIXTURE_SCHEME}cand_label.png",
            created_by="sales@example.com",
            notes="Phase 4 演示 — 点击「运行比对」查看 diff",
            status="draft",
        )
    )
    await db.commit()
    return 1
