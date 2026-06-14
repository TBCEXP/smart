from __future__ import annotations

import csv
import io
import re
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import ImportLead, Lead, Schedule, TradeShow
from app.services.clients import ExaClient, FirecrawlClient, extract_domain
from app.services.data_loader import get_hs_codes_for_l3, load_geo_config


class GeoSchedulerService:
    def __init__(self) -> None:
        self.geo = load_geo_config()

    def generate_country_queue(
        self,
        country_iso: str,
        exa_per_task: int = 5,
    ) -> list[dict[str, Any]]:
        country = self.geo.get("countries", {}).get(country_iso.upper(), {})
        cities = country.get("cities", [])
        l3_list = [c["code"] for c in self.geo.get("categories", {}).get("l3", [])]
        queue = []
        for city in cities:
            for l3 in l3_list:
                queue.append(
                    {
                        "country_iso": country_iso.upper(),
                        "city": city,
                        "category_l3": l3,
                        "language": country.get("language", "es"),
                        "exa_count": exa_per_task,
                        "track": "track_a",
                    }
                )
        return queue

    async def materialize_schedules(
        self,
        db: AsyncSession,
        country_iso: str,
        interval_hours: int = 24,
    ) -> int:
        from app.services.data_loader import build_exa_query

        queue = self.generate_country_queue(country_iso)
        created = 0
        for item in queue:
            keyword = build_exa_query(
                item["category_l3"],
                item["city"],
                item["country_iso"],
                item["language"],
            )
            existing = await db.execute(
                select(Schedule).where(
                    Schedule.country_iso == item["country_iso"],
                    Schedule.city == item["city"],
                    Schedule.category_l3 == item["category_l3"],
                )
            )
            if existing.scalar_one_or_none():
                continue
            db.add(
                Schedule(
                    keyword=keyword,
                    industry="跨境电商",
                    interval_hours=interval_hours,
                    country_iso=item["country_iso"],
                    city=item["city"],
                    category_l3=item["category_l3"],
                    language=item["language"],
                    track="track_a",
                    next_run_at=datetime.utcnow() + timedelta(hours=created),
                )
            )
            created += 1
        await db.commit()
        return created

    async def get_due_schedules(self, db: AsyncSession) -> list[Schedule]:
        now = datetime.utcnow()
        result = await db.execute(
            select(Schedule).where(
                Schedule.enabled.is_(True),
                (Schedule.next_run_at.is_(None)) | (Schedule.next_run_at <= now),
            )
        )
        return list(result.scalars().all())


class TrackCService:
    def __init__(self) -> None:
        self.exa = ExaClient()

    async def import_csv(
        self,
        db: AsyncSession,
        content: str,
        country_iso: str,
        hs_codes: list[str] | None = None,
        source: str = "manual",
    ) -> dict[str, Any]:
        reader = csv.DictReader(io.StringIO(content))
        imported = 0
        duplicates = 0
        for row in reader:
            company = row.get("company_name") or row.get("Company") or row.get("importer", "")
            website = row.get("website") or row.get("Website") or ""
            domain = extract_domain(website) if website else ""
            hs = row.get("hs_code") or row.get("HS Code") or (hs_codes[0] if hs_codes else "")
            if domain:
                existing = await db.execute(select(ImportLead).where(ImportLead.domain == domain))
                if existing.scalar_one_or_none():
                    duplicates += 1
                    continue
            record = ImportLead(
                company_name=company,
                country_iso=country_iso.upper(),
                hs_code=hs,
                website=website,
                domain=domain,
                contact_email=row.get("email", ""),
                import_volume=_parse_float(row.get("volume") or row.get("import_volume")),
                source=source,
                raw_data=dict(row),
            )
            db.add(record)
            imported += 1
        await db.commit()
        return {"imported": imported, "duplicates": duplicates}

    async def match_domains(self, db: AsyncSession, limit: int = 50) -> int:
        result = await db.execute(
            select(ImportLead).where(
                ImportLead.status == "pending",
                ImportLead.domain == "",
            ).limit(limit)
        )
        rows = result.scalars().all()
        matched = 0
        for row in rows:
            query = f"category:company {row.company_name} {row.country_iso} website"
            language = "es" if row.country_iso.upper() in ("MX", "CO", "CL", "PE", "AR") else "en"
            try:
                hits = await self.exa.search(
                    query, 1, search_type="similar", country_iso=row.country_iso, language=language
                )
                if hits:
                    row.website = hits[0].get("url", "")
                    row.domain = hits[0].get("domain", "")
                    row.status = "matched"
                    matched += 1
            except Exception:
                row.status = "match_failed"
        await db.commit()
        return matched

    async def promote_to_leads(self, db: AsyncSession, import_lead_id: str) -> Lead | None:
        record = await db.get(ImportLead, import_lead_id)
        if not record:
            return None
        if record.domain:
            existing = await db.execute(select(Lead).where(Lead.domain == record.domain))
            if existing.scalar_one_or_none():
                record.status = "duplicate"
                await db.commit()
                return None
        lead = Lead(
            company_name=record.company_name,
            website_url=record.website,
            domain=record.domain,
            industry="跨境电商",
            keyword=f"HS {record.hs_code} importer",
            country_iso=record.country_iso,
            hs_code=record.hs_code,
            track="track_c",
            source=record.source,
            preferred_channel="email",
            status="待联系",
        )
        record.status = "promoted"
        record.matched_lead_id = lead.id
        db.add(lead)
        await db.commit()
        await db.refresh(lead)
        return lead


class TradeShowService:
    def __init__(self) -> None:
        self.firecrawl = FirecrawlClient()

    async def seed_defaults(self, db: AsyncSession) -> None:
        defaults = [
            {
                "name": "Expo ANTAD",
                "country_iso": "MX",
                "region": "americas",
                "show_type": "retail_wholesale",
                "exhibitor_list_url": "https://www.antad.net.mx/expo-antad",
            },
            {
                "name": "HD Expo",
                "country_iso": "US",
                "region": "americas",
                "show_type": "hospitality",
                "exhibitor_list_url": "https://www.hdexpo.com/exhibitors",
            },
        ]
        for item in defaults:
            existing = await db.execute(
                select(TradeShow).where(TradeShow.name == item["name"])
            )
            if existing.scalar_one_or_none():
                continue
            db.add(TradeShow(**item))
        await db.commit()

    async def crawl_exhibitors(self, db: AsyncSession, show: TradeShow) -> dict[str, Any]:
        content = await self.firecrawl.scrape(show.exhibitor_list_url, ["/", "/exhibitors"])
        companies = _extract_company_names(content)
        show.exhibitor_count = len(companies)
        show.last_crawled_at = datetime.utcnow()
        await db.commit()
        return {"show_id": show.id, "exhibitors_found": len(companies), "samples": companies[:20]}


def _parse_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        return None


def _extract_company_names(text: str) -> list[str]:
    lines = text.splitlines()
    names = []
    for line in lines:
        line = line.strip(" #-•\t")
        if 3 < len(line) < 120 and not line.startswith("http"):
            if re.search(r"[A-Za-z]", line):
                names.append(line)
    return list(dict.fromkeys(names))[:200]
