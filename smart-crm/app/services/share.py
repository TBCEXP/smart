from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import CatalogDocument, Factory, FileTransfer, SalesOrder, SalesOrderLine, ShareLink
from app.services.catalog import catalog_dict
from app.services.files import file_dict
from app.services.phase1 import order_dict


def _new_token() -> str:
    return secrets.token_urlsafe(16)


async def create_share_link(
    db: AsyncSession,
    resource_type: str,
    resource_id: str,
    customer_email: str = "",
    created_by: str = "",
    ttl_days: int = 14,
) -> ShareLink:
    link = ShareLink(
        token=_new_token(),
        resource_type=resource_type,
        resource_id=resource_id,
        customer_email=customer_email,
        created_by=created_by,
        expires_at=datetime.utcnow() + timedelta(days=max(1, ttl_days)),
    )
    db.add(link)
    await db.commit()
    await db.refresh(link)
    return link


async def resolve_share(db: AsyncSession, token: str) -> dict[str, Any]:
    result = await db.execute(
        select(ShareLink).where(ShareLink.token == token, ShareLink.active.is_(True))
    )
    link = result.scalar_one_or_none()
    if not link:
        return {"valid": False, "detail": "链接无效或已过期"}
    if link.expires_at and link.expires_at < datetime.utcnow():
        return {"valid": False, "detail": "分享链接已过期"}
    link.view_count += 1
    await db.commit()

    payload: dict[str, Any] = {
        "valid": True,
        "token": link.token,
        "resource_type": link.resource_type,
        "resource_id": link.resource_id,
        "customer_email": link.customer_email,
        "expires_at": link.expires_at.isoformat() if link.expires_at else None,
    }
    if link.resource_type == "order":
        order = await db.get(SalesOrder, link.resource_id)
        if not order:
            payload["valid"] = False
            payload["detail"] = "订单不存在"
            return payload
        lines = await db.execute(
            select(SalesOrderLine).where(SalesOrderLine.order_id == order.id)
        )
        payload["order"] = order_dict(order, list(lines.scalars().all()))
    elif link.resource_type == "factories":
        rows = await db.execute(select(Factory).where(Factory.active.is_(True)))
        payload["factories"] = [
            {
                "code": f.code,
                "name_zh": f.name_zh,
                "name_en": f.name_en,
                "category_focus": f.category_focus,
                "moq_default": f.moq_default,
            }
            for f in rows.scalars().all()
        ]
    elif link.resource_type == "catalog":
        doc = await db.get(CatalogDocument, link.resource_id)
        if not doc or not doc.active:
            payload["valid"] = False
            payload["detail"] = "目录不存在"
            return payload
        factory = await db.get(Factory, doc.factory_id)
        payload["catalog"] = catalog_dict(doc, factory)
    elif link.resource_type == "file":
        transfer = await db.get(FileTransfer, link.resource_id)
        if not transfer or not transfer.active:
            payload["valid"] = False
            payload["detail"] = "文件不存在"
            return payload
        payload["file"] = file_dict(transfer)
    return payload


async def seed_portal_demo(db: AsyncSession) -> None:
    """为客户门户演示种子一条订单。"""
    from app.services.phase1 import next_order_no

    existing = await db.execute(
        select(SalesOrder).where(SalesOrder.customer_email == "customer@example.com")
    )
    if existing.scalar_one_or_none():
        return
    order = SalesOrder(
        order_no=next_order_no(),
        customer_name="Demo Hotel Group",
        customer_email="customer@example.com",
        country_iso="MX",
        status="confirmed",
        currency="USD",
        total_amount=250.0,
        assigned_to="sales@example.com",
        notes="Portal demo order",
    )
    db.add(order)
    await db.flush()
    db.add(
        SalesOrderLine(
            order_id=order.id,
            sku="BK-DEMO-01",
            product_name="Commercial bakeware set",
            category_l3="bakeware",
            qty=100,
            unit_price=2.5,
        )
    )
    await db.commit()
