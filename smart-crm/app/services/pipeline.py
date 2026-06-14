from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any, AsyncGenerator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import Batch, CountryAnchor, Lead, MarketProductIntel
from app.services.clients import ExaClient, FirecrawlClient, LLMClient, extract_domain
from app.services.config_store import ConfigStore
from app.services.feishu_client import FeishuClient
from app.services.knowledge_base import KnowledgeBaseService
from app.services.data_loader import (
    build_exa_query,
    load_geo_config,
    load_prompts,
    save_batch_file,
)


class PipelineService:
    def __init__(self) -> None:
        self.config_store = ConfigStore()
        self.exa = ExaClient(self.config_store)
        self.firecrawl = FirecrawlClient(self.config_store)
        self.llm = LLMClient(self.config_store)
        self.feishu = FeishuClient(self.config_store)
        self.kb = KnowledgeBaseService(self.config_store)

    async def run_batch(
        self,
        db: AsyncSession,
        keyword: str,
        industry: str,
        count: int,
        country_iso: str = "",
        city: str = "",
        category_l3: str = "",
        language: str = "es",
        search_type: str = "standard",
        track: str = "track_a",
    ) -> tuple[str, AsyncGenerator[dict[str, Any], None]]:
        batch = Batch(
            keyword=keyword,
            industry=industry,
            total=count,
            country_iso=country_iso,
            city=city,
            category_l3=category_l3,
            track=track,
            status="running",
        )
        db.add(batch)
        await db.commit()
        await db.refresh(batch)

        async def event_stream() -> AsyncGenerator[dict[str, Any], None]:
            leads: list[dict[str, Any]] = []
            success = 0
            failed = 0
            yield {"event": "start", "batch_id": batch.id, "total": count}

            try:
                results = await self.exa.search(keyword, count)
            except Exception as exc:
                batch.status = "failed"
                await db.commit()
                yield {"event": "error", "message": str(exc)}
                return

            concurrency = int(self.config_store.get("max_concurrency", "5"))
            sem = asyncio.Semaphore(concurrency)

            async def process_one(idx: int, item: dict[str, Any]) -> dict[str, Any]:
                async with sem:
                    domain = item.get("domain") or extract_domain(item.get("url", ""))
                    existing = await db.execute(select(Lead).where(Lead.domain == domain))
                    if domain and existing.scalar_one_or_none():
                        return {"event": "skip", "index": idx, "reason": "duplicate", "domain": domain}

                    paths = load_prompts().get("industries", {}).get("hospitality_es", {}).get(
                        "firecrawl_paths", ["/products", "/about"]
                    )
                    try:
                        fc_summary = await self.firecrawl.scrape(item.get("url", ""), paths)
                    except Exception as exc:
                        fc_summary = f"Firecrawl error: {exc}"

                    prompts = load_prompts()
                    outreach_cfg = prompts.get("outreach", {}).get("hospitality_es", {})
                    system = outreach_cfg.get("system", "Write B2B outreach email.")
                    user = (
                        f"Company: {item.get('title')}\nURL: {item.get('url')}\n"
                        f"Exa: {item.get('text', '')[:1500]}\nWebsite: {fc_summary[:2000]}\n"
                        f"Country: {country_iso} City: {city} Category: {category_l3}\n"
                        f"Language: {language}"
                    )
                    outreach = await self.llm.complete(system, user)
                    whatsapp_tpl = outreach_cfg.get("whatsapp_template", "")
                    whatsapp = whatsapp_tpl.format(
                        contact_name="equipo de compras",
                        sender_name="Export Team",
                        company=item.get("title", "su empresa"),
                        company_signal=f"operan en {country_iso} con foco en {category_l3}",
                        category_l3=category_l3.replace("-", " "),
                        moq="500 pcs",
                    )

                    lead = Lead(
                        batch_id=batch.id,
                        company_name=item.get("title", ""),
                        website_url=item.get("url", ""),
                        domain=domain,
                        industry=industry,
                        keyword=keyword,
                        exa_summary=item.get("text", "")[:3000],
                        firecrawl_summary=fc_summary[:4000],
                        outreach_email=outreach,
                        whatsapp_intro=whatsapp[:500],
                        preferred_channel="whatsapp" if language == "es" else "email",
                        language=language,
                        country_iso=country_iso,
                        city=city,
                        category_l3=category_l3,
                        track=track,
                        source="exa" if search_type == "standard" else "similar",
                    )
                    db.add(lead)
                    await db.commit()
                    await db.refresh(lead)

                    ingest_mode = self.config_store.get("ingest_mode", "review")
                    if ingest_mode == "auto":
                        lead.status = "待联系"
                        try:
                            record_id = await self.feishu.create_record(lead, batch.id)
                            if record_id:
                                lead.feishu_record_id = record_id
                        except Exception:
                            pass
                    try:
                        await self.kb.index_lead(
                            lead.id,
                            f"{lead.company_name} {lead.firecrawl_summary} {lead.keyword}",
                            db,
                        )
                    except Exception:
                        pass

                    return {
                        "event": "lead",
                        "index": idx,
                        "lead": self._lead_dict(lead),
                    }

            tasks = [process_one(i, r) for i, r in enumerate(results)]
            for coro in asyncio.as_completed(tasks):
                result = await coro
                if result.get("event") == "lead":
                    success += 1
                    leads.append(result["lead"])
                elif result.get("event") == "skip":
                    failed += 1
                yield result

            batch.success = success
            batch.failed = failed
            batch.status = "completed"
            batch.completed_at = datetime.utcnow()
            await db.commit()

            save_batch_file(
                batch.id,
                {
                    "batch": {
                        "id": batch.id,
                        "keyword": keyword,
                        "industry": industry,
                        "success": success,
                        "failed": failed,
                    },
                    "leads": leads,
                },
            )
            yield {"event": "complete", "batch_id": batch.id, "success": success, "failed": failed}

        return batch.id, event_stream()

    def _lead_dict(self, lead: Lead) -> dict[str, Any]:
        return {
            "id": lead.id,
            "company_name": lead.company_name,
            "website_url": lead.website_url,
            "domain": lead.domain,
            "industry": lead.industry,
            "keyword": lead.keyword,
            "exa_summary": lead.exa_summary,
            "firecrawl_summary": lead.firecrawl_summary,
            "outreach_email": lead.outreach_email,
            "whatsapp_intro": lead.whatsapp_intro,
            "lead_score": lead.lead_score,
            "status": lead.status,
            "preferred_channel": lead.preferred_channel,
            "country_iso": lead.country_iso,
            "city": lead.city,
            "category_l3": lead.category_l3,
            "track": lead.track,
        }


class TrackBService:
    def __init__(self) -> None:
        self.firecrawl = FirecrawlClient()
        self.llm = LLMClient()

    async def crawl_anchor(self, db: AsyncSession, anchor: CountryAnchor) -> MarketProductIntel:
        paths = anchor.crawl_paths or ["/products", "/collections"]
        summary = await self.firecrawl.scrape(anchor.website, paths)
        prompts = load_prompts()
        raw = await self.llm.complete(
            prompts.get("track_b_prompt", "Summarize product categories."),
            f"Country: {anchor.country_iso}\nCompany: {anchor.company_name}\nContent:\n{summary[:5000]}",
            json_mode=True,
        )
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {"category_l3": "bakeware", "trend_summary": summary[:500], "sales_signal": "medium"}

        intel = MarketProductIntel(
            country_iso=anchor.country_iso,
            anchor_id=anchor.id,
            category_l3=parsed.get("top_l3", parsed.get("category_l3", "bakeware")),
            product_examples=parsed.get("product_examples", []),
            trend_summary=parsed.get("trend_summary", summary[:1000]),
            sales_signal=parsed.get("sales_signal", "medium"),
            source_urls=[anchor.website],
            l3_heat=parsed.get("l3_heat", {}),
        )
        anchor.last_crawled_at = datetime.utcnow()
        db.add(intel)
        await db.commit()
        await db.refresh(intel)
        return intel


async def seed_geo_data(db: AsyncSession) -> None:
    geo = load_geo_config()
    for country, anchors in geo.get("anchors", {}).items():
        for a in anchors:
            existing = await db.execute(
                select(CountryAnchor).where(
                    CountryAnchor.country_iso == country,
                    CountryAnchor.company_name == a["company_name"],
                )
            )
            if existing.scalar_one_or_none():
                continue
            db.add(
                CountryAnchor(
                    country_iso=country,
                    company_name=a["company_name"],
                    website=a["website"],
                    anchor_type=a.get("anchor_type", "brand"),
                    crawl_paths=a.get("crawl_paths", []),
                )
            )
    await db.commit()
