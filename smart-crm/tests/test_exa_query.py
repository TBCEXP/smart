"""Unit tests for Exa query resolution (LATAM Spanish templates)."""

from app.services.data_loader import resolve_exa_query
from app.services.exa_utils import build_semantic_exa_query


def test_resolve_exa_query_bakeware_mx():
    q = resolve_exa_query(
        "",
        category_l3="bakeware",
        city="CDMX",
        country_iso="MX",
        language="es",
    )
    assert "moldes" in q.lower() or "bakeware" in q.lower()
    assert "CDMX" in q
    assert "MX" in q


def test_resolve_exa_query_cookware_co():
    q = resolve_exa_query(
        "",
        category_l3="cookware-commercial",
        city="Bogotá",
        country_iso="CO",
        language="es",
    )
    assert "hostelería" in q.lower() or "cocina" in q.lower()
    assert "Bogotá" in q
    assert "CO" in q


def test_resolve_exa_query_similar_uses_anchor():
    q = resolve_exa_query(
        "Vasconia",
        category_l3="bakeware",
        city="CDMX",
        country_iso="MX",
        language="es",
        search_type="similar",
    )
    assert "Vasconia" in q
    assert "category:company" in q.lower() or "importers" in q.lower()


def test_resolve_exa_query_keyword_fallback():
    q = resolve_exa_query("custom wholesale distributor Miami")
    assert q == "custom wholesale distributor Miami"


def test_semantic_preserves_spanish_template():
    resolved = resolve_exa_query(
        "",
        category_l3="flatware",
        city="Medellín",
        country_iso="CO",
        language="es",
    )
    semantic = build_semantic_exa_query(
        resolved, "standard", "CO", "Medellín", "es"
    )
    assert semantic == resolved


def test_semantic_wraps_bare_keyword_latam():
    semantic = build_semantic_exa_query(
        "kitchen supplies",
        "standard",
        "MX",
        "CDMX",
        "es",
    )
    assert "mayorista" in semantic.lower() or "B2B" in semantic
    assert "kitchen supplies" in semantic
