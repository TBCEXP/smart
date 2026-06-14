from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PROMPTS_PATH = Path(__file__).resolve().parent.parent / "pipeline" / "prompts.yaml"


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_geo_config() -> dict[str, Any]:
    return load_yaml(DATA_DIR / "geo_config.yaml")


def load_expansion_tiers() -> dict[str, Any]:
    return load_yaml(DATA_DIR / "expansion_tiers.yaml")


def load_prompts() -> dict[str, Any]:
    return load_yaml(PROMPTS_PATH)


def get_l3_categories() -> list[dict[str, Any]]:
    geo = load_geo_config()
    return geo.get("categories", {}).get("l3", [])


def get_country_config(iso: str) -> dict[str, Any]:
    return load_geo_config().get("countries", {}).get(iso.upper(), {})


def resolve_exa_query(
    keyword: str,
    category_l3: str = "",
    city: str = "",
    country_iso: str = "",
    language: str = "es",
    search_type: str = "standard",
) -> str:
    """Resolve the Exa search phrase from L3 templates, similar-company templates, or keyword."""
    if search_type == "similar" and category_l3:
        anchor = keyword.strip()
        if anchor and not anchor.lower().startswith("category:company"):
            return build_exa_query(
                category_l3, city, country_iso, language, search_type, anchor_brand=anchor
            )
    if category_l3:
        return build_exa_query(category_l3, city, country_iso, language, search_type)
    return keyword


def build_exa_query(
    category_l3: str,
    city: str,
    country: str,
    language: str = "es",
    search_type: str = "standard",
    anchor_brand: str = "",
) -> str:
    prompts = load_prompts()
    if search_type == "similar" and anchor_brand:
        templates = prompts.get("similar_company_templates", [])
        if templates:
            return templates[0].format(
                product=category_l3.replace("-", " "),
                anchor_brand=anchor_brand,
                country=country,
                city=city,
                category_l3=category_l3.replace("-", " "),
            )
    templates = prompts.get("exa_query_templates", {}).get(category_l3, {})
    template = templates.get(language) or templates.get("es") or templates.get("en")
    if not template:
        return f"wholesale {category_l3.replace('-', ' ')} distributor {city} {country}"
    return template.format(city=city, country=country)


def get_hs_codes_for_l3(category_l3: str) -> list[str]:
    prompts = load_prompts()
    return prompts.get("track_c_hs_defaults", {}).get(category_l3, ["7323"])


def save_batch_file(batch_id: str, data: dict[str, Any]) -> Path:
    from app.config import settings

    path = settings.data_dir / "batches" / f"{batch_id}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    return path


def load_batch_file(batch_id: str) -> dict[str, Any]:
    from app.config import settings

    path = settings.data_dir / "batches" / f"{batch_id}.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text())
