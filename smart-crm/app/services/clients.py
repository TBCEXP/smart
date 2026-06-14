from __future__ import annotations

import asyncio
import json
import re
from typing import Any
from urllib.parse import urlparse

import httpx

from app.services.config_store import ConfigStore
from app.services.exa_utils import EXA_EXCLUDE_DOMAINS, build_semantic_exa_query


def extract_domain(url: str) -> str:
    if not url:
        return ""
    if not url.startswith("http"):
        url = f"https://{url}"
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def _is_excluded_domain(domain: str) -> bool:
    return any(domain == d or domain.endswith(f".{d}") for d in EXA_EXCLUDE_DOMAINS)


class ExaClient:
    def __init__(self, config: ConfigStore | None = None) -> None:
        self.config = config or ConfigStore()

    async def search(
        self,
        query: str,
        num_results: int = 10,
        search_type: str = "standard",
        country_iso: str = "",
        city: str = "",
    ) -> list[dict[str, Any]]:
        api_key = self.config.get("exa_api_key")
        semantic_query = build_semantic_exa_query(query, search_type, country_iso, city)
        if not api_key:
            return self._mock_results(semantic_query, num_results)
        payload: dict[str, Any] = {
            "query": semantic_query,
            "numResults": min(num_results + 3, 25),
            "type": "auto",
            "contents": {"text": {"maxCharacters": 2500}},
            "excludeDomains": EXA_EXCLUDE_DOMAINS,
        }
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=60) as client:
                    resp = await client.post(
                        "https://api.exa.ai/search",
                        headers={"x-api-key": api_key, "Content-Type": "application/json"},
                        json=payload,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    results = []
                    for item in data.get("results", []):
                        domain = extract_domain(item.get("url", ""))
                        if _is_excluded_domain(domain):
                            continue
                        results.append(
                            {
                                "title": item.get("title", ""),
                                "url": item.get("url", ""),
                                "text": item.get("text", ""),
                                "domain": domain,
                            }
                        )
                        if len(results) >= num_results:
                            break
                    return results
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 429 and attempt < 2:
                    await asyncio.sleep(2 ** (attempt + 1))
                    continue
                raise
        return []

    def _mock_results(self, query: str, num_results: int) -> list[dict[str, Any]]:
        slug = re.sub(r"[^a-z0-9]+", "-", query.lower())[:40].strip("-")
        return [
            {
                "title": f"Mock Company {i+1} - {query[:30]}",
                "url": f"https://{slug}-{i+1}.example.com",
                "text": f"Mock Exa result for query: {query}",
                "domain": f"{slug}-{i+1}.example.com",
            }
            for i in range(min(num_results, 5))
        ]


class FirecrawlClient:
    def __init__(self, config: ConfigStore | None = None) -> None:
        self.config = config or ConfigStore()

    async def scrape(self, base_url: str, paths: list[str] | None = None) -> str:
        api_key = self.config.get("firecrawl_api_key")
        paths = paths or ["/", "/about", "/products", "/catalog", "/wholesale"]
        if not api_key:
            return f"Mock Firecrawl summary for {base_url}. Paths: {', '.join(paths)}"
        if not base_url.startswith("http"):
            base_url = f"https://{base_url}"
        summaries: list[str] = []
        async with httpx.AsyncClient(timeout=90) as client:
            # Prefer map+scrape key pages; fallback to homepage only
            urls_to_try = [base_url.rstrip("/") + p for p in paths[:5]]
            if base_url not in urls_to_try:
                urls_to_try.insert(0, base_url)
            for url in urls_to_try[:6]:
                md = await self._scrape_one(client, api_key, url)
                if md and "Error scraping" not in md:
                    summaries.append(f"## {url}\n{md[:1800]}")
                if len(summaries) >= 3:
                    break
        if not summaries:
            async with httpx.AsyncClient(timeout=90) as client:
                md = await self._scrape_one(client, api_key, base_url)
            summaries.append(md or f"No content from {base_url}")
        return "\n\n".join(summaries)[:8000]

    async def _scrape_one(
        self,
        client: httpx.AsyncClient,
        api_key: str,
        url: str,
    ) -> str:
        for attempt in range(2):
            try:
                resp = await client.post(
                    "https://api.firecrawl.dev/v1/scrape",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "url": url,
                        "formats": ["markdown"],
                        "onlyMainContent": True,
                        "waitFor": 2000,
                    },
                )
                if resp.status_code == 429 and attempt == 0:
                    await asyncio.sleep(3)
                    continue
                if resp.status_code == 200:
                    return resp.json().get("data", {}).get("markdown", "")[:2000]
                return f"HTTP {resp.status_code} for {url}"
            except httpx.TimeoutException:
                if attempt == 0:
                    await asyncio.sleep(2)
                    continue
                return f"Timeout scraping {url}"
        return ""


class LLMClient:
    def __init__(self, config: ConfigStore | None = None) -> None:
        self.config = config or ConfigStore()

    async def complete(
        self,
        system: str,
        user: str,
        json_mode: bool = False,
        temperature: float = 0.4,
    ) -> str:
        api_key = self.config.get("openai_api_key")
        model = self.config.get("openai_model", "gpt-4o-mini")
        if not api_key:
            if json_mode:
                return json.dumps(
                    {
                        "icp": {
                            "buyer_types": ["distributor", "importer"],
                            "company_size": "20-500",
                            "website_signals": ["/catalog", "/wholesale"],
                            "decision_makers": ["Purchasing Manager"],
                        },
                        "keywords": {
                            "es": [
                                "distribuidor moldes repostería México mayorista"
                            ],
                            "en": [],
                        },
                        "channel_plan": [
                            {"channel": "email", "priority": 1, "rationale": "B2B standard"},
                            {"channel": "whatsapp", "priority": 2, "rationale": "LATAM preference"},
                        ],
                        "seeds": {
                            "companies": [],
                            "similar_search_queries": [
                                "category:company hospitality distributor Mexico"
                            ],
                            "tradeshows": ["Expo ANTAD"],
                            "hs_codes": ["732393"],
                        },
                        "action_plan": {
                            "week1": "Track B Vasconia crawl",
                            "week2": "Exa 20 leads CDMX",
                            "week3": "CSV import enrich",
                            "week4": "WhatsApp follow-up",
                        },
                    },
                    ensure_ascii=False,
                )
            return json.dumps(
                {
                    "email_body": f"Mock Spanish outreach for: {user[:120]}",
                    "subject_lines": [
                        "Oportunidad OEM utensilios hostelería",
                        "Proveedor certificado NSF - catálogo mayorista",
                    ],
                    "lead_score": "B",
                    "whatsapp_intro": "Hola, somos fabricante OEM de utensilios hostelería. ¿Le interesa catálogo?",
                },
                ensure_ascii=False,
            )
        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
