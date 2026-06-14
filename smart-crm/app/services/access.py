from __future__ import annotations

from fastapi import HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import UserSession
from app.services.auth import AuthService

_auth = AuthService()


async def session_from_request(
    request: Request, db: AsyncSession
) -> UserSession | None:
    token = request.headers.get("X-Session-Token") or request.cookies.get(
        "session_token", ""
    )
    if not token:
        return None
    return await _auth.get_session(db, token)


async def require_session(request: Request, db: AsyncSession) -> UserSession:
    session = await session_from_request(request, db)
    if not session:
        raise HTTPException(401, "Authentication required")
    return session


def is_sales_scoped(session: UserSession | None) -> bool:
    return bool(session and session.role == "sales")
