"""Phase 1 order PATCH tests."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.database import get_session, init_db
from app.models.entities import SalesOrder
from app.services.phase1 import next_order_no
from main import app


@pytest.mark.asyncio
async def test_patch_order_status_requires_auth():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.patch("/api/orders/fake-id", json={"status": "confirmed"})
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_patch_order_status_with_session():
    await init_db()
    async with get_session() as db:
        order = SalesOrder(
            order_no=next_order_no(),
            customer_name="Patch Test",
            status="draft",
            assigned_to="admin@example.com",
        )
        db.add(order)
        await db.commit()
        await db.refresh(order)
        order_id = order.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        send = await client.post(
            "/api/auth/otp/send",
            json={"email": "admin@example.com", "portal": "admin"},
        )
        assert send.status_code == 200
        from pathlib import Path

        log = Path("data/auth_emails.log")
        code = ""
        if log.exists():
            import re

            codes = re.findall(r"\d{6}", log.read_text())
            code = codes[-1] if codes else ""
        assert code
        verify = await client.post(
            "/api/auth/otp/verify",
            json={"email": "admin@example.com", "code": code, "portal": "admin"},
        )
        token = verify.json()["session_token"]
        resp = await client.patch(
            f"/api/orders/{order_id}",
            json={"status": "confirmed"},
            headers={"X-Session-Token": token},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "confirmed"
