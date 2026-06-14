from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import (
    CountryAnchor,
    MarketProductIntel,
    Schedule,
    StrategyAction,
    StrategySession,
)
from app.services.clients import LLMClient
from app.services.data_loader import (
    build_exa_query,
    get_country_config,
    get_hs_codes_for_l3,
    get_l3_categories,
    load_geo_config,
    load_prompts,
)


class BrainstormService:
    def __init__(self) -> None:
        self.llm = LLMClient()

    async def generate(
        self,
        session: AsyncSession,
        country_iso: str,
        city: str,
        category_l3: str,
        language: str = "es",
        context: dict[str, Any] | None = None,
    ) -> StrategySession:
        prompts = load_prompts()
        geo = load_geo_config()
        country = get_country_config(country_iso)
        l3_info = next(
            (c for c in get_l3_categories() if c["code"] == category_l3),
            {"name_zh": category_l3, "reference_brands_latam": []},
        )
        defaults = geo.get("brainstorm_defaults", {}).get(country_iso.upper(), {})

        intel_rows = await session.execute(
            select(MarketProductIntel)
            .where(MarketProductIntel.country_iso == country_iso.upper())
            .order_by(MarketProductIntel.created_at.desc())
            .limit(5)
        )
        intel_list = intel_rows.scalars().all()

        anchor_rows = await session.execute(
            select(CountryAnchor).where(CountryAnchor.country_iso == country_iso.upper())
        )
        anchors = anchor_rows.scalars().all()

        anchor_brand = ""
        if l3_info.get("reference_brands_latam"):
            anchor_brand = l3_info["reference_brands_latam"][0]
        elif anchors:
            anchor_brand = anchors[0].company_name

        similar_queries = []
        for tmpl in prompts.get("similar_company_templates", [])[:3]:
            similar_queries.append(
                tmpl.format(
                    product=l3_info.get("name_en", category_l3),
                    anchor_brand=anchor_brand or "Winco",
                    country=country.get("name", country_iso),
                    city=city or defaults.get("cities", ["CDMX"])[0],
                    category_l3=l3_info.get("name_en", category_l3),
                )
            )

        user_prompt = json.dumps(
            {
                "country": country_iso,
                "city": city,
                "category_l3": category_l3,
                "category_name": l3_info.get("name_zh"),
                "language": language,
                "context": context or {},
                "market_intel": [
                    {"l3": i.category_l3, "summary": i.trend_summary[:500]}
                    for i in intel_list
                ],
                "anchors": [a.company_name for a in anchors],
                "suggested_similar_queries": similar_queries,
                "hs_codes": get_hs_codes_for_l3(category_l3),
                "channel_priority": country.get("channel_priority", ["email", "whatsapp"]),
            },
            ensure_ascii=False,
        )

        raw = await self.llm.complete(
            prompts.get("brainstorm_system", ""),
            user_prompt,
            json_mode=True,
        )
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {
                "icp": {},
                "keywords": {"es": [build_exa_query(category_l3, city, country_iso, language)]},
                "channel_plan": [],
                "seeds": {"similar_search_queries": similar_queries},
                "action_plan": {},
            }

        if not parsed.get("seeds", {}).get("similar_search_queries"):
            parsed.setdefault("seeds", {})["similar_search_queries"] = similar_queries
        if not parsed.get("seeds", {}).get("hs_codes"):
            parsed.setdefault("seeds", {})["hs_codes"] = get_hs_codes_for_l3(category_l3)

        record = StrategySession(
            country_iso=country_iso.upper(),
            city=city,
            category_l3=category_l3,
            language=language,
            icp_json=parsed.get("icp", {}),
            keywords=parsed.get("keywords", {}),
            channel_plan=parsed.get("channel_plan", []),
            seeds=parsed.get("seeds", {}),
            action_plan=parsed.get("action_plan", {}),
            market_intel_refs=[i.id for i in intel_list],
        )
        session.add(record)
        await session.commit()
        await session.refresh(record)
        return record

    async def create_action(
        self,
        session: AsyncSession,
        session_id: str,
        action_type: str,
        payload: dict[str, Any],
    ) -> StrategyAction:
        strat = await session.get(StrategySession, session_id)
        if not strat:
            raise ValueError("Strategy session not found")

        action = StrategyAction(
            session_id=session_id,
            action_type=action_type,
            payload_json=payload,
            status="pending",
        )

        if action_type == "track_a_job":
            keywords = payload.get("keywords") or strat.keywords.get("es", [])
            for kw in keywords[:10]:
                schedule = Schedule(
                    keyword=kw,
                    industry="跨境电商",
                    interval_hours=payload.get("interval_hours", 24),
                    country_iso=strat.country_iso,
                    city=strat.city,
                    category_l3=strat.category_l3,
                    language=strat.language,
                    track="track_a",
                    next_run_at=datetime.utcnow(),
                )
                session.add(schedule)
            action.status = "done"

        elif action_type == "anchor":
            for seed in payload.get("companies", strat.seeds.get("companies", [])):
                if isinstance(seed, dict) and seed.get("website"):
                    anchor = CountryAnchor(
                        country_iso=strat.country_iso,
                        company_name=seed.get("name", ""),
                        website=seed["website"],
                        anchor_type=seed.get("type", "brand"),
                        crawl_paths=seed.get("crawl_paths", ["/products"]),
                    )
                    session.add(anchor)
            action.status = "done"

        elif action_type == "similar_search":
            queries = payload.get("queries") or strat.seeds.get("similar_search_queries", [])
            for q in queries[:5]:
                schedule = Schedule(
                    keyword=q,
                    industry="跨境电商",
                    interval_hours=48,
                    country_iso=strat.country_iso,
                    city=strat.city,
                    category_l3=strat.category_l3,
                    language=strat.language,
                    track="track_a",
                    next_run_at=datetime.utcnow() + timedelta(hours=1),
                )
                session.add(schedule)
            action.status = "done"

        session.add(action)
        await session.commit()
        await session.refresh(action)
        return action

    def session_to_cards(self, record: StrategySession) -> list[dict[str, Any]]:
        return [
            {"id": 1, "title": "ICP 画像", "content": record.icp_json},
            {"id": 2, "title": "关键词包", "content": record.keywords},
            {"id": 3, "title": "渠道策略", "content": record.channel_plan},
            {"id": 4, "title": "竞品与客户种子", "content": record.seeds},
            {"id": 5, "title": "30 天行动计划", "content": record.action_plan},
        ]
