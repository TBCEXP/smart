from __future__ import annotations

import json
from typing import Any

import httpx

from app.services.config_store import ConfigStore


class KnowledgeBaseService:
    """PostgreSQL 线索知识层：embedding 写入 + 语义检索（pgvector 或余弦回退）。"""

    def __init__(self, config: ConfigStore | None = None) -> None:
        self.config = config or ConfigStore()

    async def embed_text(self, text: str) -> list[float]:
        api_key = self.config.get("openai_api_key")
        if not api_key or not text.strip():
            return []
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.openai.com/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "text-embedding-3-small",
                    "input": text[:6000],
                },
            )
            resp.raise_for_status()
            return resp.json()["data"][0]["embedding"]

    async def index_lead(self, lead_id: str, text: str, db) -> None:
        from app.models.entities import Lead

        vec = await self.embed_text(text)
        lead = await db.get(Lead, lead_id)
        if lead and vec:
            lead.embedding = json.dumps(vec)
            await db.commit()

    async def search(self, db, query: str, limit: int = 10) -> list[dict[str, Any]]:
        from sqlalchemy import select

        from app.models.entities import Lead

        query_vec = await self.embed_text(query)
        if not query_vec:
            # 文本回退：按国家/品类/关键词模糊匹配
            result = await db.execute(
                select(Lead)
                .where(
                    Lead.company_name.contains(query[:20])
                    | Lead.keyword.contains(query[:30])
                )
                .limit(limit)
            )
            return [self._lead_brief(l) for l in result.scalars().all()]

        # 余弦相似度（存储为 JSON，兼容 SQLite 开发环境）
        result = await db.execute(select(Lead).where(Lead.embedding.isnot(None)))
        scored: list[tuple[float, Any]] = []
        for lead in result.scalars().all():
            try:
                vec = json.loads(lead.embedding or "[]")
                if len(vec) != len(query_vec):
                    continue
                sim = _cosine(query_vec, vec)
                scored.append((sim, lead))
            except (json.JSONDecodeError, TypeError):
                continue
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {**self._lead_brief(lead), "score": round(sim, 4)}
            for sim, lead in scored[:limit]
        ]

    def _lead_brief(self, lead) -> dict[str, Any]:
        return {
            "id": lead.id,
            "company_name": lead.company_name,
            "website_url": lead.website_url,
            "country_iso": lead.country_iso,
            "city": lead.city,
            "category_l3": lead.category_l3,
            "keyword": lead.keyword,
            "status": lead.status,
        }


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(x * x for x in b) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)
