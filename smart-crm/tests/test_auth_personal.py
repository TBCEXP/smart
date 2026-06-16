"""Personal email auto-whitelist for login."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.services.auth import email_domain, is_personal_email_domain
from main import app


def test_personal_email_domains():
    assert is_personal_email_domain("hotmail.com")
    assert is_personal_email_domain("hotmail.co.uk")
    assert is_personal_email_domain("outlook.com")
    assert is_personal_email_domain("live.com")
    assert is_personal_email_domain("msn.com")
    assert not is_personal_email_domain("tbcexp.com")


def test_email_domain_parse():
    assert email_domain("tbcexp@hotmail.com") == "hotmail.com"


@pytest.mark.asyncio
async def test_hotmail_otp_send_auto_whitelist():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/auth/otp/send",
            json={"email": "newuser@hotmail.com", "portal": "admin"},
        )
    assert resp.status_code == 200
    assert resp.json().get("status") == "sent"
