"""TBCEXP ERP bridge tests."""

import pytest

from app.models.entities import Lead
from app.services.tbcexp_client import TbcexpClient


@pytest.mark.asyncio
async def test_push_lead_mock_mode():
    client = TbcexpClient()
    lead = Lead(
        id="test-lead-uuid-001",
        company_name="Demo Hotel Supplies",
        country_iso="MX",
        category_l3="bakeware",
    )
    result = await client.push_lead(lead)
    assert result["status"] == "ok"
    assert result["mode"] == "mock"
    assert "external_id" in result


@pytest.mark.asyncio
async def test_list_orders_mock_mode():
    client = TbcexpClient()
    result = await client.list_orders()
    assert result["mode"] == "mock"
    assert result["total"] >= 1
    assert result["orders"][0]["order_no"]


def test_lead_payload_fields():
    client = TbcexpClient()
    lead = Lead(
        id="abc",
        company_name="Corp",
        domain="corp.com",
        country_iso="CO",
        assigned_to="sales@example.com",
    )
    payload = client.lead_payload(lead)
    assert payload["source"] == "smart_crm"
    assert payload["company_name"] == "Corp"
    assert payload["assigned_to"] == "sales@example.com"
