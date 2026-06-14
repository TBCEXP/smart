from __future__ import annotations

import asyncio
import csv
import io
import json
import os
import zipfile
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import (
    AuthEmailRequest,
    AuthOtpRequest,
    BrainstormActionRequest,
    BrainstormRequest,
    ConfigPayload,
    CatalogDocumentRequest,
    CatalogUploadUrlRequest,
    ContentBatchGenerateRequest,
    ContentGenerateRequest,
    ContentUpdateRequest,
    FactoryRequest,
    FeishuWebhookRequest,
    OrderCreateRequest,
    OrderLineRequest,
    OrderUpdateRequest,
    CatalogDocumentUpdateRequest,
    OutreachLogRequest,
    OutreachReplyRequest,
    PilotRequest,
    RunRequest,
    ScheduleRequest,
    SendEmailRequest,
    ShareLinkRequest,
    FileTransferRequest,
    FileUploadUrlRequest,
    BarcodeValidateRequest,
    PrepressReviewRequest,
    ProductionInspectionRequest,
    ProductionHumanReviewRequest,
    TradeShowCrawlRequest,
)
from app.database import ASYNC_DB_URL, get_session
from app.models.entities import (
    Batch,
    CatalogDocument,
    ContentDraft,
    CountryAnchor,
    Factory,
    ImportLead,
    Lead,
    MarketProductIntel,
    OutreachLog,
    Schedule,
    SalesOrder,
    SalesOrderLine,
    FileTransfer,
    PrepressReview,
    ProductionInspection,
    ShareLink,
    StrategyAction,
    StrategySession,
    TradeShow,
)
from app.services.access import is_sales_scoped, session_from_request
from app.services.apollo_client import ApolloClient
from app.services.auth import AuthService
from app.services.brainstorm import BrainstormService
from app.services.catalog import (
    catalog_dict,
    customer_can_view,
    seed_catalog_documents,
)
from app.services.config_store import ConfigStore
from app.services.content_studio import CONTENT_TYPES, ContentStudioService
from app.services.data_loader import (
    load_batch_file,
    load_expansion_tiers,
    load_geo_config,
    resolve_exa_query,
)
from app.services.exa_utils import build_semantic_exa_query
from app.services.integrations_probe import IntegrationsProbeService
from app.services.geo_track import GeoSchedulerService, TrackCService, TradeShowService
from app.services.knowledge_base import KnowledgeBaseService
from app.services.latam_pilot import LatamPilotService
from app.services.phase1 import (
    catalog_tree,
    factory_dict,
    next_order_no,
    order_dict,
    order_line_dict,
    recalc_order_total,
    seed_factories,
)
from app.services.pipeline import PipelineService, TrackBService, seed_geo_data
from app.config import settings
from app.services.r2_client import R2Client
from app.services.files import file_dict
from app.services.notify import notify_share_link
from app.services.prepress import review_dict, run_prepress_analysis, seed_prepress_reviews
from app.services.production_inspect import (
    inspection_dict,
    run_production_analysis,
    seed_production_inspections,
)
from app.services.barcode_engine import generate_barcode_svg, validate_barcode
from app.services.share import create_share_link, resolve_share, seed_portal_demo
from app.services.tbcexp_client import TbcexpClient
from app.services.feishu_client import FeishuClient

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
content_svc = ContentStudioService()
pilot_svc = LatamPilotService()
probe_svc = IntegrationsProbeService()
tbcexp_svc = TbcexpClient()
feishu_svc = FeishuClient()
apollo_svc = ApolloClient()
r2_svc = R2Client()

# In-memory SSE queues and scheduler state
_sse_queues: dict[str, asyncio.Queue] = {}
_scheduler_task: asyncio.Task | None = None


async def get_db():
    async with get_session() as session:
        yield session


@router.get("/health")
async def health():
    return {
        "status": "ok",
        "time": datetime.utcnow().isoformat(),
        "version": os.getenv("VERSION", "1.5.0"),
        "db": "postgresql" if "postgresql" in ASYNC_DB_URL else "sqlite",
    }


@router.get("/integrations/status")
async def integrations_status():
    """Check which external APIs are configured (vs mock mode)."""
    cfg = config_store.load()
    keys = [
        ("exa", "exa_api_key", "Exa 语义搜索"),
        ("firecrawl", "firecrawl_api_key", "Firecrawl 网站分析"),
        ("openai", "openai_api_key", "OpenAI 开发信/Brainstorm"),
        ("feishu", "feishu_app_id", "飞书入库"),
        ("resend", "resend_api_key", "邮件 OTP/通知"),
        ("apollo", "apollo_api_key", "Apollo 联系人补充"),
        ("r2", "r2_account_id", "Cloudflare R2 目录存储"),
        ("importgenius", "importgenius_api_key", "海关数据"),
        ("tbcexp", "tbcexp_api_url", "TBCEXP ERP"),
    ]
    services = []
    configured = 0
    for sid, key, label in keys:
        val = cfg.get(key, "")
        ok = bool(val and val.strip())
        if ok:
            configured += 1
        services.append({"id": sid, "label": label, "configured": ok, "mode": "live" if ok else "mock"})
    return {
        "configured_count": configured,
        "total": len(keys),
        "production_ready": configured >= 4,
        "note": "production_ready 需要至少 Exa+Firecrawl+OpenAI+飞书",
        "services": services,
    }


@router.post("/integrations/probe")
async def integrations_probe():
    """对已配置的 API Key 做轻量连通性探测。"""
    return await probe_svc.probe_all()


@router.post("/integrations/feishu/test-write")
async def feishu_test_write():
    """写入一条测试记录，验证飞书表格字段映射（需登录）。"""
    return await probe_svc.test_feishu_write()


async def _phase_business_stats(db: AsyncSession) -> dict[str, Any]:
    """Phase 1/2 业务数据统计。"""
    cfg = config_store.load()
    factories = (
        await db.execute(
            select(func.count()).select_from(Factory).where(Factory.active.is_(True))
        )
    ).scalar_one()
    orders = (
        await db.execute(select(func.count()).select_from(SalesOrder))
    ).scalar_one()
    leads = (await db.execute(select(func.count()).select_from(Lead))).scalar_one()
    catalogs = (
        await db.execute(
            select(func.count())
            .select_from(CatalogDocument)
            .where(CatalogDocument.active.is_(True))
        )
    ).scalar_one()
    shares = (
        await db.execute(
            select(func.count()).select_from(ShareLink).where(ShareLink.active.is_(True))
        )
    ).scalar_one()
    portal_orders = (
        await db.execute(
            select(func.count()).select_from(SalesOrder).where(
                SalesOrder.customer_email == "customer@example.com"
            )
        )
    ).scalar_one()
    file_transfers = (
        await db.execute(
            select(func.count())
            .select_from(FileTransfer)
            .where(FileTransfer.active.is_(True))
        )
    ).scalar_one()
    prepress_reviews = (
        await db.execute(
            select(func.count())
            .select_from(PrepressReview)
            .where(PrepressReview.active.is_(True))
        )
    ).scalar_one()
    production_inspections = (
        await db.execute(
            select(func.count())
            .select_from(ProductionInspection)
            .where(ProductionInspection.active.is_(True))
        )
    ).scalar_one()
    return {
        "phase1": {
            "factories": factories,
            "orders": orders,
            "leads": leads,
            "erp_configured": bool(cfg.get("tbcexp_api_url") and cfg.get("tbcexp_api_token")),
        },
        "phase2": {
            "catalog_documents": catalogs,
            "share_links": shares,
            "r2_configured": bool(cfg.get("r2_account_id") and cfg.get("r2_access_key_id")),
            "portal_demo_orders": portal_orders,
        },
        "phase3": {
            "file_transfers": file_transfers,
            "notify_service": True,
        },
        "phase4": {
            "prepress_reviews": prepress_reviews,
            "rule_engine": True,
        },
        "phase5": {
            "production_inspections": production_inspections,
            "opencv_align": True,
        },
    }


@router.get("/system/readiness")
async def system_readiness(db: AsyncSession = Depends(get_db)):
    """第零期 + 1.5 期 + Phase 1/2 合并就绪检查（部署后一键验收）。"""
    cfg = config_store.load()
    integ = await integrations_status()
    mx = await pilot_svc.status(db, "MX")
    due = await geo_scheduler.get_due_schedules(db)
    biz = await _phase_business_stats(db)
    return {
        "health": "ok",
        "integrations": integ,
        "production_ready": integ.get("production_ready", False),
        "ingest_mode": cfg.get("ingest_mode", "review"),
        "scheduler_enabled": cfg.get("scheduler_enabled", False),
        "mx_pilot": {
            "intel_reports": mx["totals"]["intel_reports"],
            "active_schedules": mx["totals"]["active_schedules"],
            "latest_run": mx.get("latest_run"),
        },
        "due_schedules": len(due),
        "checklist": {
            "api_keys_configured": integ.get("configured_count", 0) >= 4,
            "pilot_has_run": mx.get("latest_run") is not None,
            "schedules_queued": mx["totals"]["active_schedules"] > 0,
            "ready_for_live_pilot": integ.get("production_ready", False),
            "phase1_factories_seeded": biz["phase1"]["factories"] >= 1,
            "phase1_orders_api": True,
            "phase2_catalog_seeded": biz["phase2"]["catalog_documents"] >= 1,
            "phase2_portal_ready": biz["phase2"]["portal_demo_orders"] >= 1,
            "phase2_r2_optional": biz["phase2"]["r2_configured"],
            "phase3_files_seeded": biz.get("phase3", {}).get("file_transfers", 0) >= 1,
            "phase3_share_notify": biz.get("phase3", {}).get("notify_service", False),
            "phase4_prepress_seeded": biz.get("phase4", {}).get("prepress_reviews", 0) >= 1,
            "phase4_rule_engine": biz.get("phase4", {}).get("rule_engine", False),
            "phase5_inspection_seeded": biz.get("phase5", {}).get("production_inspections", 0) >= 1,
            "phase5_opencv_align": biz.get("phase5", {}).get("opencv_align", False),
        },
        "business": biz,
        "milestones": (await _phase15_milestones(db))["milestones"],
        "kb": {
            "db_mode": "postgresql" if "postgresql" in ASYNC_DB_URL else "sqlite",
            "search_engine": "pgvector" if "postgresql" in ASYNC_DB_URL else "cosine_json",
        },
    }


@router.get("/system/handoff-report")
async def handoff_report(db: AsyncSession = Depends(get_db)):
    """导出 Phase 0–2 交接 Markdown 报告。"""
    ready = await system_readiness(db)
    ms = ready.get("milestones", {})
    biz = ready.get("business", {})
    integ = ready.get("integrations", {})
    lines = [
        "# SMART CRM 交接报告",
        "",
        f"- 生成时间: {datetime.utcnow().isoformat()}Z",
        f"- production_ready: {ready.get('production_ready')}",
        f"- API Keys: {integ.get('configured_count', 0)}/{integ.get('total', 0)}",
        "",
        "## 里程碑 (Phase 1.5)",
        "",
        f"- 1.5.4 飞书≥30: {'✓' if ms.get('1_5_4_feishu_30') else '○'}",
        f"- 1.5.5 WhatsApp≥5: {'✓' if ms.get('1_5_5_whatsapp_5') else '○'}",
        f"- 1.5.6 Track C: {'✓' if ms.get('1_5_6_track_c') else '○'}",
        f"- 1.5.7 KB召回: {'✓' if ms.get('1_5_7_kb_recall') else '○'}",
        "",
        "## Phase 1 员工业务",
        "",
        f"- 工厂: {biz.get('phase1', {}).get('factories', 0)}",
        f"- 订单: {biz.get('phase1', {}).get('orders', 0)}",
        f"- 线索: {biz.get('phase1', {}).get('leads', 0)}",
        f"- ERP 已配置: {biz.get('phase1', {}).get('erp_configured')}",
        "",
        "## Phase 2 目录/门户",
        "",
        f"- 目录元数据: {biz.get('phase2', {}).get('catalog_documents', 0)}",
        f"- 分享链接: {biz.get('phase2', {}).get('share_links', 0)}",
        f"- R2 已配置: {biz.get('phase2', {}).get('r2_configured')}",
        f"- 门户演示订单: {biz.get('phase2', {}).get('portal_demo_orders', 0)}",
        "",
        "## Phase 3 大文件/通知",
        "",
        f"- 大文件元数据: {biz.get('phase3', {}).get('file_transfers', 0)}",
        f"- 分享邮件通知: {'✓' if biz.get('phase3', {}).get('notify_service') else '○'}",
        "",
        "## Phase 4 印刷前稿 AI",
        "",
        f"- 前稿比对任务: {biz.get('phase4', {}).get('prepress_reviews', 0)}",
        f"- 规则引擎（条码/OCR/图形 diff）: {'✓' if biz.get('phase4', {}).get('rule_engine') else '○'}",
        "",
        "## Phase 5 大货实拍 AI",
        "",
        f"- 实拍检测任务: {biz.get('phase5', {}).get('production_inspections', 0)}",
        f"- OpenCV 对齐比对: {'✓' if biz.get('phase5', {}).get('opencv_align') else '○'}",
        "",
        "## 验收命令",
        "",
        "```bash",
        "bash scripts/run_all_tests.sh http://YOUR_HOST:8000",
        "bash scripts/phase3_verify.sh http://YOUR_HOST:8000",
        "bash scripts/phase4_verify.sh http://YOUR_HOST:8000",
        "bash scripts/phase5_verify.sh http://YOUR_HOST:8000",
        "bash scripts/phase2_live.sh http://YOUR_HOST:8000",
        "bash scripts/prod_onboard.sh http://YOUR_HOST:8000 --full",
        "```",
    ]
    body = "\n".join(lines)
    return PlainTextResponse(
        body,
        media_type="text/markdown",
        headers={"Content-Disposition": "attachment; filename=smart-crm-handoff.md"},
    )


@router.get("/config")
async def get_config():
    return config_store.masked()


@router.post("/config")
async def save_config(payload: ConfigPayload):
    return config_store.save(payload)


@router.get("/exa/preview-query")
async def preview_exa_query(
    keyword: str = "",
    category_l3: str = "",
    country_iso: str = "",
    city: str = "",
    language: str = "es",
    search_type: str = "standard",
):
    """Preview resolved L3 template + semantic Exa query before running Track A."""
    resolved = resolve_exa_query(
        keyword,
        category_l3=category_l3,
        city=city,
        country_iso=country_iso,
        language=language,
        search_type=search_type,
    )
    semantic = build_semantic_exa_query(
        resolved, search_type, country_iso, city, language
    )
    return {
        "keyword": keyword,
        "category_l3": category_l3,
        "country_iso": country_iso,
        "city": city,
        "language": language,
        "search_type": search_type,
        "resolved_query": resolved,
        "semantic_query": semantic,
        "uses_l3_template": bool(category_l3),
    }


@router.get("/leads")
async def list_leads(
    request: Request,
    db: AsyncSession = Depends(get_db),
    country_iso: str = "",
    status: str = "",
    track: str = "",
    lead_score: str = "",
    mine: int = 0,
    limit: int = 50,
    offset: int = 0,
):
    """Phase 1 线索查询 — sales 角色自动仅看自己的线索。"""
    q = select(Lead).order_by(Lead.created_at.desc())
    session = await session_from_request(request, db)
    if mine:
        if not session:
            raise HTTPException(401, "mine=1 requires session")
        q = q.where(Lead.assigned_to == session.email)
    elif is_sales_scoped(session):
        q = q.where(Lead.assigned_to == session.email)
    if country_iso:
        q = q.where(Lead.country_iso == country_iso.upper())
    if status:
        q = q.where(Lead.status == status)
    if track:
        q = q.where(Lead.track == track)
    if lead_score:
        q = q.where(Lead.lead_score == lead_score.upper()[:1])
    q = q.limit(min(max(limit, 1), 200)).offset(max(offset, 0))
    result = await db.execute(q)
    rows = result.scalars().all()
    return {
        "total_returned": len(rows),
        "offset": offset,
        "limit": limit,
        "leads": [_lead_public_dict(l) for l in rows],
    }


def _lead_public_dict(lead: Lead) -> dict[str, Any]:
    data = pipeline._lead_dict(lead)
    data["feishu_record_id"] = lead.feishu_record_id
    data["assigned_to"] = lead.assigned_to
    data["confirmed_by"] = lead.confirmed_by
    data["tbcexp_synced"] = lead.tbcexp_synced
    data["contact_email"] = lead.contact_email
    data["contact_name"] = lead.contact_name
    data["contact_title"] = lead.contact_title
    return data


@router.get("/admin/summary")
async def admin_summary(request: Request, db: AsyncSession = Depends(get_db)):
    """Phase 1 员工后台汇总（按角色统计）。"""
    session = await session_from_request(request, db)
    lead_q = select(Lead)
    order_q = select(SalesOrder)
    if is_sales_scoped(session):
        lead_q = lead_q.where(Lead.assigned_to == session.email)
        order_q = order_q.where(SalesOrder.assigned_to == session.email)

    leads = (await db.execute(lead_q)).scalars().all()
    orders = (await db.execute(order_q)).scalars().all()
    factories = (await db.execute(select(Factory).where(Factory.active.is_(True)))).scalars().all()

    return {
        "user": {
            "email": session.email if session else None,
            "role": session.role if session else None,
            "scoped": is_sales_scoped(session),
        },
        "leads": {
            "total": len(leads),
            "feishu_synced": sum(1 for l in leads if l.feishu_record_id),
            "erp_synced": sum(1 for l in leads if l.tbcexp_synced),
            "assigned": sum(1 for l in leads if l.assigned_to),
        },
        "orders": {
            "total": len(orders),
            "draft": sum(1 for o in orders if o.status == "draft"),
            "confirmed": sum(1 for o in orders if o.status == "confirmed"),
        },
        "factories": len(factories),
    }


@router.get("/feishu/records/{record_id}")
async def get_feishu_record(record_id: str):
    """飞书记录只读查询（核对入库字段）。"""
    return await feishu_svc.get_record(record_id)


@router.get("/catalog/documents")
async def list_catalog_documents(
    db: AsyncSession = Depends(get_db),
    doc_type: str = "",
):
    q = (
        select(CatalogDocument)
        .where(CatalogDocument.active.is_(True))
        .order_by(CatalogDocument.created_at.desc())
    )
    if doc_type:
        q = q.where(CatalogDocument.doc_type == doc_type)
    result = await db.execute(q)
    out = []
    for doc in result.scalars().all():
        factory = await db.get(Factory, doc.factory_id)
        out.append(catalog_dict(doc, factory, r2_svc))
    return out


@router.post("/catalog/documents")
async def create_catalog_document(
    req: CatalogDocumentRequest, db: AsyncSession = Depends(get_db)
):
    factory = await db.get(Factory, req.factory_id)
    if not factory:
        raise HTTPException(404, "Factory not found")
    allowed_types = {"catalog", "quote", "price_list"}
    doc_type = req.doc_type if req.doc_type in allowed_types else "catalog"
    doc = CatalogDocument(
        factory_id=req.factory_id,
        title=req.title,
        title_en=req.title_en,
        category_l3=req.category_l3,
        doc_type=doc_type,
        file_url=req.file_url or "r2://pending/upload.pdf",
        pages=req.pages,
        file_size_mb=req.file_size_mb,
        authorized_emails=req.authorized_emails,
        notes=req.notes,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return catalog_dict(doc, factory, r2_svc)


@router.get("/catalog/documents/{doc_id}/download-url")
async def catalog_download_url(
    doc_id: str, request: Request, db: AsyncSession = Depends(get_db)
):
    """获取目录 PDF 签名下载链接（门户客户或员工）。"""
    doc = await db.get(CatalogDocument, doc_id)
    if not doc or not doc.active:
        raise HTTPException(404, "Catalog not found")
    session = await session_from_request(request, db)
    if not session:
        raise HTTPException(401, "Session required")
    if session.portal == "portal" and not customer_can_view(doc, session.email):
        raise HTTPException(403, "Not authorized for this catalog")
    factory = await db.get(Factory, doc.factory_id)
    resolved = r2_svc.resolve_download_url(doc.file_url)
    return {
        "id": doc.id,
        "title": doc.title,
        "file_url": doc.file_url,
        "factory_code": factory.code if factory else "",
        **resolved,
    }


@router.post("/catalog/documents/{doc_id}/upload-url")
async def catalog_upload_url(
    doc_id: str,
    req: CatalogUploadUrlRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """生成 R2 预签名上传 URL（员工后台）。"""
    session = await session_from_request(request, db)
    if not session or session.portal != "admin":
        raise HTTPException(401, "Admin session required")
    doc = await db.get(CatalogDocument, doc_id)
    if not doc or not doc.active:
        raise HTTPException(404, "Catalog not found")
    key = req.key.strip()
    if not key:
        parsed = R2Client.parse_r2_url(doc.file_url)
        if parsed:
            key = parsed[1]
        else:
            safe_title = "".join(c if c.isalnum() else "-" for c in doc.title[:32]).strip("-")
            key = f"catalogs/{safe_title or doc.id}.pdf"
    result = r2_svc.presign_put(
        key=key,
        ttl_seconds=max(60, min(req.ttl_seconds, 3600)),
        content_type=req.content_type,
    )
    if req.update_file_url and result.get("file_url"):
        doc.file_url = result["file_url"]
        await db.commit()
    return {"document_id": doc.id, **result}


@router.patch("/catalog/documents/{doc_id}")
async def update_catalog_document(
    doc_id: str,
    req: CatalogDocumentUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """更新目录元数据（授权邮箱、标题等）。"""
    session = await session_from_request(request, db)
    if not session or session.portal != "admin":
        raise HTTPException(401, "Admin session required")
    doc = await db.get(CatalogDocument, doc_id)
    if not doc:
        raise HTTPException(404, "Catalog not found")
    if req.title:
        doc.title = req.title
    if req.title_en:
        doc.title_en = req.title_en
    if req.category_l3:
        doc.category_l3 = req.category_l3
    if req.doc_type and req.doc_type in {"catalog", "quote", "price_list"}:
        doc.doc_type = req.doc_type
    if req.authorized_emails is not None:
        doc.authorized_emails = req.authorized_emails
    if req.pages is not None:
        doc.pages = req.pages
    if req.file_size_mb is not None:
        doc.file_size_mb = req.file_size_mb
    if req.notes:
        doc.notes = req.notes
    if req.active is not None:
        doc.active = req.active
    await db.commit()
    await db.refresh(doc)
    factory = await db.get(Factory, doc.factory_id)
    return catalog_dict(doc, factory, r2_svc)


@router.get("/files/transfers")
async def list_file_transfers(db: AsyncSession = Depends(get_db)):
    """大文件中转元数据列表（员工后台 / 验收脚本）。"""
    result = await db.execute(
        select(FileTransfer)
        .where(FileTransfer.active.is_(True))
        .order_by(FileTransfer.created_at.desc())
    )
    return [file_dict(t, r2_svc) for t in result.scalars().all()]


@router.post("/files/transfers")
async def create_file_transfer(
    req: FileTransferRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """创建大文件元数据（实体文件通过 R2 上传）。"""
    session = await session_from_request(request, db)
    if not session or session.portal != "admin":
        raise HTTPException(401, "Admin session required")
    transfer = FileTransfer(
        title=req.title,
        customer_email=req.customer_email,
        order_id=req.order_id or None,
        file_url=req.file_url or "r2://smart-crm/files/pending.bin",
        file_size_mb=req.file_size_mb,
        content_type=req.content_type,
        notes=req.notes,
        created_by=session.email,
    )
    db.add(transfer)
    await db.commit()
    await db.refresh(transfer)
    return file_dict(transfer, r2_svc)


@router.post("/files/transfers/{transfer_id}/upload-url")
async def file_upload_url(
    transfer_id: str,
    req: FileUploadUrlRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """生成 R2 预签名上传 URL（大文件）。"""
    session = await session_from_request(request, db)
    if not session or session.portal != "admin":
        raise HTTPException(401, "Admin session required")
    transfer = await db.get(FileTransfer, transfer_id)
    if not transfer or not transfer.active:
        raise HTTPException(404, "File transfer not found")
    key = req.key.strip()
    if not key:
        parsed = R2Client.parse_r2_url(transfer.file_url)
        if parsed:
            key = parsed[1]
        else:
            safe_title = "".join(c if c.isalnum() else "-" for c in transfer.title[:32]).strip("-")
            key = f"files/{safe_title or transfer.id}.bin"
    result = r2_svc.presign_put(
        key=key,
        ttl_seconds=max(60, min(req.ttl_seconds, 3600)),
        content_type=req.content_type or transfer.content_type,
    )
    if req.update_file_url and result.get("file_url"):
        transfer.file_url = result["file_url"]
        await db.commit()
    return {"transfer_id": transfer.id, **result}


@router.post("/prepress/barcode/validate")
async def prepress_barcode_validate(req: BarcodeValidateRequest):
    """条码校验（EAN-13 / Code128 规则引擎）。"""
    return validate_barcode(req.value, req.symbology)


@router.post("/prepress/barcode/generate")
async def prepress_barcode_generate(req: BarcodeValidateRequest):
    """生成条码 SVG（用于前稿预览）。"""
    return generate_barcode_svg(req.value, req.symbology)


@router.get("/prepress/reviews")
async def list_prepress_reviews(db: AsyncSession = Depends(get_db)):
    """印刷前稿比对任务列表。"""
    result = await db.execute(
        select(PrepressReview)
        .where(PrepressReview.active.is_(True))
        .order_by(PrepressReview.created_at.desc())
    )
    return [review_dict(r) for r in result.scalars().all()]


@router.post("/prepress/reviews")
async def create_prepress_review(
    req: PrepressReviewRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """创建前稿比对任务。"""
    session = await session_from_request(request, db)
    if not session or session.portal != "admin":
        raise HTTPException(401, "Admin session required")
    review = PrepressReview(
        title=req.title,
        order_id=req.order_id or None,
        reference_image=req.reference_image,
        candidate_image=req.candidate_image,
        barcode_expected=req.barcode_expected,
        barcode_symbology=req.barcode_symbology,
        reference_text=req.reference_text,
        candidate_text=req.candidate_text,
        notes=req.notes,
        created_by=session.email,
        status="draft",
    )
    db.add(review)
    await db.commit()
    await db.refresh(review)
    return review_dict(review)


@router.get("/prepress/reviews/{review_id}")
async def get_prepress_review(review_id: str, db: AsyncSession = Depends(get_db)):
    review = await db.get(PrepressReview, review_id)
    if not review or not review.active:
        raise HTTPException(404, "Prepress review not found")
    return review_dict(review)


@router.post("/prepress/reviews/{review_id}/run")
async def run_prepress_review(
    review_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """运行条码 + 文本 diff + 图形 diff 规则引擎。"""
    session = await session_from_request(request, db)
    if not session or session.portal != "admin":
        raise HTTPException(401, "Admin session required")
    review = await db.get(PrepressReview, review_id)
    if not review or not review.active:
        raise HTTPException(404, "Prepress review not found")
    review.status = "running"
    await db.commit()
    result = run_prepress_analysis(review)
    review.result_json = result
    review.verdict = result.get("verdict", "pending")
    review.status = "done"
    review.ran_at = datetime.utcnow()
    await db.commit()
    await db.refresh(review)
    return review_dict(review)


@router.get("/inspections/production")
async def list_production_inspections(db: AsyncSession = Depends(get_db)):
    """大货实拍检测任务列表。"""
    result = await db.execute(
        select(ProductionInspection)
        .where(ProductionInspection.active.is_(True))
        .order_by(ProductionInspection.created_at.desc())
    )
    return [inspection_dict(r) for r in result.scalars().all()]


@router.post("/inspections/production")
async def create_production_inspection(
    req: ProductionInspectionRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    session = await session_from_request(request, db)
    if not session or session.portal != "admin":
        raise HTTPException(401, "Admin session required")
    row = ProductionInspection(
        title=req.title,
        order_id=req.order_id or None,
        prepress_review_id=req.prepress_review_id or None,
        approved_image=req.approved_image or "fixture://inspection/approved_box.png",
        photo_image=req.photo_image or "fixture://inspection/production_photo.png",
        notes=req.notes,
        created_by=session.email,
        status="draft",
        human_review_status="pending",
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return inspection_dict(row)


@router.get("/inspections/production/{inspection_id}")
async def get_production_inspection(inspection_id: str, db: AsyncSession = Depends(get_db)):
    row = await db.get(ProductionInspection, inspection_id)
    if not row or not row.active:
        raise HTTPException(404, "Production inspection not found")
    return inspection_dict(row)


@router.post("/inspections/production/{inspection_id}/run")
async def run_production_inspection(
    inspection_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """OpenCV 对齐后与确稿比对。"""
    session = await session_from_request(request, db)
    if not session or session.portal != "admin":
        raise HTTPException(401, "Admin session required")
    row = await db.get(ProductionInspection, inspection_id)
    if not row or not row.active:
        raise HTTPException(404, "Production inspection not found")
    row.status = "running"
    await db.commit()
    result = run_production_analysis(row)
    row.result_json = result
    row.verdict = result.get("verdict", "pending")
    row.status = "done"
    row.ran_at = datetime.utcnow()
    await db.commit()
    await db.refresh(row)
    return inspection_dict(row)


@router.patch("/inspections/production/{inspection_id}/review")
async def human_review_production_inspection(
    inspection_id: str,
    req: ProductionHumanReviewRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """人工终审（通过/驳回）。"""
    session = await session_from_request(request, db)
    if not session or session.portal != "admin":
        raise HTTPException(401, "Admin session required")
    row = await db.get(ProductionInspection, inspection_id)
    if not row or not row.active:
        raise HTTPException(404, "Production inspection not found")
    status = req.human_review_status.strip().lower()
    if status not in {"approved", "rejected", "pending"}:
        raise HTTPException(400, "human_review_status must be approved/rejected/pending")
    row.human_review_status = status
    row.human_review_notes = req.human_review_notes
    row.human_reviewed_by = session.email
    row.human_reviewed_at = datetime.utcnow()
    await db.commit()
    await db.refresh(row)
    return inspection_dict(row)


@router.post("/leads/{lead_id}/enrich-contact")
async def enrich_lead_contact(lead_id: str, db: AsyncSession = Depends(get_db)):
    """Apollo 联系人补充（L4），写入 lead.contact_* 字段。"""
    lead = await db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(404, "Lead not found")
    result = await apollo_svc.enrich_lead(lead)
    if result.get("contact_email"):
        lead.contact_email = result["contact_email"]
    if result.get("contact_name"):
        lead.contact_name = result["contact_name"]
    if result.get("contact_title"):
        lead.contact_title = result["contact_title"]
    await db.commit()
    return {"lead_id": lead_id, **result}


@router.get("/bridge/tbcexp/status/{lead_id}")
async def tbcexp_sync_status(lead_id: str, db: AsyncSession = Depends(get_db)):
    lead = await db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(404, "Lead not found")
    return {
        "lead_id": lead_id,
        "tbcexp_synced": lead.tbcexp_synced,
        "feishu_record_id": lead.feishu_record_id,
        "assigned_to": lead.assigned_to,
        "erp_configured": tbcexp_svc._configured(),
    }


@router.get("/bridge/tbcexp/orders")
async def tbcexp_list_orders(request: Request, limit: int = 20):
    """TBCEXP ERP 订单只读拉取（需员工登录）。"""
    async with get_session() as db:
        session = await session_from_request(request, db)
        if not session or session.portal != "admin":
            raise HTTPException(401, "Admin session required")
    safe_limit = max(1, min(limit, 100))
    return await tbcexp_svc.list_orders(safe_limit)


@router.get("/catalog/tree")
async def get_catalog_tree():
    """Phase 1 三级品类树（只读，源自 geo_config）。"""
    return catalog_tree()


@router.get("/factories")
async def list_factories(db: AsyncSession = Depends(get_db), active_only: bool = True):
    q = select(Factory).order_by(Factory.code)
    if active_only:
        q = q.where(Factory.active.is_(True))
    result = await db.execute(q)
    return [factory_dict(f) for f in result.scalars().all()]


@router.post("/factories")
async def create_factory(req: FactoryRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(Factory).where(Factory.code == req.code))
    if existing.scalar_one_or_none():
        raise HTTPException(409, "Factory code already exists")
    factory = Factory(
        code=req.code,
        name_zh=req.name_zh,
        name_en=req.name_en,
        country=req.country,
        city=req.city,
        contact_name=req.contact_name,
        contact_email=req.contact_email,
        category_focus=req.category_focus,
        moq_default=req.moq_default,
        notes=req.notes,
    )
    db.add(factory)
    await db.commit()
    await db.refresh(factory)
    return factory_dict(factory)


@router.get("/orders")
async def list_orders(
    request: Request,
    db: AsyncSession = Depends(get_db),
    status: str = "",
    assigned_to: str = "",
    limit: int = 50,
):
    q = select(SalesOrder).order_by(SalesOrder.created_at.desc())
    session = await session_from_request(request, db)
    if is_sales_scoped(session):
        q = q.where(SalesOrder.assigned_to == session.email)
    elif assigned_to:
        q = q.where(SalesOrder.assigned_to == assigned_to)
    if status:
        q = q.where(SalesOrder.status == status)
    result = await db.execute(q.limit(min(limit, 100)))
    orders = result.scalars().all()
    out = []
    for order in orders:
        lines = await db.execute(
            select(SalesOrderLine).where(SalesOrderLine.order_id == order.id)
        )
        out.append(order_dict(order, list(lines.scalars().all())))
    return out


@router.post("/orders")
async def create_order(
    req: OrderCreateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    assigned = req.assigned_to
    if not assigned and hasattr(request.state, "user_email"):
        assigned = request.state.user_email
    order = SalesOrder(
        order_no=next_order_no(),
        customer_name=req.customer_name,
        customer_email=req.customer_email,
        country_iso=req.country_iso.upper(),
        currency=req.currency,
        factory_id=req.factory_id or None,
        lead_id=req.lead_id or None,
        notes=req.notes,
        assigned_to=assigned,
        status="draft",
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)
    return order_dict(order, [])


@router.post("/orders/from-lead/{lead_id}")
async def create_order_from_lead(
    lead_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """从确认线索一键生成草稿订单。"""
    lead = await db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(404, "Lead not found")
    session = await session_from_request(request, db)
    assigned = session.email if session else lead.assigned_to
    order = SalesOrder(
        order_no=next_order_no(),
        customer_name=lead.company_name,
        country_iso=lead.country_iso,
        lead_id=lead.id,
        assigned_to=assigned,
        notes=f"From lead {lead.id} · {lead.category_l3}",
        status="draft",
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)
    return order_dict(order, [])


@router.get("/orders/{order_id}")
async def get_order(order_id: str, db: AsyncSession = Depends(get_db)):
    order = await db.get(SalesOrder, order_id)
    if not order:
        raise HTTPException(404, "Order not found")
    lines = await db.execute(select(SalesOrderLine).where(SalesOrderLine.order_id == order_id))
    return order_dict(order, list(lines.scalars().all()))


@router.patch("/orders/{order_id}")
async def update_order(
    order_id: str,
    req: OrderUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """更新订单状态/客户信息（员工后台）。"""
    order = await db.get(SalesOrder, order_id)
    if not order:
        raise HTTPException(404, "Order not found")
    session = await session_from_request(request, db)
    if is_sales_scoped(session) and order.assigned_to != session.email:
        raise HTTPException(403, "Not your order")
    if req.status:
        allowed = {"draft", "confirmed", "cancelled", "shipped"}
        if req.status not in allowed:
            raise HTTPException(400, f"Invalid status, allowed: {allowed}")
        order.status = req.status
    if req.customer_name:
        order.customer_name = req.customer_name
    if req.customer_email:
        order.customer_email = req.customer_email
    if req.notes:
        order.notes = req.notes
    if req.assigned_to and (not session or session.role == "admin"):
        order.assigned_to = req.assigned_to
    await db.commit()
    await db.refresh(order)
    lines = await db.execute(select(SalesOrderLine).where(SalesOrderLine.order_id == order_id))
    return order_dict(order, list(lines.scalars().all()))


@router.post("/orders/{order_id}/lines")
async def add_order_line(
    order_id: str,
    req: OrderLineRequest,
    db: AsyncSession = Depends(get_db),
):
    order = await db.get(SalesOrder, order_id)
    if not order:
        raise HTTPException(404, "Order not found")
    line = SalesOrderLine(
        order_id=order_id,
        sku=req.sku,
        product_name=req.product_name,
        category_l3=req.category_l3,
        qty=max(1, req.qty),
        unit_price=req.unit_price,
        factory_id=req.factory_id or order.factory_id,
        notes=req.notes,
    )
    db.add(line)
    await db.commit()
    await db.refresh(line)
    total = await recalc_order_total(db, order_id)
    return {"line": order_line_dict(line), "order_total": total}


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
async def confirm_lead(lead_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    lead = await db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(404, "Lead not found")
    lead.status = "待联系"
    if hasattr(request.state, "user_email"):
        lead.assigned_to = request.state.user_email
        lead.confirmed_by = request.state.user_email
    from app.services.feishu_client import FeishuClient

    feishu = FeishuClient()
    feishu_mode = "mock"
    if feishu._configured():
        feishu_mode = "live"
        try:
            record_id = await feishu.create_record(lead, lead.batch_id or "")
            if not record_id:
                raise HTTPException(502, "Feishu write returned empty record_id")
            lead.feishu_record_id = record_id
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(502, f"Feishu write failed: {exc}") from exc
    text = f"{lead.company_name} {lead.exa_summary} {lead.firecrawl_summary} {lead.keyword}"
    try:
        await kb_svc.index_lead(lead_id, text, db)
    except Exception:
        pass
    await db.commit()
    return {
        "status": "confirmed",
        "lead_id": lead_id,
        "feishu_record_id": lead.feishu_record_id,
        "feishu_mode": feishu_mode,
    }


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
    result = await tbcexp_svc.push_lead(lead)
    if result.get("status") == "ok":
        lead.tbcexp_synced = True
        await db.commit()
    return {
        "status": result.get("status", "error"),
        "mode": result.get("mode", "mock"),
        "external_id": result.get("external_id", ""),
        "detail": result.get("detail", ""),
        "sourceType": "smart_crm",
        "lead_id": lead_id,
    }


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


@router.post("/schedules/run-due")
async def run_due_schedules(
    limit: int = 3,
    count_per_task: int = 5,
    db: AsyncSession = Depends(get_db),
):
    """触发到期定时任务（后台执行，不阻塞请求）。"""
    due = await geo_scheduler.get_due_schedules(db)
    if not due:
        return {"queued": 0, "jobs": [], "message": "无到期任务"}

    jobs: list[dict[str, Any]] = []
    now = datetime.utcnow()
    for schedule in due[: max(1, limit)]:
        batch_id, stream = await pipeline.run_batch(
            db,
            keyword=schedule.keyword,
            industry=schedule.industry,
            count=count_per_task,
            country_iso=schedule.country_iso,
            city=schedule.city,
            category_l3=schedule.category_l3,
            language=schedule.language,
            track=schedule.track,
        )
        schedule.last_run_at = now
        schedule.next_run_at = now + timedelta(hours=schedule.interval_hours)
        await db.commit()

        async def _pump(batch_stream, sched_id: str, bid: str) -> None:
            success = 0
            failed = 0
            try:
                async for event in batch_stream:
                    if event.get("event") == "complete":
                        success = event.get("success", 0)
                        failed = event.get("failed", 0)
            except Exception:
                pass

        asyncio.create_task(_pump(stream, schedule.id, batch_id))
        jobs.append(
            {
                "schedule_id": schedule.id,
                "batch_id": batch_id,
                "keyword": schedule.keyword[:80],
                "city": schedule.city,
                "category_l3": schedule.category_l3,
                "stream_url": f"/api/stream/{batch_id}",
            }
        )
    return {"queued": len(jobs), "jobs": jobs}


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


@router.get("/kb/status")
async def kb_status(db: AsyncSession = Depends(get_db)):
    """知识库运行状态（pgvector / 索引覆盖率）。"""
    from sqlalchemy import func

    indexed = await db.execute(
        select(func.count()).select_from(Lead).where(Lead.embedding.isnot(None))
    )
    total = await db.execute(select(func.count()).select_from(Lead))
    pg = "postgresql" in ASYNC_DB_URL
    return {
        "db_mode": "postgresql" if pg else "sqlite",
        "search_engine": "pgvector" if pg else "cosine_json",
        "indexed_leads": indexed.scalar() or 0,
        "total_leads": total.scalar() or 0,
        "openai_configured": bool(config_store.get("openai_api_key")),
        "semantic_ready": bool(config_store.get("openai_api_key")) and pg,
    }


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


@router.get("/stats/overview")
async def stats_overview(db: AsyncSession = Depends(get_db)):
    """试点看板汇总：线索、触达、海关、试点进度。"""
    snap = await _phase15_milestones(db)
    mx = await pilot_svc.status(db, "MX")
    co = await pilot_svc.status(db, "CO")
    return {
        "leads": snap["leads"],
        "outreach": snap["outreach"],
        "track_c": snap["track_c"],
        "pilot": {
            "MX": mx.get("latest_run", {}).get("acceptance") if mx.get("latest_run") else None,
            "CO": co.get("latest_run", {}).get("acceptance") if co.get("latest_run") else None,
        },
        "milestones": snap["milestones"],
    }


async def _phase15_milestones(db: AsyncSession) -> dict[str, Any]:
    leads = await db.execute(select(Lead))
    lead_list = leads.scalars().all()
    feishu_synced = sum(1 for l in lead_list if l.feishu_record_id)
    outreach = await db.execute(select(OutreachLog))
    logs = outreach.scalars().all()
    wa_sent = sum(1 for o in logs if o.channel == "whatsapp")
    wa_replied = sum(1 for o in logs if o.channel == "whatsapp" and o.replied)
    imports = await db.execute(select(ImportLead))
    import_list = imports.scalars().all()
    matched = sum(1 for i in import_list if i.domain)
    import_count = len(import_list)
    match_rate = round(matched / import_count, 2) if import_count else 0
    kb_sample = await kb_svc.search(db, "bakeware distributor Colombia", limit=3)
    return {
        "leads": {
            "total": len(lead_list),
            "feishu_synced": feishu_synced,
            "by_country": _count_by(lead_list, "country_iso"),
        },
        "outreach": {
            "total": len(logs),
            "whatsapp_sent": wa_sent,
            "whatsapp_replied": wa_replied,
            "reply_rate": round(wa_replied / wa_sent, 2) if wa_sent else 0,
            "target_1_5_5": "≥5 家 WhatsApp 手动发送",
        },
        "track_c": {
            "imported": import_count,
            "domain_matched": matched,
            "match_rate": match_rate,
            "target_1_5_6": "CSV 50 条域名匹配率 >60%",
        },
        "milestones": {
            "1_5_4_feishu_30": feishu_synced >= 30,
            "1_5_5_whatsapp_5": wa_sent >= 5,
            "1_5_6_track_c": import_count >= 50 and match_rate > 0.6,
            "1_5_7_kb_recall": len(kb_sample) > 0,
            "feishu_synced": feishu_synced,
            "whatsapp_sent": wa_sent,
            "track_c_imported": import_count,
            "track_c_match_rate": match_rate,
            "kb_results": len(kb_sample),
        },
    }


def _count_by(items, attr: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        key = getattr(item, attr, "") or "unknown"
        counts[key] = counts.get(key, 0) + 1
    return counts


@router.post("/outreach/log")
async def log_outreach(req: OutreachLogRequest, db: AsyncSession = Depends(get_db)):
    lead = await db.get(Lead, req.lead_id) if req.lead_id else None
    record = OutreachLog(
        lead_id=req.lead_id or None,
        company_name=req.company_name or (lead.company_name if lead else ""),
        channel=req.channel,
        country_iso=req.country_iso or (lead.country_iso if lead else ""),
        message_preview=(req.message_preview or (lead.whatsapp_intro[:500] if lead else "")),
        replied=req.replied,
        reply_notes=req.reply_notes,
        created_by=req.created_by,
    )
    if lead and req.channel == "whatsapp":
        lead.status = "已联系"
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return {"id": record.id, "status": "logged", "company_name": record.company_name}


@router.get("/outreach/logs")
async def list_outreach_logs(
    channel: str = "",
    country_iso: str = "",
    db: AsyncSession = Depends(get_db),
):
    q = select(OutreachLog).order_by(OutreachLog.sent_at.desc())
    if channel:
        q = q.where(OutreachLog.channel == channel)
    if country_iso:
        q = q.where(OutreachLog.country_iso == country_iso.upper())
    result = await db.execute(q.limit(100))
    return [
        {
            "id": o.id,
            "lead_id": o.lead_id,
            "company_name": o.company_name,
            "channel": o.channel,
            "country_iso": o.country_iso,
            "sent_at": o.sent_at.isoformat() if o.sent_at else None,
            "replied": o.replied,
            "reply_notes": o.reply_notes,
        }
        for o in result.scalars().all()
    ]


@router.patch("/outreach/logs/{log_id}")
async def update_outreach_reply(
    log_id: str, req: OutreachReplyRequest, db: AsyncSession = Depends(get_db)
):
    record = await db.get(OutreachLog, log_id)
    if not record:
        raise HTTPException(404, "Outreach log not found")
    record.replied = req.replied
    record.reply_notes = req.reply_notes
    await db.commit()
    return {"id": log_id, "replied": record.replied}


@router.get("/outreach/stats")
async def outreach_stats(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(OutreachLog))
    logs = result.scalars().all()
    wa = [o for o in logs if o.channel == "whatsapp"]
    return {
        "total": len(logs),
        "whatsapp_sent": len(wa),
        "whatsapp_replied": sum(1 for o in wa if o.replied),
        "reply_rate": round(sum(1 for o in wa if o.replied) / len(wa), 2) if wa else 0,
        "milestone_1_5_5_met": len(wa) >= 5,
    }


# --- Phase 1.5 Latam Pilot (MX / CO) ---

async def _pilot_start(req: PilotRequest, db: AsyncSession) -> dict[str, Any]:
    cfg = LatamPilotService()._country_defaults(req.country_iso)
    cities = req.cities or cfg["cities"]
    city = req.city or cfg["primary_city"]
    return await pilot_svc.run(
        db,
        country_iso=req.country_iso,
        city=city,
        category_l3=req.category_l3,
        cities=cities,
        l3_codes=req.l3_codes,
        anchor_limit=req.anchor_limit,
        leads_per_task=req.leads_per_task,
        enqueue_track_a=req.enqueue_track_a,
    )


@router.get("/pilot/{country_iso}/status")
async def pilot_status(country_iso: str, db: AsyncSession = Depends(get_db)):
    return await pilot_svc.status(db, country_iso)


@router.post("/pilot/{country_iso}/start")
async def pilot_start(
    country_iso: str, req: PilotRequest, db: AsyncSession = Depends(get_db)
):
    req.country_iso = country_iso.upper()
    return await _pilot_start(req, db)


@router.get("/pilot/{country_iso}/runs")
async def pilot_runs(country_iso: str):
    return pilot_svc.list_runs(country_iso)


@router.get("/pilot/mx/status")
async def mx_pilot_status(db: AsyncSession = Depends(get_db)):
    return await pilot_svc.status(db, "MX")


@router.post("/pilot/mx/start")
async def mx_pilot_start(req: PilotRequest, db: AsyncSession = Depends(get_db)):
    req.country_iso = "MX"
    return await _pilot_start(req, db)


@router.get("/pilot/mx/runs")
async def mx_pilot_runs():
    return pilot_svc.list_runs("MX")


@router.get("/pilot/co/status")
async def co_pilot_status(db: AsyncSession = Depends(get_db)):
    return await pilot_svc.status(db, "CO")


@router.post("/pilot/co/start")
async def co_pilot_start(req: PilotRequest, db: AsyncSession = Depends(get_db)):
    req.country_iso = "CO"
    return await _pilot_start(req, db)


@router.get("/pilot/co/runs")
async def co_pilot_runs():
    return pilot_svc.list_runs("CO")


@router.get("/pilot/report")
async def pilot_report(db: AsyncSession = Depends(get_db)):
    """Phase 1.5 试点进度汇总（MX + CO）。"""
    return await _pilot_report_data(db)


def _pilot_report_markdown(report: dict[str, Any]) -> str:
    m = report.get("milestones", {})
    c = report.get("acceptance_counts", {})
    labels = {
        "1_5_4_feishu_30": "1.5.4 飞书累计≥30",
        "1_5_5_whatsapp_5": "1.5.5 WhatsApp≥5",
        "1_5_6_track_c": "1.5.6 Track C 50条匹配>60%",
        "1_5_7_kb_recall": "1.5.7 KB语义召回",
        "mx_track_b": "MX Track B 情报",
        "mx_brainstorm": "MX Brainstorm",
        "mx_queued": "MX Track A 入队",
        "co_started": "CO 试点已启动",
    }
    lines = [
        "# SMART CRM Phase 1.5 验收报告",
        "",
        f"- 生成时间: {report.get('generated_at', '')}",
        f"- 阶段: {report.get('phase', '1.5')}",
        "",
        "## 里程碑",
        "",
    ]
    for key, label in labels.items():
        mark = "✓" if m.get(key) else "○"
        lines.append(f"- {mark} {label}")
    lines.extend(
        [
            "",
            "## 计数",
            "",
            f"- 飞书同步: {c.get('feishu_synced', 0)}",
            f"- WhatsApp 记录: {c.get('whatsapp_sent', 0)}",
            f"- Track C 导入: {c.get('track_c_imported', 0)}",
            f"- Track C 匹配率: {int((c.get('track_c_match_rate') or 0) * 100)}%",
            f"- KB 召回: {c.get('kb_results', 0)} 条",
            "",
            "## MX / CO",
            "",
        ]
    )
    for iso in ("MX", "CO"):
        block = report.get("countries", {}).get(iso, {})
        totals = block.get("totals", {})
        lines.append(
            f"### {iso}: 情报 {totals.get('intel_reports', 0)} · "
            f"策略 {totals.get('brainstorm_sessions', 0)} · "
            f"任务 {totals.get('active_schedules', 0)}"
        )
    lines.append("")
    lines.append("---")
    lines.append("*由 GET /api/pilot/export 自动生成*")
    return "\n".join(lines)


@router.get("/pilot/export")
async def pilot_export(format: str = "json", db: AsyncSession = Depends(get_db)):
    """导出 Phase 1.5 验收报告（JSON 或 Markdown）。"""
    data = await _pilot_report_data(db)
    if format.lower() in ("md", "markdown"):
        return PlainTextResponse(
            _pilot_report_markdown(data),
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=pilot_report.md"},
        )
    return data


async def _pilot_report_data(db: AsyncSession) -> dict[str, Any]:
    mx = await pilot_svc.status(db, "MX")
    co = await pilot_svc.status(db, "CO")
    runs = pilot_svc.list_runs()
    snap = await _phase15_milestones(db)
    m = snap["milestones"]
    return {
        "phase": "1.5",
        "generated_at": datetime.utcnow().isoformat(),
        "countries": {
            "MX": {
                "totals": mx["totals"],
                "latest_run": mx.get("latest_run"),
                "acceptance": (mx.get("latest_run") or {}).get("acceptance"),
            },
            "CO": {
                "totals": co["totals"],
                "latest_run": co.get("latest_run"),
                "acceptance": (co.get("latest_run") or {}).get("acceptance"),
            },
        },
        "recent_runs": runs[:10],
        "milestones": {
            "mx_track_b": bool((mx.get("latest_run") or {}).get("acceptance", {}).get("track_b_intel")),
            "mx_brainstorm": bool((mx.get("latest_run") or {}).get("acceptance", {}).get("brainstorm_cards")),
            "mx_queued": bool((mx.get("latest_run") or {}).get("acceptance", {}).get("track_a_queued")),
            "co_started": co.get("latest_run") is not None,
            "1_5_4_feishu_30": m.get("1_5_4_feishu_30", False),
            "1_5_5_whatsapp_5": m.get("1_5_5_whatsapp_5", False),
            "1_5_6_track_c": m.get("1_5_6_track_c", False),
            "1_5_7_kb_recall": m.get("1_5_7_kb_recall", False),
        },
        "acceptance_counts": {
            "feishu_synced": m.get("feishu_synced", 0),
            "whatsapp_sent": m.get("whatsapp_sent", 0),
            "track_c_imported": m.get("track_c_imported", 0),
            "track_c_match_rate": m.get("track_c_match_rate", 0),
            "kb_results": m.get("kb_results", 0),
        },
    }


# --- Tab8 Content Studio (AI 内容工坊) ---

@router.get("/content/types")
async def content_types():
    return [{"id": k, "label": v} for k, v in CONTENT_TYPES.items()]


@router.post("/content/generate")
async def content_generate(req: ContentGenerateRequest, db: AsyncSession = Depends(get_db)):
    draft = await content_svc.generate(
        db,
        content_type=req.content_type,
        product_name=req.product_name,
        category_l3=req.category_l3,
        language=req.language,
        country_iso=req.country_iso,
        input_notes=req.input_notes,
        tone=req.tone,
        target_audience=req.target_audience,
    )
    return content_svc.to_dict(draft)


@router.post("/content/generate-batch")
async def content_generate_batch(
    req: ContentBatchGenerateRequest, db: AsyncSession = Depends(get_db)
):
    batch_id, drafts = await content_svc.generate_batch(
        db,
        content_type=req.content_type,
        product_name=req.product_name,
        languages=req.languages,
        category_l3=req.category_l3,
        country_iso=req.country_iso,
        input_notes=req.input_notes,
        tone=req.tone,
        target_audience=req.target_audience,
    )
    return {
        "batch_id": batch_id,
        "product_name": req.product_name,
        "content_type": req.content_type,
        "languages": [d.language for d in drafts],
        "drafts": [content_svc.to_dict(d) for d in drafts],
    }


@router.get("/content/batches/{batch_id}")
async def get_content_batch(batch_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ContentDraft)
        .where(ContentDraft.batch_id == batch_id)
        .order_by(ContentDraft.language)
    )
    drafts = result.scalars().all()
    if not drafts:
        raise HTTPException(404, "Batch not found")
    return {
        "batch_id": batch_id,
        "product_name": drafts[0].product_name,
        "content_type": drafts[0].content_type,
        "drafts": [content_svc.to_dict(d) for d in drafts],
    }


def _draft_to_markdown(draft: ContentDraft) -> str:
    return f"""---
title: {draft.title}
slug: {draft.slug}
meta_title: {draft.meta_title}
meta_description: {draft.meta_description}
keywords: {', '.join(draft.meta_keywords or [])}
language: {draft.language}
---

# {draft.h1 or draft.title}

{draft.body_markdown}
"""


@router.get("/content/batches/{batch_id}/export.zip")
async def export_content_batch_zip(batch_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ContentDraft)
        .where(ContentDraft.batch_id == batch_id)
        .order_by(ContentDraft.language)
    )
    drafts = result.scalars().all()
    if not drafts:
        raise HTTPException(404, "Batch not found")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for draft in drafts:
            filename = f"{draft.language}-{draft.slug or draft.id}.md"
            zf.writestr(filename, _draft_to_markdown(draft))
    buf.seek(0)
    product_slug = (drafts[0].slug or drafts[0].product_name or batch_id)[:40]
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{product_slug}-multilang.zip"'
        },
    )


@router.get("/content/drafts")
async def list_content_drafts(
    content_type: str = "",
    language: str = "",
    batch_id: str = "",
    db: AsyncSession = Depends(get_db),
):
    q = select(ContentDraft).order_by(ContentDraft.created_at.desc())
    if content_type:
        q = q.where(ContentDraft.content_type == content_type)
    if language:
        q = q.where(ContentDraft.language == language)
    if batch_id:
        q = q.where(ContentDraft.batch_id == batch_id)
    result = await db.execute(q.limit(50))
    return [content_svc.to_dict(d) for d in result.scalars().all()]


@router.get("/content/drafts/{draft_id}")
async def get_content_draft(draft_id: str, db: AsyncSession = Depends(get_db)):
    draft = await db.get(ContentDraft, draft_id)
    if not draft:
        raise HTTPException(404, "Draft not found")
    return content_svc.to_dict(draft)


@router.put("/content/drafts/{draft_id}")
async def update_content_draft(
    draft_id: str, req: ContentUpdateRequest, db: AsyncSession = Depends(get_db)
):
    draft = await db.get(ContentDraft, draft_id)
    if not draft:
        raise HTTPException(404, "Draft not found")
    for field in (
        "title", "slug", "meta_title", "meta_description", "h1",
        "body_markdown", "body_html", "status",
    ):
        val = getattr(req, field, None)
        if val:
            setattr(draft, field, val)
    if req.meta_keywords:
        draft.meta_keywords = req.meta_keywords
    if req.bullet_features:
        draft.bullet_features = req.bullet_features
    draft.updated_at = datetime.utcnow()
    await db.commit()
    return content_svc.to_dict(draft)


@router.post("/content/drafts/{draft_id}/regenerate")
async def regenerate_content(draft_id: str, db: AsyncSession = Depends(get_db)):
    draft = await db.get(ContentDraft, draft_id)
    if not draft:
        raise HTTPException(404, "Draft not found")
    new_draft = await content_svc.generate(
        db,
        content_type=draft.content_type,
        product_name=draft.product_name,
        category_l3=draft.category_l3,
        language=draft.language,
        country_iso=draft.country_iso,
        input_notes=draft.input_notes,
    )
    return content_svc.to_dict(new_draft)


@router.get("/content/drafts/{draft_id}/export.md")
async def export_content_md(draft_id: str, db: AsyncSession = Depends(get_db)):
    draft = await db.get(ContentDraft, draft_id)
    if not draft:
        raise HTTPException(404, "Draft not found")
    md = _draft_to_markdown(draft)
    return StreamingResponse(
        iter([md]),
        media_type="text/markdown",
        headers={"Content-Disposition": f"attachment; filename={draft.slug or draft.id}.md"},
    )


# --- Phase 2 Portal & Share ---

@router.get("/portal/overview")
async def portal_overview(request: Request, db: AsyncSession = Depends(get_db)):
    session = await session_from_request(request, db)
    if not session or session.portal != "portal":
        raise HTTPException(401, "Customer portal session required")
    orders = await db.execute(
        select(SalesOrder)
        .where(SalesOrder.customer_email == session.email)
        .order_by(SalesOrder.created_at.desc())
    )
    rows = orders.scalars().all()
    return {
        "email": session.email,
        "orders_count": len(rows),
        "orders": [
            {
                "id": o.id,
                "order_no": o.order_no,
                "customer_name": o.customer_name,
                "status": o.status,
                "total_amount": o.total_amount,
                "currency": o.currency,
            }
            for o in rows[:20]
        ],
    }


@router.get("/portal/orders/{order_id}")
async def portal_order_detail(
    order_id: str, request: Request, db: AsyncSession = Depends(get_db)
):
    session = await session_from_request(request, db)
    if not session or session.portal != "portal":
        raise HTTPException(401, "Customer portal session required")
    order = await db.get(SalesOrder, order_id)
    if not order or order.customer_email != session.email:
        raise HTTPException(404, "Order not found")
    lines = await db.execute(
        select(SalesOrderLine).where(SalesOrderLine.order_id == order_id)
    )
    return order_dict(order, list(lines.scalars().all()))


@router.get("/portal/catalogs")
async def portal_catalogs(
    request: Request,
    db: AsyncSession = Depends(get_db),
    doc_type: str = "",
):
    session = await session_from_request(request, db)
    if not session or session.portal != "portal":
        raise HTTPException(401, "Customer portal session required")
    q = select(CatalogDocument).where(CatalogDocument.active.is_(True))
    if doc_type:
        q = q.where(CatalogDocument.doc_type == doc_type)
    result = await db.execute(q)
    out = []
    for doc in result.scalars().all():
        if customer_can_view(doc, session.email):
            factory = await db.get(Factory, doc.factory_id)
            out.append(catalog_dict(doc, factory, r2_svc))
    return out


@router.get("/portal/quotes")
async def portal_quotes(request: Request, db: AsyncSession = Depends(get_db)):
    """客户门户授权报价单（doc_type=quote 或 price_list）。"""
    session = await session_from_request(request, db)
    if not session or session.portal != "portal":
        raise HTTPException(401, "Customer portal session required")
    result = await db.execute(
        select(CatalogDocument).where(
            CatalogDocument.active.is_(True),
            CatalogDocument.doc_type.in_(("quote", "price_list")),
        )
    )
    out = []
    for doc in result.scalars().all():
        if customer_can_view(doc, session.email):
            factory = await db.get(Factory, doc.factory_id)
            out.append(catalog_dict(doc, factory, r2_svc))
    return out


@router.get("/portal/orders")
async def portal_orders(request: Request, db: AsyncSession = Depends(get_db)):
    session = await session_from_request(request, db)
    if not session or session.portal != "portal":
        raise HTTPException(401, "Customer portal session required")
    result = await db.execute(
        select(SalesOrder)
        .where(SalesOrder.customer_email == session.email)
        .order_by(SalesOrder.created_at.desc())
    )
    out = []
    for order in result.scalars().all():
        lines = await db.execute(
            select(SalesOrderLine).where(SalesOrderLine.order_id == order.id)
        )
        out.append(order_dict(order, list(lines.scalars().all())))
    return out


@router.post("/share/links")
async def create_share(
    req: ShareLinkRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    session = await session_from_request(request, db)
    created_by = session.email if session else ""
    link = await create_share_link(
        db,
        resource_type=req.resource_type,
        resource_id=req.resource_id,
        customer_email=req.customer_email,
        created_by=created_by,
        ttl_days=req.ttl_days,
    )
    base = settings.app_base_url.rstrip("/")
    share_url = f"{base}/s/{link.token}"
    notify_result = None
    to_email = (req.customer_email or "").strip()
    if req.notify_email and to_email:
        notify_result = await notify_share_link(
            to_email,
            share_url,
            req.resource_type,
            req.notify_message,
            config_store,
        )
    return {
        "token": link.token,
        "url": share_url,
        "expires_at": link.expires_at.isoformat() if link.expires_at else None,
        "resource_type": link.resource_type,
        "resource_id": link.resource_id,
        "notify": notify_result,
    }


@router.get("/share/{token}")
async def get_share(token: str, db: AsyncSession = Depends(get_db)):
    """公开分享内容（无需登录）。"""
    return await resolve_share(db, token)


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
