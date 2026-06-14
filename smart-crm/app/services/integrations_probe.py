from __future__ import annotations

import time
from typing import Any

import httpx

from app.services.clients import ExaClient, FirecrawlClient, LLMClient
from app.services.config_store import ConfigStore
from app.services.feishu_client import FeishuClient


class IntegrationsProbeService:
    """轻量探测外部 API 是否可用（配置后验证连通性）。"""

    def __init__(self, config: ConfigStore | None = None) -> None:
        self.config = config or ConfigStore()
        self.exa = ExaClient(self.config)
        self.firecrawl = FirecrawlClient(self.config)
        self.llm = LLMClient(self.config)
        self.feishu = FeishuClient(self.config)

    async def probe_all(self) -> dict[str, Any]:
        started = time.time()
        probes = [
            await self._probe_exa(),
            await self._probe_firecrawl(),
            await self._probe_openai(),
            await self._probe_feishu(),
        ]
        live_ok = sum(1 for p in probes if p.get("status") == "ok" and not p.get("mock"))
        live_fail = sum(1 for p in probes if p.get("status") == "error")
        mock_count = sum(1 for p in probes if p.get("mock"))
        return {
            "elapsed_ms": int((time.time() - started) * 1000),
            "production_ready": live_ok >= 4,
            "summary": {
                "live_ok": live_ok,
                "live_error": live_fail,
                "mock": mock_count,
            },
            "note": "production_ready 需 Exa+Firecrawl+OpenAI+飞书 四项 live 探测通过",
            "probes": probes,
        }

    async def _probe_exa(self) -> dict[str, Any]:
        key = self.config.get("exa_api_key")
        if not key:
            return {"id": "exa", "label": "Exa", "status": "mock", "mock": True, "detail": "未配置 Key"}
        try:
            results = await self.exa.search("hospitality distributor Mexico", 1)
            return {
                "id": "exa",
                "label": "Exa",
                "status": "ok",
                "mock": False,
                "detail": f"返回 {len(results)} 条结果",
            }
        except Exception as exc:
            return {"id": "exa", "label": "Exa", "status": "error", "mock": False, "detail": str(exc)[:200]}

    async def _probe_firecrawl(self) -> dict[str, Any]:
        key = self.config.get("firecrawl_api_key")
        if not key:
            return {"id": "firecrawl", "label": "Firecrawl", "status": "mock", "mock": True, "detail": "未配置 Key"}
        try:
            text = await self.firecrawl.scrape("https://www.vasconia.com", ["/"])
            ok = bool(text and "error" not in text.lower()[:80])
            return {
                "id": "firecrawl",
                "label": "Firecrawl",
                "status": "ok" if ok else "error",
                "mock": False,
                "detail": f"抓取 {len(text)} 字符" if ok else text[:120],
            }
        except Exception as exc:
            return {
                "id": "firecrawl",
                "label": "Firecrawl",
                "status": "error",
                "mock": False,
                "detail": str(exc)[:200],
            }

    async def _probe_openai(self) -> dict[str, Any]:
        key = self.config.get("openai_api_key")
        if not key:
            return {"id": "openai", "label": "OpenAI", "status": "mock", "mock": True, "detail": "未配置 Key"}
        try:
            out = await self.llm.complete(
                "Reply with JSON only.",
                '{"ping":"pong"}',
                json_mode=True,
                temperature=0,
            )
            return {
                "id": "openai",
                "label": "OpenAI",
                "status": "ok" if out else "error",
                "mock": False,
                "detail": f"模型 {self.config.get('openai_model', 'gpt-4o-mini')} 响应 OK",
            }
        except Exception as exc:
            return {
                "id": "openai",
                "label": "OpenAI",
                "status": "error",
                "mock": False,
                "detail": str(exc)[:200],
            }

    async def _probe_feishu(self) -> dict[str, Any]:
        if not self.feishu._configured():
            return {"id": "feishu", "label": "飞书", "status": "mock", "mock": True, "detail": "未配置 App/Table"}
        try:
            token = await self.feishu._tenant_token()
            return {
                "id": "feishu",
                "label": "飞书",
                "status": "ok" if token else "error",
                "mock": False,
                "detail": "tenant_access_token 获取成功",
            }
        except Exception as exc:
            return {
                "id": "feishu",
                "label": "飞书",
                "status": "error",
                "mock": False,
                "detail": str(exc)[:200],
            }

    async def probe_resend(self) -> dict[str, Any]:
        key = self.config.get("resend_api_key")
        if not key:
            return {"id": "resend", "label": "Resend", "status": "mock", "mock": True, "detail": "未配置"}
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    "https://api.resend.com/domains",
                    headers={"Authorization": f"Bearer {key}"},
                )
                if resp.status_code in (200, 403):
                    return {"id": "resend", "label": "Resend", "status": "ok", "mock": False, "detail": "API Key 有效"}
                return {
                    "id": "resend",
                    "label": "Resend",
                    "status": "error",
                    "mock": False,
                    "detail": f"HTTP {resp.status_code}",
                }
        except Exception as exc:
            return {"id": "resend", "label": "Resend", "status": "error", "mock": False, "detail": str(exc)[:200]}
