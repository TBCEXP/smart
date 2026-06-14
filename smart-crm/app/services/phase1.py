from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import Factory, SalesOrder, SalesOrderLine
from app.services.data_loader import load_geo_config

DEFAULT_FACTORIES: list[dict[str, str]] = [
    {
        "code": "F-SD-01",
        "name_zh": "顺德不锈钢厨具厂",
        "name_en": "Shunde Stainless Cookware Co.",
        "country": "CN",
        "city": "Foshan",
        "category_focus": "cookware-commercial,flatware",
        "moq_default": "500 pcs",
    },
    {
        "code": "F-ZJ-02",
        "name_zh": "浙江烘焙模具厂",
        "name_en": "Zhejiang Bakeware Moulds Ltd.",
        "country": "CN",
        "city": "Yongkang",
        "category_focus": "bakeware",
        "moq_default": "300 pcs",
    },
    {
        "code": "F-GD-03",
        "name_zh": "广东食品储存容器厂",
        "name_en": "Guangdong Food Storage Containers",
        "country": "CN",
        "city": "Guangzhou",
        "category_focus": "food-storage,buffet",
        "moq_default": "1000 pcs",
    },
]


def catalog_tree() -> dict[str, Any]:
    """L1/L2/L3 品类树（来自 geo_config.yaml）。"""
    geo = load_geo_config()
    cats = geo.get("categories", {})
    return {
        "l1": cats.get("l1", {}),
        "l2": cats.get("l2", {}),
        "l3": cats.get("l3", []),
    }


async def seed_factories(db: AsyncSession) -> int:
    created = 0
    for item in DEFAULT_FACTORIES:
        existing = await db.execute(select(Factory).where(Factory.code == item["code"]))
        if existing.scalar_one_or_none():
            continue
        db.add(Factory(**item))
        created += 1
    if created:
        await db.commit()
    return created


def factory_dict(f: Factory) -> dict[str, Any]:
    return {
        "id": f.id,
        "code": f.code,
        "name_zh": f.name_zh,
        "name_en": f.name_en,
        "country": f.country,
        "city": f.city,
        "contact_name": f.contact_name,
        "contact_email": f.contact_email,
        "category_focus": f.category_focus,
        "moq_default": f.moq_default,
        "active": f.active,
        "notes": f.notes,
        "created_at": f.created_at.isoformat() if f.created_at else None,
    }


def order_line_dict(line: SalesOrderLine) -> dict[str, Any]:
    return {
        "id": line.id,
        "sku": line.sku,
        "product_name": line.product_name,
        "category_l3": line.category_l3,
        "qty": line.qty,
        "unit_price": line.unit_price,
        "factory_id": line.factory_id,
        "notes": line.notes,
        "line_total": round(line.qty * line.unit_price, 2),
    }


def order_dict(order: SalesOrder, lines: list[SalesOrderLine] | None = None) -> dict[str, Any]:
    line_rows = lines if lines is not None else list(order.lines or [])
    return {
        "id": order.id,
        "order_no": order.order_no,
        "customer_name": order.customer_name,
        "country_iso": order.country_iso,
        "status": order.status,
        "currency": order.currency,
        "total_amount": order.total_amount,
        "assigned_to": order.assigned_to,
        "factory_id": order.factory_id,
        "lead_id": order.lead_id,
        "notes": order.notes,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "lines": [order_line_dict(l) for l in line_rows],
    }


def next_order_no() -> str:
    return f"ORD-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"


async def recalc_order_total(db: AsyncSession, order_id: str) -> float:
    result = await db.execute(
        select(SalesOrderLine).where(SalesOrderLine.order_id == order_id)
    )
    lines = result.scalars().all()
    total = sum(l.qty * l.unit_price for l in lines)
    order = await db.get(SalesOrder, order_id)
    if order:
        order.total_amount = round(total, 2)
        await db.commit()
    return total
