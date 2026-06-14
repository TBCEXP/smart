from __future__ import annotations

from typing import Any

import httpx

from app.models.entities import Lead
from app.services.config_store import ConfigStore


class TbcexpClient:
    """TBCEXP ERP 桥接 — 将确认线索推送为 ERP 潜在客户（Mock 或 HTTP）。"""

    def __init__(self, config: ConfigStore | None = None) -> None:
        self.config = config or ConfigStore()

    def _configured(self) -> bool:
        return bool(
            self.config.get("tbcexp_api_url", "").strip()
            and self.config.get("tbcexp_api_token", "").strip()
        )

    def lead_payload(self, lead: Lead) -> dict[str, Any]:
        return {
            "source": "smart_crm",
            "sourceType": "smart_crm",
            "external_id": lead.id,
            "company_name": lead.company_name,
            "website_url": lead.website_url,
            "domain": lead.domain,
            "country_iso": lead.country_iso,
            "city": lead.city,
            "category_l3": lead.category_l3,
            "lead_score": lead.lead_score,
            "status": lead.status,
            "assigned_to": lead.assigned_to,
            "feishu_record_id": lead.feishu_record_id,
            "preferred_channel": lead.preferred_channel,
            "language": lead.language,
            "keyword": lead.keyword,
            "notes": (lead.firecrawl_summary or "")[:500],
        }

    async def push_lead(self, lead: Lead) -> dict[str, Any]:
        payload = self.lead_payload(lead)
        if not self._configured():
            return {
                "mode": "mock",
                "status": "ok",
                "external_id": f"mock-erp-{lead.id[:8]}",
                "detail": "TBCEXP URL/Token 未配置，已模拟同步",
                "payload": payload,
            }

        base = self.config.get("tbcexp_api_url", "").rstrip("/")
        token = self.config.get("tbcexp_api_token", "")
        url = f"{base}/api/external/leads"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json() if resp.content else {}
            return {
                "mode": "live",
                "status": "ok",
                "external_id": data.get("id") or data.get("external_id", ""),
                "detail": "已推送至 TBCEXP ERP",
                "response": data,
            }

    async def probe(self) -> dict[str, Any]:
        if not self._configured():
            return {
                "id": "tbcexp",
                "label": "TBCEXP ERP",
                "status": "mock",
                "mock": True,
                "detail": "未配置 URL/Token",
            }
        base = self.config.get("tbcexp_api_url", "").rstrip("/")
        token = self.config.get("tbcexp_api_token", "")
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{base}/api/health",
                    headers={"Authorization": f"Bearer {token}"},
                )
                ok = resp.status_code < 500
                return {
                    "id": "tbcexp",
                    "label": "TBCEXP ERP",
                    "status": "ok" if ok else "error",
                    "mock": False,
                    "detail": f"HTTP {resp.status_code}",
                }
        except Exception as exc:
            return {
                "id": "tbcexp",
                "label": "TBCEXP ERP",
                "status": "error",
                "mock": False,
                "detail": str(exc)[:200],
            }

    async def list_orders(self, limit: int = 20) -> dict[str, Any]:
        """ERP 订单只读拉取（Mock 或 HTTP）。"""
        if not self._configured():
            return {
                "mode": "mock",
                "total": 2,
                "orders": [
                    {
                        "external_id": "erp-ord-1001",
                        "order_no": "TBCEXP-2026-1001",
                        "customer_name": "Hotel Supplies MX",
                        "customer_email": "buyer@hotel.com",
                        "country_iso": "MX",
                        "status": "confirmed",
                        "currency": "USD",
                        "total_amount": 12500.0,
                        "assigned_to": "sales@example.com",
                        "source": "tbcexp",
                    },
                    {
                        "external_id": "erp-ord-1002",
                        "order_no": "TBCEXP-2026-1002",
                        "customer_name": "Distribuidora Bogotá",
                        "customer_email": "procurement@dist.co",
                        "country_iso": "CO",
                        "status": "draft",
                        "currency": "USD",
                        "total_amount": 4800.0,
                        "assigned_to": "sales@example.com",
                        "source": "tbcexp",
                    },
                ][:limit],
                "detail": "TBCEXP 未配置，返回演示订单",
            }

        base = self.config.get("tbcexp_api_url", "").rstrip("/")
        token = self.config.get("tbcexp_api_token", "")
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{base}/api/external/orders",
                headers={"Authorization": f"Bearer {token}"},
                params={"limit": limit},
            )
            resp.raise_for_status()
            data = resp.json() if resp.content else {}
            orders = data.get("orders") or data.get("data") or data
            if isinstance(orders, dict):
                orders = orders.get("items", [])
            return {
                "mode": "live",
                "total": len(orders) if isinstance(orders, list) else 0,
                "orders": orders[:limit] if isinstance(orders, list) else [],
                "detail": "已从 TBCEXP 拉取",
            }
