from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    data_dir: Path = Path(os.getenv("DATA_DIR", "data"))
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://smartcrm:smartcrm@postgres:5432/smartcrm",
    )
    sync_database_url: str = os.getenv(
        "SYNC_DATABASE_URL",
        "postgresql://smartcrm:smartcrm@postgres:5432/smartcrm",
    )
    session_secret: str = os.getenv("SESSION_SECRET", "change-me-in-production")
    session_days: int = int(os.getenv("SESSION_DAYS", "7"))
    otp_ttl_minutes: int = 10
    magic_link_ttl_minutes: int = 15
    otp_resend_seconds: int = 60
    app_base_url: str = os.getenv("APP_BASE_URL", "http://localhost:8000")

    class Config:
        env_file = ".env"


settings = Settings()
settings.data_dir.mkdir(parents=True, exist_ok=True)
(settings.data_dir / "batches").mkdir(parents=True, exist_ok=True)


class ConfigPayload(BaseModel):
    exa_api_key: str = ""
    firecrawl_api_key: str = ""
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    feishu_app_id: str = ""
    feishu_app_secret: str = ""
    feishu_base_token: str = ""
    feishu_table_id: str = ""
    ingest_mode: str = "review"
    max_concurrency: int = 5
    extended_feishu_fields: bool = True
    tbcexp_api_url: str = ""
    tbcexp_api_token: str = ""
    resend_api_key: str = ""
    resend_from_email: str = ""
    scheduler_enabled: bool = False
    apollo_api_key: str = ""
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket: str = "smart-crm"
    r2_public_base_url: str = ""
    importgenius_api_key: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""


class RunRequest(BaseModel):
    keyword: str
    industry: str = "跨境电商"
    count: int = 10
    country_iso: str = ""
    city: str = ""
    category_l3: str = ""
    language: str = "es"
    search_type: str = "standard"


class ScheduleRequest(BaseModel):
    keyword: str
    industry: str = "跨境电商"
    interval_hours: int = 24
    country_iso: str = ""
    city: str = ""
    category_l3: str = ""
    language: str = "es"
    track: str = "track_a"


class BrainstormRequest(BaseModel):
    country_iso: str
    city: str = ""
    category_l3: str
    language: str = "es"
    moq: str = ""
    certifications: str = ""
    oem_experience: str = ""


class BrainstormActionRequest(BaseModel):
    session_id: str
    action_type: str
    payload: dict[str, Any] = Field(default_factory=dict)


class MarketIntelCrawlRequest(BaseModel):
    anchor_id: str


class TradeShowCrawlRequest(BaseModel):
    tradeshow_id: str


class ImportCsvRequest(BaseModel):
    source: str = "manual"
    hs_codes: list[str] = Field(default_factory=list)
    country_iso: str = ""


class AuthEmailRequest(BaseModel):
    email: str
    portal: str = "admin"


class AuthOtpRequest(BaseModel):
    email: str
    code: str
    portal: str = "admin"


class SendEmailRequest(BaseModel):
    lead_id: str
    to_email: str = ""
    subject: str = ""
    body: str = ""


class FeishuWebhookRequest(BaseModel):
    batch_id: str
    lead_index: int
    status: str
    record_id: str = ""


class ContentGenerateRequest(BaseModel):
    content_type: str = "seo_pack"
    product_name: str
    category_l3: str = ""
    language: str = "es"
    country_iso: str = ""
    input_notes: str = ""
    tone: str = "professional_b2b"
    target_audience: str = "hospitality_wholesaler"


class ContentBatchGenerateRequest(BaseModel):
    content_type: str = "seo_pack"
    product_name: str
    category_l3: str = ""
    languages: list[str] = Field(default_factory=lambda: ["es", "en", "pt"])
    country_iso: str = ""
    input_notes: str = ""
    tone: str = "professional_b2b"
    target_audience: str = "hospitality_wholesaler"


class PilotRequest(BaseModel):
    country_iso: str = "MX"
    city: str = ""
    category_l3: str = "bakeware"
    cities: list[str] = Field(default_factory=list)
    l3_codes: list[str] = Field(default_factory=lambda: ["bakeware", "cookware-commercial", "flatware"])
    anchor_limit: int = 2
    leads_per_task: int = 5
    enqueue_track_a: bool = True


class MxPilotRequest(PilotRequest):
    country_iso: str = "MX"


class ContentUpdateRequest(BaseModel):
    title: str = ""
    slug: str = ""
    meta_title: str = ""
    meta_description: str = ""
    meta_keywords: list[str] = Field(default_factory=list)
    h1: str = ""
    body_markdown: str = ""
    body_html: str = ""
    bullet_features: list[str] = Field(default_factory=list)
    status: str = "draft"


class OutreachLogRequest(BaseModel):
    lead_id: str = ""
    company_name: str = ""
    channel: str = "whatsapp"
    country_iso: str = ""
    message_preview: str = ""
    replied: bool = False
    reply_notes: str = ""
    created_by: str = ""


class OutreachReplyRequest(BaseModel):
    replied: bool = True
    reply_notes: str = ""


class ShareLinkRequest(BaseModel):
    resource_type: str = "order"
    resource_id: str
    customer_email: str = ""
    ttl_days: int = 14
    notify_email: bool = False
    notify_message: str = ""


class CatalogUploadUrlRequest(BaseModel):
    key: str = ""
    content_type: str = "application/pdf"
    ttl_seconds: int = 900
    update_file_url: bool = True


class CatalogDocumentRequest(BaseModel):
    factory_id: str
    title: str
    title_en: str = ""
    category_l3: str = ""
    doc_type: str = "catalog"
    file_url: str = ""
    pages: int = 0
    file_size_mb: float = 0.0
    authorized_emails: list[str] = Field(default_factory=list)
    notes: str = ""


class FactoryRequest(BaseModel):
    code: str
    name_zh: str = ""
    name_en: str = ""
    country: str = "CN"
    city: str = ""
    contact_name: str = ""
    contact_email: str = ""
    category_focus: str = ""
    moq_default: str = "500 pcs"
    notes: str = ""


class OrderCreateRequest(BaseModel):
    customer_name: str
    customer_email: str = ""
    country_iso: str = ""
    currency: str = "USD"
    factory_id: str = ""
    lead_id: str = ""
    notes: str = ""
    assigned_to: str = ""


class OrderLineRequest(BaseModel):
    sku: str = ""
    product_name: str
    category_l3: str = ""
    qty: int = 1
    unit_price: float = 0.0
    factory_id: str = ""
    notes: str = ""


class OrderUpdateRequest(BaseModel):
    status: str = ""
    customer_name: str = ""
    customer_email: str = ""
    notes: str = ""
    assigned_to: str = ""


class CatalogDocumentUpdateRequest(BaseModel):
    title: str = ""
    title_en: str = ""
    category_l3: str = ""
    doc_type: str = ""
    authorized_emails: list[str] | None = None
    pages: int | None = None
    file_size_mb: float | None = None
    notes: str = ""
    active: bool | None = None


