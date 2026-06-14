from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import CatalogDocument, Factory
from app.services.r2_client import R2Client


def catalog_dict(
    doc: CatalogDocument,
    factory: Factory | None = None,
    r2: R2Client | None = None,
) -> dict[str, Any]:
    resolved = (r2 or R2Client()).resolve_download_url(doc.file_url)
    return {
        "id": doc.id,
        "factory_id": doc.factory_id,
        "factory_code": factory.code if factory else "",
        "factory_name": factory.name_zh if factory else "",
        "title": doc.title,
        "title_en": doc.title_en,
        "category_l3": doc.category_l3,
        "file_url": doc.file_url,
        "download_url": resolved.get("download_url"),
        "download_mode": resolved.get("mode"),
        "file_size_mb": doc.file_size_mb,
        "pages": doc.pages,
        "authorized_emails": doc.authorized_emails or [],
        "notes": doc.notes,
        "storage": resolved.get("storage"),
        "storage_detail": resolved.get("detail"),
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
    }


async def seed_catalog_documents(db: AsyncSession) -> int:
    factories = await db.execute(select(Factory).order_by(Factory.code))
    rows = list(factories.scalars().all())
    if not rows:
        return 0
    seeds = [
        {
            "title": "2026 商用锅具目录",
            "title_en": "Commercial Cookware Catalog 2026",
            "category_l3": "cookware-commercial",
            "file_url": "r2://smart-crm/catalogs/cookware-2026.pdf",
            "pages": 48,
            "file_size_mb": 12.5,
            "authorized_emails": ["customer@example.com"],
        },
        {
            "title": "烘焙模具 OEM 图册",
            "title_en": "Bakeware OEM Catalog",
            "category_l3": "bakeware",
            "file_url": "r2://smart-crm/catalogs/bakeware-oem.pdf",
            "pages": 32,
            "file_size_mb": 8.2,
            "authorized_emails": ["customer@example.com", "buyer@hotel.com"],
        },
        {
            "title": "食品储存容器批发价目",
            "title_en": "Food Storage Wholesale Price List",
            "category_l3": "food-storage",
            "file_url": "r2://smart-crm/catalogs/food-storage-price.pdf",
            "pages": 16,
            "file_size_mb": 3.1,
            "authorized_emails": [],
        },
    ]
    created = 0
    for i, seed in enumerate(seeds):
        factory = rows[i % len(rows)]
        existing = await db.execute(
            select(CatalogDocument).where(
                CatalogDocument.factory_id == factory.id,
                CatalogDocument.title == seed["title"],
            )
        )
        if existing.scalar_one_or_none():
            continue
        db.add(
            CatalogDocument(
                factory_id=factory.id,
                title=seed["title"],
                title_en=seed["title_en"],
                category_l3=seed["category_l3"],
                file_url=seed["file_url"],
                pages=seed["pages"],
                file_size_mb=seed["file_size_mb"],
                authorized_emails=seed["authorized_emails"],
                notes="Phase 2 元数据种子 — PDF 待上传 R2",
            )
        )
        created += 1
    if created:
        await db.commit()
    return created


def customer_can_view(doc: CatalogDocument, email: str) -> bool:
    allowed = doc.authorized_emails or []
    if not allowed:
        return True
    return email.lower() in [e.lower() for e in allowed]
