from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.entities import CountryAnchor, MarketProductIntel, Schedule, StrategySession
from app.services.brainstorm import BrainstormService
from app.services.data_loader import build_exa_query, get_country_config, get_l3_categories, load_geo_config
from app.services.pipeline import TrackBService, seed_geo_data


PILOT_DEFAULT_L3 = ["bakeware", "cookware-commercial", "flatware"]

PILOT_DEFAULTS: dict[str, dict[str, Any]] = {
    "MX": {
        "cities": ["CDMX", "Monterrey"],
        "primary_city": "CDMX",
        "primary_l3": "bakeware",
        "language": "es",
        "anchor_limit": 2,
    },
    "CO": {
        "cities": ["Bogotá", "Medellín"],
        "primary_city": "Bogotá",
        "primary_l3": "bakeware",
        "language": "es",
        "anchor_limit": 2,
    },
}


class LatamPilotService:
    """Phase 1.5 西语试点编排：Track B → Brainstorm → Track A 入队。"""

    def __init__(self) -> None:
        self.track_b = TrackBService()
        self.brainstorm = BrainstormService()
        self._runs_path = settings.data_dir / "pilot_runs.json"

    def _country_defaults(self, country_iso: str) -> dict[str, Any]:
        iso = country_iso.upper()
        defaults = PILOT_DEFAULTS.get(iso, PILOT_DEFAULTS["MX"]).copy()
        geo = get_country_config(iso)
        if geo.get("cities"):
            defaults.setdefault("cities", geo["cities"][:2])
        defaults.setdefault("language", geo.get("language", "es"))
        return defaults

    def _save_run(self, record: dict[str, Any]) -> None:
        runs: list[dict[str, Any]] = []
        if self._runs_path.exists():
            try:
                runs = json.loads(self._runs_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                runs = []
        runs.insert(0, record)
        self._runs_path.write_text(
            json.dumps(runs[:30], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def list_runs(self, country_iso: str = "") -> list[dict[str, Any]]:
        if not self._runs_path.exists():
            return []
        try:
            runs = json.loads(self._runs_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        if country_iso:
            iso = country_iso.upper()
            runs = [r for r in runs if r.get("country_iso") == iso]
        return runs

    async def run(
        self,
        db: AsyncSession,
        country_iso: str = "MX",
        city: str = "",
        category_l3: str = "bakeware",
        cities: list[str] | None = None,
        l3_codes: list[str] | None = None,
        anchor_limit: int | None = None,
        leads_per_task: int = 5,
        enqueue_track_a: bool = True,
    ) -> dict[str, Any]:
        iso = country_iso.upper()
        cfg = self._country_defaults(iso)
        pilot_id = str(uuid.uuid4())
        started = datetime.utcnow()
        steps: list[dict[str, Any]] = []
        target_cities = cities or cfg["cities"]
        target_l3 = l3_codes or PILOT_DEFAULT_L3
        pilot_city = city or cfg["primary_city"]
        language = cfg.get("language", "es")
        anchor_cap = anchor_limit if anchor_limit is not None else cfg.get("anchor_limit", 2)

        await seed_geo_data(db)
        steps.append({"step": "seed_geo", "status": "ok", "detail": f"{iso} 锚点/地理数据已就绪"})

        anchor_rows = await db.execute(
            select(CountryAnchor)
            .where(CountryAnchor.country_iso == iso)
            .order_by(CountryAnchor.company_name)
        )
        anchors = anchor_rows.scalars().all()
        if not anchors:
            steps.append({"step": "track_b", "status": "failed", "detail": f"未找到 {iso} 锚点"})
        else:
            for anchor in anchors[: max(1, anchor_cap)]:
                try:
                    intel = await self.track_b.crawl_anchor(db, anchor)
                    steps.append(
                        {
                            "step": "track_b_crawl",
                            "status": "ok",
                            "anchor": anchor.company_name,
                            "intel_id": intel.id,
                            "category_l3": intel.category_l3,
                            "sales_signal": intel.sales_signal,
                        }
                    )
                except Exception as exc:
                    steps.append(
                        {
                            "step": "track_b_crawl",
                            "status": "error",
                            "anchor": anchor.company_name,
                            "detail": str(exc),
                        }
                    )

        session = await self.brainstorm.generate(
            db,
            country_iso=iso,
            city=pilot_city,
            category_l3=category_l3,
            language=language,
        )
        cards = self.brainstorm.session_to_cards(session)
        steps.append(
            {
                "step": "brainstorm",
                "status": "ok",
                "session_id": session.id,
                "cards_count": len(cards),
                "keywords_es": (session.keywords or {}).get("es", [])[:5],
            }
        )

        schedules_created = 0
        schedule_keywords: list[str] = []
        if enqueue_track_a:
            brainstorm_keywords = (session.keywords or {}).get("es", [])
            similar_queries = (session.seeds or {}).get("similar_search_queries", [])
            keyword_pool = brainstorm_keywords or similar_queries

            for l3 in target_l3[:3]:
                for task_city in target_cities[:2]:
                    kw = ""
                    city_key = task_city.lower().replace("ó", "o").replace("á", "a")
                    for candidate in keyword_pool:
                        cand = candidate.lower()
                        if city_key in cand or task_city.lower() in cand or l3 in candidate:
                            kw = candidate
                            break
                    if not kw:
                        kw = build_exa_query(l3, task_city, iso, language)

                    existing = await db.execute(
                        select(Schedule).where(
                            Schedule.country_iso == iso,
                            Schedule.city == task_city,
                            Schedule.category_l3 == l3,
                            Schedule.keyword == kw,
                        )
                    )
                    if existing.scalar_one_or_none():
                        continue

                    db.add(
                        Schedule(
                            keyword=kw,
                            industry="跨境电商",
                            interval_hours=24,
                            country_iso=iso,
                            city=task_city,
                            category_l3=l3,
                            language=language,
                            track="track_a",
                            next_run_at=datetime.utcnow(),
                        )
                    )
                    schedules_created += 1
                    schedule_keywords.append(f"{task_city}/{l3}: {kw[:80]}")

            await db.commit()
            steps.append(
                {
                    "step": "enqueue_track_a",
                    "status": "ok",
                    "schedules_created": schedules_created,
                    "leads_per_task": leads_per_task,
                    "keywords": schedule_keywords,
                }
            )

        acceptance = self._acceptance_check(steps, session, schedules_created)
        record = {
            "pilot_id": pilot_id,
            "phase": "1.5",
            "country_iso": iso,
            "city": pilot_city,
            "category_l3": category_l3,
            "started_at": started.isoformat(),
            "completed_at": datetime.utcnow().isoformat(),
            "session_id": session.id,
            "steps": steps,
            "acceptance": acceptance,
            "next_actions": [
                "Tab4 点击「执行到期任务」或 Tab1 手动跑 Track A（每任务 5 条）",
                "Tab3 审核开发信 → confirm 入库飞书",
                "Tab8 为热点 L3 批量生成 es/en/pt SEO 内容",
            ],
        }
        self._save_run(record)
        return record

    def _acceptance_check(
        self,
        steps: list[dict[str, Any]],
        session: StrategySession,
        schedules_created: int,
    ) -> dict[str, Any]:
        track_b_ok = any(
            s.get("step") == "track_b_crawl" and s.get("status") == "ok" for s in steps
        )
        brainstorm_ok = any(s.get("step") == "brainstorm" and s.get("status") == "ok" for s in steps)
        keywords = (session.keywords or {}).get("es", [])
        return {
            "track_b_intel": track_b_ok,
            "brainstorm_cards": brainstorm_ok and len(keywords) > 0,
            "track_a_queued": schedules_created >= 1,
            "ready_for_manual_review": track_b_ok and brainstorm_ok,
            "notes": (
                "自动入队后请在 Tab4 执行到期任务或 Tab1 手动跑 Track A；"
                "确认开发信质量后再 confirm 入库飞书。"
            ),
        }

    async def status(self, db: AsyncSession, country_iso: str = "MX") -> dict[str, Any]:
        iso = country_iso.upper()
        runs = self.list_runs(iso)
        latest = runs[0] if runs else None
        intel_count = await db.execute(
            select(MarketProductIntel).where(MarketProductIntel.country_iso == iso)
        )
        session_count = await db.execute(
            select(StrategySession).where(StrategySession.country_iso == iso)
        )
        schedule_count = await db.execute(
            select(Schedule).where(Schedule.country_iso == iso, Schedule.enabled.is_(True))
        )
        cfg = self._country_defaults(iso)
        return {
            "phase": "1.5",
            "country_iso": iso,
            "latest_run": latest,
            "totals": {
                "intel_reports": len(intel_count.scalars().all()),
                "brainstorm_sessions": len(session_count.scalars().all()),
                "active_schedules": len(schedule_count.scalars().all()),
            },
            "pilot_defaults": {
                "cities": cfg["cities"],
                "l3_codes": PILOT_DEFAULT_L3,
                "anchors": [
                    a["company_name"]
                    for a in load_geo_config().get("anchors", {}).get(iso, [])
                ],
                "l3_labels": [
                    {"code": c["code"], "name_zh": c.get("name_zh", c["code"])}
                    for c in get_l3_categories()
                    if c["code"] in PILOT_DEFAULT_L3
                ],
            },
        }


# Backward-compatible alias
MxPilotService = LatamPilotService
