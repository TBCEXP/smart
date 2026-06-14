from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.database import get_session
from app.services.auth import AuthService

# 完全公开（无需登录）
PUBLIC_PREFIXES = (
    "/api/health",
    "/api/integrations/",
    "/api/auth/",
    "/api/webhooks/",
    "/api/stream/",
    "/static/",
    "/s/",
)

PUBLIC_GET_PATHS = {
    "/",
    "/admin",
    "/admin/leads",
    "/admin/dashboard",
    "/portal",
    "/portal/dashboard",
    "/docs/feishu-fields",
}

# 仅保护敏感写操作：API Key 保存、确认入库、ERP 同步、发信
PROTECTED_POST_PATHS = (
    "/api/config",
    "/api/confirm/",
    "/api/regenerate/",
    "/api/bridge/",
    "/api/send-email",
    "/api/integrations/feishu/test-write",
    "/api/factories",
    "/api/orders",
    "/api/orders/from-lead/",
    "/api/share/links",
    "/api/catalog/documents",
    "/api/catalog/documents/",
    "/api/files/transfers",
    "/api/files/transfers/",
    "/api/files/tus/",
    "/api/prepress/reviews",
    "/api/prepress/reviews/",
    "/api/inspections/production",
    "/api/inspections/production/",
)

PROTECTED_PATCH_PREFIXES = (
    "/api/orders/",
    "/api/catalog/documents/",
    "/api/inspections/production/",
)


class AuthMiddleware(BaseHTTPMiddleware):
    """
    获客面板（Tab1-7）保持 PDF 原设计：无需登录即可跑批次。
    仅保护 API Key 配置与销售确认类操作；生产环境建议 Nginx 层再加 IP 限制。
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if any(path.startswith(p) for p in PUBLIC_PREFIXES):
            return await call_next(request)

        if request.method == "GET":
            return await call_next(request)

        if request.method == "HEAD" and path.startswith("/api/files/tus/"):
            return await call_next(request)

        if path in PUBLIC_GET_PATHS:
            return await call_next(request)

        needs_auth = any(path.startswith(p) for p in PROTECTED_POST_PATHS)
        if request.method == "PATCH":
            needs_auth = needs_auth or any(path.startswith(p) for p in PROTECTED_PATCH_PREFIXES)
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
