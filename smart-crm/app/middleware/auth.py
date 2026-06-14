from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.database import get_session
from app.services.auth import AuthService

# 公开路径（无需登录）
PUBLIC_PREFIXES = (
    "/api/health",
    "/api/auth/",
    "/api/webhooks/",
    "/static/",
    "/s/",
)

# 获客面板页面只读浏览允许；写操作需登录
PUBLIC_GET_PATHS = {"/", "/admin", "/portal"}

PROTECTED_WRITE_PREFIXES = (
    "/api/config",
    "/api/run",
    "/api/schedules",
    "/api/brainstorm/",
    "/api/market/",
    "/api/import/",
    "/api/tradeshows/",
    "/api/geo/",
    "/api/confirm/",
    "/api/regenerate/",
    "/api/bridge/",
    "/api/send-email",
)


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if any(path.startswith(p) for p in PUBLIC_PREFIXES):
            return await call_next(request)

        if request.method == "GET" and path in PUBLIC_GET_PATHS:
            return await call_next(request)

        # GET 读接口：批次/结果/配置掩码 允许面板演示；生产可收紧
        if request.method == "GET" and (
            path.startswith("/api/batch")
            or path.startswith("/api/batches")
            or path == "/api/config"
            or path.startswith("/api/stream/")
            or path.startswith("/api/market/")
            or path.startswith("/api/brainstorm/")
            or path.startswith("/api/import/")
            or path.startswith("/api/tradeshows")
            or path.startswith("/api/geo/")
        ):
            return await call_next(request)

        needs_auth = request.method != "GET" or any(
            path.startswith(p) for p in PROTECTED_WRITE_PREFIXES
        )
        if not needs_auth:
            return await call_next(request)

        token = request.headers.get("X-Session-Token") or request.cookies.get("session_token")
        if not token:
            return JSONResponse({"detail": "Authentication required"}, status_code=401)

        auth = AuthService()
        async with get_session() as db:
            session = await auth.get_session(db, token)
            if not session:
                return JSONResponse({"detail": "Invalid or expired session"}, status_code=401)
            request.state.user_email = session.email
            request.state.user_role = session.role
            request.state.user_portal = session.portal

        return await call_next(request)
