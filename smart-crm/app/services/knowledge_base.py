from __future__ import annotations

import json
from typing import Any

import httpx
from sqlalchemy import text

from app.database import ASYNC_DB_URL
from app.services.config_store import ConfigStore

EMBED_DIM = 1536


def _pg_mode() -> bool:
    return "postgresql" in ASYNC_DB_URL


def _vec_literal(vec: list[float]) -> str:
    return "[" + ",".join(f"{x:.8f}" for x in vec) + "]"


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
        if not lead or not vec:
            return
        emb_json = json.dumps(vec)
        lead.embedding = emb_json
        if _pg_mode():
            await db.execute(
                text(
                    "UPDATE leads SET embedding = :emb, "
                    "embedding_vec = CAST(:vec AS vector) WHERE id = :id"
                ),
                {"emb": emb_json, "vec": _vec_literal(vec), "id": lead_id},
            )
        await db.commit()

    async def search(self, db, query: str, limit: int = 10) -> list[dict[str, Any]]:
        query_vec = await self.embed_text(query)
        if not query_vec:
            return await self._text_search(db, query, limit)
        if _pg_mode():
            pg_results = await self._pgvector_search(db, query_vec, limit)
            if pg_results:
                return pg_results
        return await self._cosine_json_search(db, query_vec, limit)

    async def _pgvector_search(
        self, db, query_vec: list[float], limit: int
    ) -> list[dict[str, Any]]:
        result = await db.execute(
            text(
                """
                SELECT id, company_name, website_url, country_iso, city,
                       category_l3, keyword, status,
                       1 - (embedding_vec <=> CAST(:q AS vector)) AS score
                FROM leads
                WHERE embedding_vec IS NOT NULL
                ORDER BY embedding_vec <=> CAST(:q AS vector)
                LIMIT :lim
                """
            ),
            {"q": _vec_literal(query_vec), "lim": limit},
        )
        rows = result.mappings().all()
        return [
            {
                "id": r["id"],
                "company_name": r["company_name"],
                "website_url": r["website_url"],
                "country_iso": r["country_iso"],
                "city": r["city"],
                "category_l3": r["category_l3"],
                "keyword": r["keyword"],
                "status": r["status"],
                "score": round(float(r["score"]), 4),
                "search_mode": "pgvector",
            }
            for r in rows
        ]

    async def _cosine_json_search(
        self, db, query_vec: list[float], limit: int
    ) -> list[dict[str, Any]]:
        from sqlalchemy import select

        from app.models.entities import Lead

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
            {**self._lead_brief(lead), "score": round(sim, 4), "search_mode": "cosine_json"}
            for sim, lead in scored[:limit]
        ]

    async def _text_search(self, db, query: str, limit: int) -> list[dict[str, Any]]:
        from sqlalchemy import or_, select

        from app.models.entities import Lead

        tokens = [t.strip() for t in query.replace("，", " ").split() if t.strip()]
        if not tokens:
            tokens = [query[:20]]
        clauses = []
        for tok in tokens[:6]:
            pat = f"%{tok}%"
            clauses.extend(
                [
                    Lead.company_name.ilike(pat),
                    Lead.keyword.ilike(pat),
                    Lead.country_iso.ilike(pat),
                    Lead.category_l3.ilike(pat),
                    Lead.city.ilike(pat),
                    Lead.firecrawl_summary.ilike(pat),
                    Lead.exa_summary.ilike(pat),
                ]
            )
        result = await db.execute(select(Lead).where(or_(*clauses)).limit(limit))
        return [
            {**self._lead_brief(l), "search_mode": "text_fallback"}
            for l in result.scalars().all()
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
