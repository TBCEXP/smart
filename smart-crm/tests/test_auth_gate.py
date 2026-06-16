"""Auth gate: main panel and APIs require login."""

import pytest
from httpx import ASGITransport, AsyncClient

from main import app


@pytest.mark.asyncio
async def test_root_redirects_without_session():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
        resp = await client.get("/")
    assert resp.status_code == 302
    assert resp.headers["location"].startswith("/admin?next=")


@pytest.mark.asyncio
async def test_api_leads_requires_auth():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/leads?limit=1")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_health_and_share_stay_public():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        health = await client.get("/api/health")
        share = await client.get("/api/share/invalid-token-test")
    assert health.status_code == 200
    assert share.status_code == 200
