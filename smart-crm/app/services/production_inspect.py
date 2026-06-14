from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.entities import ProductionInspection
from app.services.artwork_diff import combined_verdict
from app.services.photo_align import align_and_compare
from app.services.prepress import resolve_image_path


def resolve_inspection_image(url: str) -> Path | None:
    if not url:
        return None
    if url.startswith("fixture://inspection/"):
        name = url.replace("fixture://inspection/", "")
        return inspection_fixture_dir() / name
    return resolve_image_path(url)


def inspection_fixture_dir() -> Path:
    return settings.data_dir / "fixtures" / "inspection"


def ensure_inspection_fixtures() -> tuple[Path, Path]:
    d = inspection_fixture_dir()
    d.mkdir(parents=True, exist_ok=True)
    approved = d / "approved_box.png"
    photo = d / "production_photo.png"
    if approved.exists() and photo.exists():
        return approved, photo
    try:
        import cv2
        import numpy as np
    except ImportError:
        approved.touch()
        photo.touch()
        return approved, photo

    base = np.ones((320, 480, 3), dtype=np.uint8) * 245
    cv2.rectangle(base, (40, 40), (440, 280), (30, 30, 30), 2)
    cv2.putText(base, "APPROVED ARTWORK", (60, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (20, 20, 20), 2)
    cv2.putText(base, "SKU: BK-DEMO-01", (60, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (20, 20, 20), 1)
    cv2.rectangle(base, (60, 200), (220, 240), (0, 0, 0), -1)
    cv2.imwrite(str(approved), base)

    # 实拍：轻微旋转 + 小瑕疵红点
    center = (240, 160)
    matrix = cv2.getRotationMatrix2D(center, 4.0, 1.0)
    rotated = cv2.warpAffine(base, matrix, (480, 320), borderValue=(250, 250, 250))
    cv2.circle(rotated, (350, 220), 8, (0, 0, 220), -1)
    cv2.imwrite(str(photo), rotated)
    return approved, photo


def inspection_dict(row: ProductionInspection) -> dict[str, Any]:
    result = row.result_json if isinstance(row.result_json, dict) else {}
    return {
        "id": row.id,
        "title": row.title,
        "order_id": row.order_id,
        "prepress_review_id": row.prepress_review_id,
        "approved_image": row.approved_image,
        "photo_image": row.photo_image,
        "status": row.status,
        "verdict": row.verdict,
        "human_review_status": row.human_review_status,
        "human_review_notes": row.human_review_notes,
        "human_reviewed_by": row.human_reviewed_by,
        "result": result,
        "created_by": row.created_by,
        "notes": row.notes,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "ran_at": row.ran_at.isoformat() if row.ran_at else None,
        "human_reviewed_at": row.human_reviewed_at.isoformat() if row.human_reviewed_at else None,
    }


def run_production_analysis(row: ProductionInspection) -> dict[str, Any]:
    approved_path = resolve_inspection_image(row.approved_image)
    photo_path = resolve_inspection_image(row.photo_image)
    if approved_path and photo_path:
        align_check = align_and_compare(approved_path, photo_path)
    else:
        align_check = {
            "check": "photo_align",
            "status": "skipped",
            "detail": "无本地图片",
        }
    align_check["check"] = "photo_align"
    verdict = combined_verdict([align_check])
    return {
        "verdict": verdict,
        "checks": [align_check],
        "summary": {
            "diff_pct": align_check.get("diff_pct"),
            "alignment": align_check.get("alignment"),
            "match_inliers": align_check.get("match_inliers"),
        },
        "engine": "opencv_align",
        "note": "OpenCV 对齐后与确稿比对；需人工终审确认",
        "requires_human_review": True,
    }


async def seed_production_inspections(db: AsyncSession) -> int:
    existing = await db.execute(select(ProductionInspection).limit(1))
    if existing.scalar_one_or_none():
        return 0
    ensure_inspection_fixtures()
    from app.models.entities import PrepressReview

    prepress_id = None
    prepress_row = await db.execute(select(PrepressReview).limit(1))
    prepress = prepress_row.scalar_one_or_none()
    if prepress:
        prepress_id = prepress.id
    db.add(
        ProductionInspection(
            title="大货包装实拍抽检 (演示)",
            prepress_review_id=prepress_id,
            approved_image="fixture://inspection/approved_box.png",
            photo_image="fixture://inspection/production_photo.png",
            created_by="sales@example.com",
            notes="Phase 5 演示 — 关联前稿任务后运行检测 + 人工终审",
            status="draft",
            human_review_status="pending",
        )
    )
    await db.commit()
    return 1
