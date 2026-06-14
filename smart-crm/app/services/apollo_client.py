from __future__ import annotations

from typing import Any

import httpx

from app.models.entities import Lead
from app.services.config_store import ConfigStore


class ApolloClient:
    """Apollo.io 联系人补充（L4 矩阵）— Mock 或 API。"""

    def __init__(self, config: ConfigStore | None = None) -> None:
        self.config = config or ConfigStore()

    def _configured(self) -> bool:
        return bool(self.config.get("apollo_api_key", "").strip())

    async def enrich_lead(self, lead: Lead) -> dict[str, Any]:
        domain = lead.domain or ""
        if not domain and lead.website_url:
            from app.services.clients import extract_domain

            domain = extract_domain(lead.website_url)
        if not self._configured():
            slug = domain.replace(".", "-") if domain else "company"
            return {
                "mode": "mock",
                "contact_name": "Procurement Manager",
                "contact_email": f"buying@{domain or 'example.com'}",
                "contact_title": "Purchasing Director",
                "phone": "",
                "confidence": "low",
                "detail": "Apollo Key 未配置，返回演示联系人",
            }
        api_key = self.config.get("apollo_api_key")
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    "https://api.apollo.io/v1/people/match",
                    headers={"Content-Type": "application/json", "Cache-Control": "no-cache"},
                    params={"api_key": api_key},
                    json={
                        "domain": domain,
                        "organization_name": lead.company_name,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                person = data.get("person") or {}
                return {
                    "mode": "live",
                    "contact_name": person.get("name", ""),
                    "contact_email": person.get("email", ""),
                    "contact_title": person.get("title", ""),
                    "phone": person.get("phone_number", ""),
                    "confidence": "medium",
                    "detail": "Apollo match",
                }
        except Exception as exc:
            return {
                "mode": "error",
                "contact_name": "",
                "contact_email": "",
                "contact_title": "",
                "phone": "",
                "confidence": "none",
                "detail": str(exc)[:200],
            }

    async def probe(self) -> dict[str, Any]:
        if not self._configured():
            return {
                "id": "apollo",
                "label": "Apollo",
                "status": "mock",
                "mock": True,
                "detail": "未配置 Key（可选）",
            }
        return {
            "id": "apollo",
            "label": "Apollo",
            "status": "ok",
            "mock": False,
            "detail": "API Key 已配置",
        }
