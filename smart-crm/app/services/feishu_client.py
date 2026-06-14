from __future__ import annotations

import time
from typing import Any

import httpx

from app.models.entities import Lead
from app.services.config_store import ConfigStore
from app.services.data_loader import load_prompts


class FeishuClient:
    """飞书多维表格写入客户端（PDF §3.2 字段规范）。"""

    def __init__(self, config: ConfigStore | None = None) -> None:
        self.config = config or ConfigStore()
        self._token: str = ""
        self._token_expires: float = 0

    def _configured(self) -> bool:
        return bool(
            self.config.get("feishu_app_id")
            and self.config.get("feishu_app_secret")
            and self.config.get("feishu_base_token")
            and self.config.get("feishu_table_id")
        )

    async def _tenant_token(self) -> str:
        if self._token and time.time() < self._token_expires - 60:
            return self._token
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                json={
                    "app_id": self.config.get("feishu_app_id"),
                    "app_secret": self.config.get("feishu_app_secret"),
                },
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") != 0:
                raise RuntimeError(f"Feishu auth failed: {data}")
            self._token = data["tenant_access_token"]
            self._token_expires = time.time() + data.get("expire", 7200)
            return self._token

    def _lead_fields(self, lead: Lead, batch_id: str = "") -> dict[str, Any]:
        extended = self.config.get("extended_feishu_fields", "true").lower() in (
            "true",
            "1",
            "yes",
        )
        fields: dict[str, Any] = {
            "公司名称": lead.company_name,
            "网站 URL": lead.website_url,
            "行业分类": lead.industry or "跨境电商",
            "搜索关键词": lead.keyword,
            "Exa 搜索结果摘要": (lead.exa_summary or "")[:8000],
            "Firecrawl 分析摘要": (lead.firecrawl_summary or "")[:8000],
            "个性化开发信": (lead.outreach_email or "")[:8000],
            "状态": lead.status or "待联系",
            "备注": f"track={lead.track} channel={lead.preferred_channel}",
            "创建时间": int(time.time() * 1000),
        }
        if extended:
            fields.update(
                {
                    "线索评分": lead.lead_score or "B",
                    "主题行": (lead.subject_lines or "")[:500],
                    "批次 ID": batch_id or lead.batch_id or "",
                    "处理状态": "成功",
                    "产品品类 L3": lead.category_l3,
                    "语言": lead.language,
                    "国家": lead.country_iso,
                    "首选渠道": lead.preferred_channel,
                }
            )
        return fields

    async def create_record(self, lead: Lead, batch_id: str = "") -> str:
        if not self._configured():
            return ""
        token = await self._tenant_token()
        table_id = self.config.get("feishu_table_id")
        base_token = self.config.get("feishu_base_token")
        payload = {"fields": self._lead_fields(lead, batch_id)}
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"https://open.feishu.cn/open-apis/bitable/v1/apps/{base_token}/tables/{table_id}/records",
                headers={"Authorization": f"Bearer {token}"},
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") != 0:
                raise RuntimeError(f"Feishu write failed: {data}")
            return data.get("data", {}).get("record", {}).get("record_id", "")

    async def update_status(self, record_id: str, status: str) -> None:
        if not record_id or not self._configured():
            return
        token = await self._tenant_token()
        table_id = self.config.get("feishu_table_id")
        base_token = self.config.get("feishu_base_token")
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.put(
                f"https://open.feishu.cn/open-apis/bitable/v1/apps/{base_token}/tables/{table_id}/records/{record_id}",
                headers={"Authorization": f"Bearer {token}"},
                json={"fields": {"状态": status}},
            )
            resp.raise_for_status()
