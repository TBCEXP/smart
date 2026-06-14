from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import ContentDraft
from app.services.clients import LLMClient
from app.services.data_loader import get_l3_categories, load_prompts


CONTENT_TYPES = {
    "seo_pack": "SEO 套装（Meta + Keywords + Slug）",
    "product_description": "B2B 产品描述",
    "category_page": "品类落地页",
    "blog_article": "SEO 博客文章",
}

LANGUAGE_LABELS = {
    "es": "西班牙语",
    "en": "英语",
    "pt": "葡萄牙语",
    "fr": "法语",
}


def slugify(text: str, language: str = "es") -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"[\s_]+", "-", text)
    return text[:80].strip("-")


class ContentStudioService:
    def __init__(self) -> None:
        self.llm = LLMClient()

    async def generate(
        self,
        db: AsyncSession,
        content_type: str,
        product_name: str,
        category_l3: str = "",
        language: str = "es",
        country_iso: str = "",
        input_notes: str = "",
        tone: str = "professional_b2b",
        target_audience: str = "hospitality_wholesaler",
        created_by: str = "",
        batch_id: str | None = None,
    ) -> ContentDraft:
        prompts = load_prompts()
        studio = prompts.get("content_studio", {})
        system = studio.get("system", "Generate SEO B2B content as JSON.")
        type_prompt = studio.get("types", {}).get(content_type, {})

        l3_name = category_l3
        for c in get_l3_categories():
            if c["code"] == category_l3:
                l3_name = c.get("name_zh", category_l3)
                break

        user = json.dumps(
            {
                "content_type": content_type,
                "product_name": product_name,
                "category_l3": l3_name,
                "language": language,
                "country_iso": country_iso,
                "input_notes": input_notes,
                "tone": tone,
                "target_audience": target_audience,
                "instructions": type_prompt.get("instructions", ""),
                "output_fields": type_prompt.get("output_fields", []),
            },
            ensure_ascii=False,
        )

        raw = await self.llm.complete(system, user, json_mode=True, temperature=0.5)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {
                "title": product_name,
                "slug": slugify(product_name),
                "meta_title": product_name[:60],
                "meta_description": input_notes[:150] or product_name,
                "meta_keywords": [product_name, category_l3],
                "h1": product_name,
                "body_markdown": raw,
                "bullet_features": [],
            }

        slug = data.get("slug") or slugify(data.get("title", product_name), language)
        keywords = data.get("meta_keywords", [])
        if isinstance(keywords, str):
            keywords = [k.strip() for k in keywords.split(",")]

        draft = ContentDraft(
            batch_id=batch_id,
            content_type=content_type,
            language=language,
            country_iso=country_iso.upper(),
            category_l3=category_l3,
            product_name=product_name,
            input_notes=input_notes,
            title=data.get("title", product_name),
            slug=slug,
            meta_title=(data.get("meta_title", "") or "")[:70],
            meta_description=(data.get("meta_description", "") or "")[:320],
            meta_keywords=keywords,
            h1=data.get("h1", product_name),
            body_markdown=data.get("body_markdown", data.get("product_description_long", "")),
            body_html=data.get("body_html", ""),
            bullet_features=data.get("bullet_features", []),
            extra_json={
                "product_description_short": data.get("product_description_short", ""),
                "seo_notes": data.get("seo_notes", ""),
                "cta": data.get("cta", ""),
            },
            status="draft",
            created_by=created_by,
            updated_at=datetime.utcnow(),
        )
        db.add(draft)
        await db.commit()
        await db.refresh(draft)
        return draft

    async def generate_batch(
        self,
        db: AsyncSession,
        content_type: str,
        product_name: str,
        languages: list[str],
        category_l3: str = "",
        country_iso: str = "",
        input_notes: str = "",
        tone: str = "professional_b2b",
        target_audience: str = "hospitality_wholesaler",
        created_by: str = "",
    ) -> tuple[str, list[ContentDraft]]:
        batch_id = str(uuid.uuid4())
        langs = [lang.strip().lower() for lang in languages if lang.strip()]
        if not langs:
            langs = ["es", "en", "pt"]

        drafts: list[ContentDraft] = []
        for language in langs:
            draft = await self.generate(
                db,
                content_type=content_type,
                product_name=product_name,
                category_l3=category_l3,
                language=language,
                country_iso=country_iso,
                input_notes=input_notes,
                tone=tone,
                target_audience=target_audience,
                created_by=created_by,
                batch_id=batch_id,
            )
            drafts.append(draft)
        return batch_id, drafts

    def to_dict(self, draft: ContentDraft) -> dict[str, Any]:
        return {
            "id": draft.id,
            "batch_id": draft.batch_id,
            "content_type": draft.content_type,
            "content_type_label": CONTENT_TYPES.get(draft.content_type, draft.content_type),
            "language": draft.language,
            "language_label": LANGUAGE_LABELS.get(draft.language, draft.language),
            "country_iso": draft.country_iso,
            "category_l3": draft.category_l3,
            "product_name": draft.product_name,
            "title": draft.title,
            "slug": draft.slug,
            "meta_title": draft.meta_title,
            "meta_description": draft.meta_description,
            "meta_keywords": draft.meta_keywords,
            "h1": draft.h1,
            "body_markdown": draft.body_markdown,
            "body_html": draft.body_html,
            "bullet_features": draft.bullet_features,
            "extra": draft.extra_json,
            "status": draft.status,
            "created_at": draft.created_at.isoformat() if draft.created_at else None,
        }
