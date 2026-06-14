"""System readiness API."""

import pytest
from httpx import ASGITransport, AsyncClient

from main import app


@pytest.mark.asyncio
async def test_readiness_includes_production_blockers():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/system/readiness")
    assert resp.status_code == 200
    data = resp.json()
    blockers = data.get("production_blockers", {})
    assert blockers.get("code_complete") is True
    assert "detected" in blockers
    assert "manual" in blockers
    assert any(item["id"] == "api_keys" for item in blockers["detected"])
