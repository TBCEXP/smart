from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse

import httpx

from app.services.config_store import ConfigStore


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


class ExaClient:
    def __init__(self, config: ConfigStore | None = None) -> None:
        self.config = config or ConfigStore()

    async def search(self, query: str, num_results: int = 10) -> list[dict[str, Any]]:
        api_key = self.config.get("exa_api_key")
        if not api_key:
            return self._mock_results(query, num_results)
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.exa.ai/search",
                headers={"x-api-key": api_key, "Content-Type": "application/json"},
                json={
                    "query": query,
                    "numResults": num_results,
                    "type": "auto",
                    "contents": {"text": {"maxCharacters": 2000}},
                },
            )
            resp.raise_for_status()
            data = resp.json()
            results = []
            for item in data.get("results", []):
                results.append(
                    {
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "text": item.get("text", ""),
                        "domain": extract_domain(item.get("url", "")),
                    }
                )
            return results

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
        paths = paths or ["/", "/about", "/products"]
        if not api_key:
            return f"Mock Firecrawl summary for {base_url}. Paths: {', '.join(paths)}"
        summaries = []
        async with httpx.AsyncClient(timeout=90) as client:
            for path in paths[:5]:
                url = base_url.rstrip("/") + path
                try:
                    resp = await client.post(
                        "https://api.firecrawl.dev/v1/scrape",
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json",
                        },
                        json={"url": url, "formats": ["markdown"]},
                    )
                    if resp.status_code == 200:
                        md = resp.json().get("data", {}).get("markdown", "")
                        summaries.append(md[:1500])
                except Exception as exc:
                    summaries.append(f"Error scraping {url}: {exc}")
        return "\n\n".join(summaries)[:6000]


class LLMClient:
    def __init__(self, config: ConfigStore | None = None) -> None:
        self.config = config or ConfigStore()

    async def complete(self, system: str, user: str, json_mode: bool = False) -> str:
        api_key = self.config.get("openai_api_key")
        model = self.config.get("openai_model", "gpt-4o-mini")
        if not api_key:
            if json_mode:
                return json.dumps(
                    {
                        "icp": {"buyer_types": ["distributor"], "company_size": "20-500"},
                        "keywords": {"es": [user[:80]], "en": []},
                        "channel_plan": [
                            {"channel": "email", "priority": 1},
                            {"channel": "whatsapp", "priority": 2},
                        ],
                        "seeds": {"companies": [], "similar_search_queries": [user]},
                        "action_plan": {"week1": "Track B anchors", "week2": "Exa 20 leads"},
                    },
                    ensure_ascii=False,
                )
            return (
                f"Mock outreach for: {user[:200]}\n\n"
                "Subject: Partnership opportunity - kitchen supplies OEM\n"
                "Score: B"
            )
        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.4,
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
