from __future__ import annotations

import json
import re
from typing import Any

# Exa best practice: exclude non-B2B domains from lead results
EXA_EXCLUDE_DOMAINS = [
    "facebook.com",
    "linkedin.com",
    "instagram.com",
    "twitter.com",
    "x.com",
    "youtube.com",
    "wikipedia.org",
    "amazon.com",
    "mercadolibre.com",
    "alibaba.com",
]


def build_semantic_exa_query(
    keyword: str,
    search_type: str = "standard",
    country_iso: str = "",
    city: str = "",
) -> str:
    """Turn keyword into Exa-friendly semantic description (not bare keywords)."""
    if search_type == "similar":
        if "category:company" not in keyword.lower():
            return f"category:company {keyword}"
        return keyword
    if country_iso or city:
        return (
            f"B2B wholesale distributor or importer of hospitality kitchen supplies "
            f"in {city} {country_iso}. {keyword}. Company website with catalog or wholesale page."
        )
    return f"B2B company: {keyword}. Official business website with products or wholesale."


def parse_outreach_response(raw: str) -> dict[str, str]:
    """Parse LLM outreach — supports JSON or plain text fallback."""
    raw = raw.strip()
    if raw.startswith("{"):
        try:
            data = json.loads(raw)
            subjects = data.get("subject_lines", [])
            if isinstance(subjects, list):
                subject_str = " | ".join(subjects[:2])
            else:
                subject_str = str(subjects)
            return {
                "email_body": data.get("email_body", raw),
                "subject_lines": subject_str,
                "lead_score": str(data.get("lead_score", "B")).upper()[:1],
                "whatsapp_intro": data.get("whatsapp_intro", ""),
            }
        except json.JSONDecodeError:
            pass
    score = "B"
    if "score: a" in raw.lower() or "评分: a" in raw:
        score = "A"
    elif "score: c" in raw.lower():
        score = "C"
    return {
        "email_body": raw,
        "subject_lines": "",
        "lead_score": score,
        "whatsapp_intro": "",
    }
