"""TBCEXP ERP field mapping — lead push + order pull transformers."""

from __future__ import annotations

from typing import Any

from app.models.entities import Lead, SalesOrder

FIELD_MAP_VERSION = "1.0"

LEAD_FIELD_MAP: list[dict[str, Any]] = [
    {"crm": "id", "erp": "external_id", "type": "string", "required": True},
    {"crm": "company_name", "erp": "company_name", "type": "string", "required": True},
    {"crm": "website_url", "erp": "website_url", "type": "string"},
    {"crm": "domain", "erp": "domain", "type": "string"},
    {"crm": "country_iso", "erp": "country_iso", "type": "string"},
    {"crm": "city", "erp": "city", "type": "string"},
    {"crm": "category_l1", "erp": "category_l1", "type": "string"},
    {"crm": "category_l2", "erp": "category_l2", "type": "string"},
    {"crm": "category_l3", "erp": "category_l3", "type": "string"},
    {"crm": "lead_score", "erp": "lead_score", "type": "string"},
    {"crm": "status", "erp": "status", "type": "string"},
    {"crm": "assigned_to", "erp": "assigned_to", "type": "string"},
    {"crm": "feishu_record_id", "erp": "feishu_record_id", "type": "string"},
    {"crm": "preferred_channel", "erp": "preferred_channel", "type": "string"},
    {"crm": "language", "erp": "language", "type": "string"},
    {"crm": "keyword", "erp": "keyword", "type": "string"},
    {"crm": "contact_email", "erp": "contact_email", "type": "string"},
    {"crm": "contact_name", "erp": "contact_name", "type": "string"},
    {"crm": "contact_title", "erp": "contact_title", "type": "string"},
    {"crm": "buyer_type", "erp": "buyer_type", "type": "string"},
    {"crm": "track", "erp": "track", "type": "string"},
    {"crm": "source", "erp": "source", "type": "string"},
    {"crm": "hs_code", "erp": "hs_code", "type": "string"},
    {"crm": "industry", "erp": "industry", "type": "string"},
    {"crm": "firecrawl_summary", "erp": "notes", "type": "text", "max_len": 500},
]

ORDER_FIELD_MAP: list[dict[str, Any]] = [
    {"erp": "order_no", "crm": "order_no", "type": "string", "required": True},
    {"erp": "external_id", "crm": "notes", "type": "string", "prefix": "erp_id:"},
    {"erp": "customer_name", "crm": "customer_name", "type": "string"},
    {"erp": "customer_email", "crm": "customer_email", "type": "string"},
    {"erp": "country_iso", "crm": "country_iso", "type": "string"},
    {"erp": "status", "crm": "status", "type": "string"},
    {"erp": "currency", "crm": "currency", "type": "string"},
    {"erp": "total_amount", "crm": "total_amount", "type": "number"},
    {"erp": "assigned_to", "crm": "assigned_to", "type": "string"},
]


def lead_to_erp_payload(lead: Lead) -> dict[str, Any]:
    """Map CRM Lead → TBCEXP POST /api/external/leads body."""
    payload: dict[str, Any] = {
        "source": "smart_crm",
        "sourceType": "smart_crm",
    }
    for spec in LEAD_FIELD_MAP:
        crm_key = spec["crm"]
        erp_key = spec["erp"]
        value = getattr(lead, crm_key, "") or ""
        if spec.get("max_len"):
            value = str(value)[: spec["max_len"]]
        if value or spec.get("required"):
            payload[erp_key] = value
    if not payload.get("notes"):
        payload["notes"] = (lead.firecrawl_summary or lead.notes or "")[:500]
    return payload


def erp_order_to_crm(row: dict[str, Any]) -> dict[str, Any]:
    """Map TBCEXP order row → SalesOrder fields."""
    mapped: dict[str, Any] = {}
    for spec in ORDER_FIELD_MAP:
        erp_key = spec["erp"]
        crm_key = spec["crm"]
        value = row.get(erp_key)
        if value is None or value == "":
            continue
        if spec.get("prefix"):
            mapped[crm_key] = f"{spec['prefix']}{value}"
        elif spec["type"] == "number":
            mapped[crm_key] = float(value)
        else:
            mapped[crm_key] = str(value)
    if not mapped.get("order_no"):
        ext = row.get("external_id") or row.get("id")
        if ext:
            mapped["order_no"] = str(ext)
    if not mapped.get("status"):
        mapped["status"] = "draft"
    if not mapped.get("currency"):
        mapped["currency"] = "USD"
    return mapped


def field_map_documentation() -> dict[str, Any]:
    return {
        "version": FIELD_MAP_VERSION,
        "lead_push": {
            "endpoint": "POST {tbcexp_api_url}/api/external/leads",
            "fields": LEAD_FIELD_MAP,
        },
        "order_pull": {
            "endpoint": "GET {tbcexp_api_url}/api/external/orders",
            "fields": ORDER_FIELD_MAP,
        },
    }


async def sync_erp_orders(db, client, limit: int = 20) -> dict[str, Any]:
    """Pull ERP orders and upsert into SalesOrder by order_no."""
    from sqlalchemy import select

    pull = await client.list_orders(limit)
    created = 0
    updated = 0
    skipped = 0
    for row in pull.get("orders", []):
        mapped = erp_order_to_crm(row)
        order_no = mapped.get("order_no", "").strip()
        if not order_no:
            skipped += 1
            continue
        existing = await db.execute(
            select(SalesOrder).where(SalesOrder.order_no == order_no)
        )
        order = existing.scalar_one_or_none()
        if order:
            for key, value in mapped.items():
                if key == "order_no":
                    continue
                setattr(order, key, value)
            updated += 1
        else:
            db.add(SalesOrder(**mapped))
            created += 1
    await db.commit()
    return {
        "mode": pull.get("mode", "mock"),
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "pulled": len(pull.get("orders", [])),
        "detail": pull.get("detail", ""),
    }
