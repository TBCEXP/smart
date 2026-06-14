from __future__ import annotations

import asyncio
import csv
import io
import json
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import (
    AuthEmailRequest,
    AuthOtpRequest,
    BrainstormActionRequest,
    BrainstormRequest,
    ConfigPayload,
    FeishuWebhookRequest,
    ImportCsvRequest,
    RunRequest,
    ScheduleRequest,
    SendEmailRequest,
    TradeShowCrawlRequest,
)
from app.database import get_session
from app.models.entities import (
    Batch,
    CountryAnchor,
    ImportLead,
    Lead,
    MarketProductIntel,
    Schedule,
    StrategyAction,
    StrategySession,
    TradeShow,
)
from app.services.auth import AuthService
from app.services.brainstorm import BrainstormService
from app.services.config_store import ConfigStore
from app.services.data_loader import load_batch_file, load_expansion_tiers, load_geo_config
from app.services.geo_track import GeoSchedulerService, TrackCService, TradeShowService
from app.services.knowledge_base import KnowledgeBaseService
from app.services.pipeline import PipelineService, TrackBService, seed_geo_data

router = APIRouter()
config_store = ConfigStore()
pipeline = PipelineService()
brainstorm_svc = BrainstormService()
track_b = TrackBService()
geo_scheduler = GeoSchedulerService()
track_c = TrackCService()
tradeshow_svc = TradeShowService()
auth_svc = AuthService()
kb_svc = KnowledgeBaseService()

# In-memory SSE queues and scheduler state
_sse_queues: dict[str, asyncio.Queue] = {}
_scheduler_task: asyncio.Task | None = None


async def get_db():
    async with get_session() as session:
        yield session


@router.get("/health")
async def health():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}


@router.get("/config")
async def get_config():
    return config_store.masked()


@router.post("/config")
async def save_config(payload: ConfigPayload):
    return config_store.save(payload)


@router.post("/run")
async def run_batch(req: RunRequest, db: AsyncSession = Depends(get_db)):
    batch_id, stream = await pipeline.run_batch(
        db,
        keyword=req.keyword,
        industry=req.industry,
        count=req.count,
        country_iso=req.country_iso,
        city=req.city,
        category_l3=req.category_l3,
        language=req.language,
        search_type=req.search_type,
    )
    queue: asyncio.Queue = asyncio.Queue()
    _sse_queues[batch_id] = queue

    async def pump():
        async for event in stream:
            await queue.put(event)
        await queue.put(None)

    asyncio.create_task(pump())
    return JSONResponse({"batch_id": batch_id}, status_code=202)


@router.get("/stream/{batch_id}")
async def stream_batch(batch_id: str):
    queue = _sse_queues.get(batch_id)
    if not queue:
        raise HTTPException(404, "Batch stream not found")

    async def event_generator():
        while True:
            event = await queue.get()
            if event is None:
                yield "event: complete\ndata: {}\n\n"
                break
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/batch/{batch_id}")
async def get_batch(batch_id: str, db: AsyncSession = Depends(get_db)):
    batch = await db.get(Batch, batch_id)
    if not batch:
        data = load_batch_file(batch_id)
        if data:
            return data
        raise HTTPException(404, "Batch not found")
    leads = await db.execute(select(Lead).where(Lead.batch_id == batch_id))
    return {
        "batch": {
            "id": batch.id,
            "keyword": batch.keyword,
            "status": batch.status,
            "success": batch.success,
            "failed": batch.failed,
            "total": batch.total,
        },
        "leads": [pipeline._lead_dict(l) for l in leads.scalars().all()],
    }


@router.get("/batches")
async def list_batches(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Batch).order_by(Batch.created_at.desc()).limit(50))
    batches = result.scalars().all()
    return [
        {
            "id": b.id,
            "keyword": b.keyword,
            "industry": b.industry,
            "status": b.status,
            "success": b.success,
            "total": b.total,
            "created_at": b.created_at.isoformat() if b.created_at else None,
            "country_iso": b.country_iso,
            "track": b.track,
        }
        for b in batches
    ]


@router.get("/batch/{batch_id}/export.csv")
async def export_csv(batch_id: str, db: AsyncSession = Depends(get_db)):
    leads = await db.execute(select(Lead).where(Lead.batch_id == batch_id))
    rows = leads.scalars().all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "company_name",
            "website_url",
            "domain",
            "industry",
            "keyword",
            "lead_score",
            "status",
            "preferred_channel",
            "country_iso",
            "city",
            "category_l3",
            "outreach_email",
            "whatsapp_intro",
        ]
    )
    for l in rows:
        writer.writerow(
            [
                l.company_name,
                l.website_url,
                l.domain,
                l.industry,
                l.keyword,
                l.lead_score,
                l.status,
                l.preferred_channel,
                l.country_iso,
                l.city,
                l.category_l3,
                l.outreach_email,
                l.whatsapp_intro,
            ]
        )
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=batch_{batch_id}.csv"},
    )


@router.post("/confirm/{lead_id}")
async def confirm_lead(lead_id: str, db: AsyncSession = Depends(get_db)):
    lead = await db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(404, "Lead not found")
    lead.status = "待联系"
    from app.services.feishu_client import FeishuClient

    feishu = FeishuClient()
    try:
        record_id = await feishu.create_record(lead, lead.batch_id or "")
        if record_id:
            lead.feishu_record_id = record_id
    except Exception as exc:
        raise HTTPException(502, f"Feishu write failed: {exc}") from exc
    await db.commit()
    return {"status": "confirmed", "lead_id": lead_id, "feishu_record_id": lead.feishu_record_id}


@router.post("/regenerate/{lead_id}")
async def regenerate_lead(lead_id: str, db: AsyncSession = Depends(get_db)):
    lead = await db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(404, "Lead not found")
    from app.services.clients import LLMClient
    from app.services.data_loader import load_prompts

    llm = LLMClient()
    prompts = load_prompts()
    system = prompts.get("outreach", {}).get("hospitality_es", {}).get("system", "")
    user = f"Regenerate outreach for {lead.company_name}\n{lead.firecrawl_summary[:2000]}"
    lead.outreach_email = await llm.complete(system, user)
    await db.commit()
    return {"status": "regenerated", "outreach_email": lead.outreach_email}


@router.post("/webhooks/feishu")
async def feishu_webhook(payload: FeishuWebhookRequest, db: AsyncSession = Depends(get_db)):
    batch = await db.get(Batch, payload.batch_id)
    if not batch:
        raise HTTPException(404, "Batch not found")
    leads = await db.execute(
        select(Lead).where(Lead.batch_id == payload.batch_id).order_by(Lead.created_at)
    )
    items = list(leads.scalars().all())
    if payload.lead_index < len(items):
        items[payload.lead_index].status = payload.status
        if payload.record_id:
            items[payload.lead_index].feishu_record_id = payload.record_id
        await db.commit()
    return {"status": "ok"}


@router.post("/bridge/tbcexp/{lead_id}")
async def bridge_tbcexp(lead_id: str, db: AsyncSession = Depends(get_db)):
    lead = await db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(404, "Lead not found")
    lead.tbcexp_synced = True
    await db.commit()
    return {"status": "synced", "sourceType": "smart_crm"}


@router.post("/send-email")
async def send_email(req: SendEmailRequest, db: AsyncSession = Depends(get_db)):
    lead = await db.get(Lead, req.lead_id)
    if not lead:
        raise HTTPException(404, "Lead not found")
    to_email = req.to_email or ""
    if not to_email:
        return {"status": "error", "message": "No recipient email"}
    await auth_svc._send_email(
        to_email,
        req.subject or "Partnership opportunity",
        req.body or lead.outreach_email,
    )
    return {"status": "sent"}


@router.get("/schedules")
async def list_schedules(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Schedule).order_by(Schedule.next_run_at))
    return [
        {
            "id": s.id,
            "keyword": s.keyword,
            "industry": s.industry,
            "interval_hours": s.interval_hours,
            "country_iso": s.country_iso,
            "city": s.city,
            "category_l3": s.category_l3,
            "track": s.track,
            "enabled": s.enabled,
            "next_run_at": s.next_run_at.isoformat() if s.next_run_at else None,
        }
        for s in result.scalars().all()
    ]


@router.post("/schedules")
async def add_schedule(req: ScheduleRequest, db: AsyncSession = Depends(get_db)):
    schedule = Schedule(
        keyword=req.keyword,
        industry=req.industry,
        interval_hours=req.interval_hours,
        country_iso=req.country_iso,
        city=req.city,
        category_l3=req.category_l3,
        language=req.language,
        track=req.track,
        next_run_at=datetime.utcnow(),
    )
    db.add(schedule)
    await db.commit()
    await db.refresh(schedule)
    return {"id": schedule.id, "status": "created"}


# --- Brainstorm Lab (Tab6) ---

@router.post("/brainstorm/generate")
async def brainstorm_generate(req: BrainstormRequest, db: AsyncSession = Depends(get_db)):
    session = await brainstorm_svc.generate(
        db,
        country_iso=req.country_iso,
        city=req.city,
        category_l3=req.category_l3,
        language=req.language,
        context={
            "moq": req.moq,
            "certifications": req.certifications,
            "oem_experience": req.oem_experience,
        },
    )
    return {
        "session_id": session.id,
        "cards": brainstorm_svc.session_to_cards(session),
    }


@router.get("/brainstorm/sessions")
async def list_brainstorm_sessions(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(StrategySession).order_by(StrategySession.created_at.desc()).limit(30)
    )
    return [
        {
            "id": s.id,
            "country_iso": s.country_iso,
            "city": s.city,
            "category_l3": s.category_l3,
            "created_at": s.created_at.isoformat(),
        }
        for s in result.scalars().all()
    ]


@router.get("/brainstorm/sessions/{session_id}")
async def get_brainstorm_session(session_id: str, db: AsyncSession = Depends(get_db)):
    session = await db.get(StrategySession, session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    actions = await db.execute(
        select(StrategyAction).where(StrategyAction.session_id == session_id)
    )
    return {
        "session_id": session.id,
        "cards": brainstorm_svc.session_to_cards(session),
        "actions": [
            {
                "id": a.id,
                "action_type": a.action_type,
                "status": a.status,
                "payload": a.payload_json,
            }
            for a in actions.scalars().all()
        ],
    }


@router.post("/brainstorm/actions")
async def brainstorm_action(req: BrainstormActionRequest, db: AsyncSession = Depends(get_db)):
    action = await brainstorm_svc.create_action(
        db, req.session_id, req.action_type, req.payload
    )
    return {"action_id": action.id, "status": action.status}


# --- Market Intel Track B (Tab5) ---

@router.get("/market/anchors")
async def list_anchors(country_iso: str = "", db: AsyncSession = Depends(get_db)):
    q = select(CountryAnchor)
    if country_iso:
        q = q.where(CountryAnchor.country_iso == country_iso.upper())
    result = await db.execute(q)
    return [
        {
            "id": a.id,
            "country_iso": a.country_iso,
            "company_name": a.company_name,
            "website": a.website,
            "anchor_type": a.anchor_type,
            "last_crawled_at": a.last_crawled_at.isoformat() if a.last_crawled_at else None,
        }
        for a in result.scalars().all()
    ]


@router.post("/market/anchors/{anchor_id}/crawl")
async def crawl_anchor(anchor_id: str, db: AsyncSession = Depends(get_db)):
    anchor = await db.get(CountryAnchor, anchor_id)
    if not anchor:
        raise HTTPException(404, "Anchor not found")
    intel = await track_b.crawl_anchor(db, anchor)
    return {
        "intel_id": intel.id,
        "category_l3": intel.category_l3,
        "sales_signal": intel.sales_signal,
        "trend_summary": intel.trend_summary,
    }


@router.get("/market/intel")
async def list_intel(country_iso: str = "", db: AsyncSession = Depends(get_db)):
    q = select(MarketProductIntel).order_by(MarketProductIntel.created_at.desc())
    if country_iso:
        q = q.where(MarketProductIntel.country_iso == country_iso.upper())
    result = await db.execute(q.limit(50))
    return [
        {
            "id": i.id,
            "country_iso": i.country_iso,
            "category_l3": i.category_l3,
            "sales_signal": i.sales_signal,
            "trend_summary": i.trend_summary[:500],
            "l3_heat": i.l3_heat,
        }
        for i in result.scalars().all()
    ]


# --- Track C Import (Tab7) ---

@router.post("/import/csv")
async def import_csv(
    file: UploadFile = File(...),
    country_iso: str = "",
    hs_codes: str = "",
    source: str = "manual",
    db: AsyncSession = Depends(get_db),
):
    content = (await file.read()).decode("utf-8", errors="ignore")
    hs_list = [h.strip() for h in hs_codes.split(",") if h.strip()]
    result = await track_c.import_csv(db, content, country_iso, hs_list, source)
    return result


@router.post("/import/match-domains")
async def match_domains(db: AsyncSession = Depends(get_db)):
    matched = await track_c.match_domains(db)
    return {"matched": matched}


@router.get("/import/leads")
async def list_import_leads(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ImportLead).order_by(ImportLead.created_at.desc()).limit(100)
    )
    return [
        {
            "id": r.id,
            "company_name": r.company_name,
            "country_iso": r.country_iso,
            "hs_code": r.hs_code,
            "domain": r.domain,
            "status": r.status,
        }
        for r in result.scalars().all()
    ]


@router.post("/import/leads/{import_id}/promote")
async def promote_import_lead(import_id: str, db: AsyncSession = Depends(get_db)):
    lead = await track_c.promote_to_leads(db, import_id)
    if not lead:
        raise HTTPException(400, "Could not promote lead")
    return pipeline._lead_dict(lead)


# --- Trade Shows ---

@router.get("/tradeshows")
async def list_tradeshows(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(TradeShow))
    return [
        {
            "id": t.id,
            "name": t.name,
            "country_iso": t.country_iso,
            "exhibitor_list_url": t.exhibitor_list_url,
            "exhibitor_count": t.exhibitor_count,
            "last_crawled_at": t.last_crawled_at.isoformat() if t.last_crawled_at else None,
        }
        for t in result.scalars().all()
    ]


@router.post("/tradeshows/{show_id}/crawl")
async def crawl_tradeshow(show_id: str, db: AsyncSession = Depends(get_db)):
    show = await db.get(TradeShow, show_id)
    if not show:
        raise HTTPException(404, "Trade show not found")
    return await tradeshow_svc.crawl_exhibitors(db, show)


# --- Geo config & scheduler ---

@router.get("/geo/config")
async def geo_config():
    return load_geo_config()


@router.get("/geo/expansion-tiers")
async def expansion_tiers():
    return load_expansion_tiers()


@router.post("/geo/seed")
async def geo_seed(db: AsyncSession = Depends(get_db)):
    await seed_geo_data(db)
    await tradeshow_svc.seed_defaults(db)
    return {"status": "seeded"}


@router.post("/geo/schedules/{country_iso}")
async def generate_country_schedules(
    country_iso: str, interval_hours: int = 24, db: AsyncSession = Depends(get_db)
):
    count = await geo_scheduler.materialize_schedules(db, country_iso, interval_hours)
    return {"created": count}


@router.get("/geo/queue/{country_iso}")
async def country_queue(country_iso: str):
    return geo_scheduler.generate_country_queue(country_iso)


@router.get("/kb/search")
async def kb_search(q: str, limit: int = 10, db: AsyncSession = Depends(get_db)):
    results = await kb_svc.search(db, q, limit)
    return {"query": q, "results": results}


@router.post("/kb/index/{lead_id}")
async def kb_index_lead(lead_id: str, db: AsyncSession = Depends(get_db)):
    lead = await db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(404, "Lead not found")
    text = f"{lead.company_name} {lead.exa_summary} {lead.firecrawl_summary} {lead.keyword}"
    await kb_svc.index_lead(lead_id, text, db)
    return {"status": "indexed", "lead_id": lead_id}


# --- Auth ---

@router.post("/auth/otp/send")
async def send_otp(req: AuthEmailRequest, db: AsyncSession = Depends(get_db)):
    try:
        return await auth_svc.send_otp(db, req.email, req.portal)
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc


@router.post("/auth/otp/verify")
async def verify_otp(req: AuthOtpRequest, db: AsyncSession = Depends(get_db)):
    try:
        session = await auth_svc.verify_otp(db, req.email, req.code, req.portal)
        return {
            "session_token": session.session_token,
            "portal": session.portal,
            "role": session.role,
            "expires_at": session.expires_at.isoformat(),
        }
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/auth/magic/send")
async def send_magic(req: AuthEmailRequest, db: AsyncSession = Depends(get_db)):
    try:
        return await auth_svc.send_magic_link(db, req.email, req.portal)
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc


@router.get("/auth/magic")
async def verify_magic(token: str, portal: str = "admin", db: AsyncSession = Depends(get_db)):
    try:
        session = await auth_svc.verify_magic(db, token, portal)
        return {
            "session_token": session.session_token,
            "portal": session.portal,
            "role": session.role,
        }
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/auth/session")
async def get_auth_session(request: Request, db: AsyncSession = Depends(get_db)):
    token = request.headers.get("X-Session-Token", "")
    if not token:
        raise HTTPException(401, "No session")
    session = await auth_svc.get_session(db, token)
    if not session:
        raise HTTPException(401, "Invalid session")
    return {
        "email": session.email,
        "portal": session.portal,
        "role": session.role,
        "expires_at": session.expires_at.isoformat(),
    }
