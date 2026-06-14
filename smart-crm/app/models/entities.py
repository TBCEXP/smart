from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class Lead(Base):
    __tablename__ = "leads"
    __table_args__ = (UniqueConstraint("domain", name="uq_lead_domain"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    batch_id: Mapped[Optional[str]] = mapped_column(String(36), index=True)
    company_name: Mapped[str] = mapped_column(String(512), default="")
    website_url: Mapped[str] = mapped_column(String(1024), default="")
    domain: Mapped[str] = mapped_column(String(255), default="", index=True)
    industry: Mapped[str] = mapped_column(String(64), default="")
    keyword: Mapped[str] = mapped_column(String(512), default="")
    exa_summary: Mapped[str] = mapped_column(Text, default="")
    firecrawl_summary: Mapped[str] = mapped_column(Text, default="")
    outreach_email: Mapped[str] = mapped_column(Text, default="")
    whatsapp_intro: Mapped[str] = mapped_column(Text, default="")
    subject_lines: Mapped[str] = mapped_column(Text, default="")
    lead_score: Mapped[str] = mapped_column(String(8), default="B")
    status: Mapped[str] = mapped_column(String(32), default="待联系")
    preferred_channel: Mapped[str] = mapped_column(String(32), default="email")
    notes: Mapped[str] = mapped_column(Text, default="")
    language: Mapped[str] = mapped_column(String(8), default="es")
    country_iso: Mapped[str] = mapped_column(String(8), default="")
    city: Mapped[str] = mapped_column(String(128), default="")
    category_l1: Mapped[str] = mapped_column(String(64), default="kitchen")
    category_l2: Mapped[str] = mapped_column(String(64), default="hotel-restaurant")
    category_l3: Mapped[str] = mapped_column(String(64), default="")
    buyer_type: Mapped[str] = mapped_column(String(64), default="")
    reference_brand_fit: Mapped[str] = mapped_column(String(64), default="")
    track: Mapped[str] = mapped_column(String(16), default="track_a")
    source: Mapped[str] = mapped_column(String(64), default="exa")
    hs_code: Mapped[str] = mapped_column(String(16), default="")
    feishu_record_id: Mapped[str] = mapped_column(String(64), default="")
    tbcexp_synced: Mapped[bool] = mapped_column(Boolean, default=False)
    informed_by_intel_id: Mapped[Optional[str]] = mapped_column(String(36))
    embedding: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Batch(Base):
    __tablename__ = "batches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    keyword: Mapped[str] = mapped_column(String(512), default="")
    industry: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[str] = mapped_column(String(32), default="running")
    total: Mapped[int] = mapped_column(Integer, default=0)
    success: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    country_iso: Mapped[str] = mapped_column(String(8), default="")
    city: Mapped[str] = mapped_column(String(128), default="")
    category_l3: Mapped[str] = mapped_column(String(64), default="")
    track: Mapped[str] = mapped_column(String(16), default="track_a")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)


class Schedule(Base):
    __tablename__ = "schedules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    keyword: Mapped[str] = mapped_column(String(512), default="")
    industry: Mapped[str] = mapped_column(String(64), default="跨境电商")
    interval_hours: Mapped[int] = mapped_column(Integer, default=24)
    country_iso: Mapped[str] = mapped_column(String(8), default="")
    city: Mapped[str] = mapped_column(String(128), default="")
    category_l3: Mapped[str] = mapped_column(String(64), default="")
    language: Mapped[str] = mapped_column(String(8), default="es")
    track: Mapped[str] = mapped_column(String(16), default="track_a")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    next_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime)


class CountryAnchor(Base):
    __tablename__ = "country_anchors"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    country_iso: Mapped[str] = mapped_column(String(8), index=True)
    company_name: Mapped[str] = mapped_column(String(256), default="")
    website: Mapped[str] = mapped_column(String(1024), default="")
    anchor_type: Mapped[str] = mapped_column(String(32), default="brand")
    crawl_paths: Mapped[dict] = mapped_column(JSON, default=list)
    last_crawled_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class MarketProductIntel(Base):
    __tablename__ = "market_product_intel"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    country_iso: Mapped[str] = mapped_column(String(8), index=True)
    anchor_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("country_anchors.id"))
    category_l3: Mapped[str] = mapped_column(String(64), default="")
    product_examples: Mapped[dict] = mapped_column(JSON, default=list)
    trend_summary: Mapped[str] = mapped_column(Text, default="")
    sales_signal: Mapped[str] = mapped_column(String(16), default="medium")
    source_urls: Mapped[dict] = mapped_column(JSON, default=list)
    l3_heat: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class StrategySession(Base):
    __tablename__ = "strategy_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    country_iso: Mapped[str] = mapped_column(String(8), index=True)
    city: Mapped[str] = mapped_column(String(128), default="")
    category_l3: Mapped[str] = mapped_column(String(64), default="")
    language: Mapped[str] = mapped_column(String(8), default="es")
    icp_json: Mapped[dict] = mapped_column(JSON, default=dict)
    keywords: Mapped[dict] = mapped_column(JSON, default=list)
    channel_plan: Mapped[dict] = mapped_column(JSON, default=list)
    seeds: Mapped[dict] = mapped_column(JSON, default=list)
    action_plan: Mapped[dict] = mapped_column(JSON, default=dict)
    market_intel_refs: Mapped[dict] = mapped_column(JSON, default=list)
    created_by: Mapped[str] = mapped_column(String(256), default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    actions: Mapped[list["StrategyAction"]] = relationship(back_populates="session")


class StrategyAction(Base):
    __tablename__ = "strategy_actions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("strategy_sessions.id"))
    action_type: Mapped[str] = mapped_column(String(32))
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    session: Mapped["StrategySession"] = relationship(back_populates="actions")


class TradeShow(Base):
    __tablename__ = "trade_shows"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(256), default="")
    country_iso: Mapped[str] = mapped_column(String(8), default="")
    region: Mapped[str] = mapped_column(String(64), default="americas")
    show_type: Mapped[str] = mapped_column(String(64), default="hospitality")
    exhibitor_list_url: Mapped[str] = mapped_column(String(1024), default="")
    event_date: Mapped[Optional[str]] = mapped_column(String(32))
    last_crawled_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    exhibitor_count: Mapped[int] = mapped_column(Integer, default=0)


class ImportLead(Base):
    __tablename__ = "import_leads"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    company_name: Mapped[str] = mapped_column(String(512), default="")
    country_iso: Mapped[str] = mapped_column(String(8), default="")
    hs_code: Mapped[str] = mapped_column(String(16), default="")
    import_volume: Mapped[Optional[float]] = mapped_column(Float)
    website: Mapped[str] = mapped_column(String(1024), default="")
    domain: Mapped[str] = mapped_column(String(255), default="", index=True)
    contact_email: Mapped[str] = mapped_column(String(256), default="")
    source: Mapped[str] = mapped_column(String(64), default="csv")
    matched_lead_id: Mapped[Optional[str]] = mapped_column(String(36))
    status: Mapped[str] = mapped_column(String(32), default="pending")
    raw_data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AuthWhitelist(Base):
    __tablename__ = "auth_whitelist"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(256), unique=True, index=True)
    portal: Mapped[str] = mapped_column(String(16), default="admin")
    role: Mapped[str] = mapped_column(String(32), default="sales")
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class AuthToken(Base):
    __tablename__ = "auth_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(256), index=True)
    portal: Mapped[str] = mapped_column(String(16), default="admin")
    token_type: Mapped[str] = mapped_column(String(16))
    token_value: Mapped[str] = mapped_column(String(256))
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used: Mapped[bool] = mapped_column(Boolean, default=False)


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(256), index=True)
    portal: Mapped[str] = mapped_column(String(16), default="admin")
    role: Mapped[str] = mapped_column(String(32), default="sales")
    session_token: Mapped[str] = mapped_column(String(256), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ContentDraft(Base):
    """AI 内容工坊产出：SEO、产品描述、文章等。"""

    __tablename__ = "content_drafts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    batch_id: Mapped[Optional[str]] = mapped_column(String(36), index=True)
    content_type: Mapped[str] = mapped_column(String(32), index=True)
    language: Mapped[str] = mapped_column(String(8), default="es")
    country_iso: Mapped[str] = mapped_column(String(8), default="")
    category_l3: Mapped[str] = mapped_column(String(64), default="")
    product_name: Mapped[str] = mapped_column(String(512), default="")
    input_notes: Mapped[str] = mapped_column(Text, default="")
    title: Mapped[str] = mapped_column(String(256), default="")
    slug: Mapped[str] = mapped_column(String(256), default="", index=True)
    meta_title: Mapped[str] = mapped_column(String(70), default="")
    meta_description: Mapped[str] = mapped_column(String(320), default="")
    meta_keywords: Mapped[dict] = mapped_column(JSON, default=list)
    h1: Mapped[str] = mapped_column(String(256), default="")
    body_html: Mapped[str] = mapped_column(Text, default="")
    body_markdown: Mapped[str] = mapped_column(Text, default="")
    bullet_features: Mapped[dict] = mapped_column(JSON, default=list)
    extra_json: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(16), default="draft")
    created_by: Mapped[str] = mapped_column(String(256), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class OutreachLog(Base):
    """人工触达记录（WhatsApp / 邮件），用于 1.5.5 回复率跟踪。"""

    __tablename__ = "outreach_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    lead_id: Mapped[Optional[str]] = mapped_column(String(36), index=True)
    company_name: Mapped[str] = mapped_column(String(512), default="")
    channel: Mapped[str] = mapped_column(String(16), default="whatsapp")
    country_iso: Mapped[str] = mapped_column(String(8), default="")
    message_preview: Mapped[str] = mapped_column(String(512), default="")
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    replied: Mapped[bool] = mapped_column(Boolean, default=False)
    reply_notes: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str] = mapped_column(String(256), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
