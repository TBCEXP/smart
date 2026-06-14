"""Apollo client mock enrichment."""

import pytest

from app.models.entities import Lead
from app.services.apollo_client import ApolloClient


@pytest.mark.asyncio
async def test_enrich_lead_mock():
    client = ApolloClient()
    lead = Lead(company_name="Hotel Supplies SA", domain="hotelsupplies.mx", website_url="https://hotelsupplies.mx")
    result = await client.enrich_lead(lead)
    assert result["mode"] == "mock"
    assert "@" in result["contact_email"]
