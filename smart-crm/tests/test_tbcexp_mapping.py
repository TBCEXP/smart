"""TBCEXP field mapping tests."""

from app.models.entities import Lead
from app.services.tbcexp_mapping import (
    erp_order_to_crm,
    field_map_documentation,
    lead_to_erp_payload,
)


def test_lead_payload_includes_extended_fields():
    lead = Lead(
        id="lead-001",
        company_name="Hotel MX",
        domain="hotel.mx",
        country_iso="MX",
        category_l1="kitchen",
        category_l2="hotel-restaurant",
        category_l3="bakeware",
        contact_email="buyer@hotel.mx",
        contact_name="Ana",
        buyer_type="distributor",
        track="track_a",
        hs_code="7323",
        firecrawl_summary="B2B hotel supplier",
    )
    payload = lead_to_erp_payload(lead)
    assert payload["external_id"] == "lead-001"
    assert payload["contact_email"] == "buyer@hotel.mx"
    assert payload["category_l1"] == "kitchen"
    assert payload["hs_code"] == "7323"
    assert payload["source"] == "smart_crm"


def test_erp_order_to_crm_mapping():
    row = {
        "external_id": "erp-99",
        "order_no": "TBCEXP-2026-0099",
        "customer_name": "Buyer Co",
        "customer_email": "b@co.com",
        "country_iso": "CO",
        "status": "confirmed",
        "currency": "USD",
        "total_amount": 9900.5,
        "assigned_to": "sales@example.com",
    }
    mapped = erp_order_to_crm(row)
    assert mapped["order_no"] == "TBCEXP-2026-0099"
    assert mapped["customer_name"] == "Buyer Co"
    assert mapped["total_amount"] == 9900.5
    assert mapped["notes"] == "erp_id:erp-99"


def test_field_map_documentation():
    doc = field_map_documentation()
    assert doc["version"] == "1.0"
    assert len(doc["lead_push"]["fields"]) >= 20
    assert len(doc["order_pull"]["fields"]) >= 5
