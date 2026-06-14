from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import FileTransfer
from app.services.r2_client import R2Client


def file_dict(transfer: FileTransfer, r2: R2Client | None = None) -> dict[str, Any]:
    resolved = (r2 or R2Client()).resolve_download_url(transfer.file_url)
    return {
        "id": transfer.id,
        "title": transfer.title,
        "file_url": transfer.file_url,
        "file_size_mb": transfer.file_size_mb,
        "content_type": transfer.content_type,
        "customer_email": transfer.customer_email,
        "order_id": transfer.order_id,
        "created_by": transfer.created_by,
        "notes": transfer.notes,
        "download_url": resolved.get("download_url"),
        "storage": resolved.get("storage"),
        "created_at": transfer.created_at.isoformat() if transfer.created_at else None,
    }


async def seed_file_transfers(db: AsyncSession) -> int:
    existing = await db.execute(select(FileTransfer).limit(1))
    if existing.scalar_one_or_none():
        return 0
    db.add(
        FileTransfer(
            title="包装设计稿 v2 (演示)",
            file_url="r2://smart-crm/files/packaging-mock-v2.zip",
            file_size_mb=45.0,
            content_type="application/zip",
            customer_email="customer@example.com",
            created_by="sales@example.com",
            notes="Phase 3 大文件演示 — 待 R2 上传",
        )
    )
    await db.commit()
    return 1
