"""System readiness API."""

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.database import init_db
from main import app


@pytest.mark.asyncio
async def test_readiness_includes_production_blockers():
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post(
            "/api/auth/otp/send",
            json={"email": "admin@example.com", "portal": "admin"},
        )
        log = Path("data/auth_emails.log")
        code = ""
        if log.exists():
            import re

            matches = re.findall(r"\b\d{6}\b", log.read_text(encoding="utf-8"))
            code = matches[-1] if matches else ""
        assert code, "OTP not found in auth_emails.log"
        verify = await client.post(
            "/api/auth/otp/verify",
            json={"email": "admin@example.com", "code": code, "portal": "admin"},
        )
        token = verify.json()["session_token"]
        resp = await client.get(
            "/api/system/readiness",
            headers={"X-Session-Token": token},
        )
    assert resp.status_code == 200
    data = resp.json()
    blockers = data.get("production_blockers", {})
    assert blockers.get("code_complete") is True
    assert "detected" in blockers
    assert "manual" in blockers
    assert any(item["id"] == "api_keys" for item in blockers["detected"])
