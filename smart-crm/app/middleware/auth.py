from __future__ import annotations

from urllib.parse import quote

from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.database import get_session
from app.services.auth import AuthService

# 完全公开 API（无需登录）
PUBLIC_API_PREFIXES = (
    "/api/health",
    "/api/auth/",
    "/api/webhooks/",
    "/api/share/",
)

# 运维探测用，不暴露业务数据
PUBLIC_API_EXACT = {
    "/api/integrations/status",
}

PUBLIC_PAGE_PATHS = {
    "/admin",
    "/portal",
    "/auth/callback",
    "/docs/feishu-fields",
}

# 需登录才能访问的页面（未登录重定向到登录页）
PROTECTED_PAGE_PATHS = {
    "/",
    "/admin/leads",
    "/admin/dashboard",
    "/portal/dashboard",
}


def _extract_token(request: Request) -> str | None:
    token = request.headers.get("X-Session-Token") or request.cookies.get("session_token")
    if not token and request.url.path.startswith("/api/stream/"):
        token = request.query_params.get("token")
    return token or None


def _login_redirect(request: Request) -> RedirectResponse:
    path = request.url.path
    portal = "portal" if path.startswith("/portal") else "admin"
    next_path = quote(path, safe="/")
    return RedirectResponse(f"/{portal}?next={next_path}", status_code=302)


class AuthMiddleware(BaseHTTPMiddleware):
    """
    获客面板与业务 API 均需登录；分享链接、健康检查、登录接口保持公开。
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if path.startswith("/static/"):
            return await call_next(request)

        if path.startswith("/s/"):
            return await call_next(request)

        if path in PUBLIC_PAGE_PATHS:
            return await call_next(request)

        if any(path.startswith(p) for p in PUBLIC_API_PREFIXES):
            return await call_next(request)

        if path in PUBLIC_API_EXACT:
            return await call_next(request)

        needs_auth = path in PROTECTED_PAGE_PATHS or path.startswith("/api/")
        if not needs_auth:
            return await call_next(request)

        token = _extract_token(request)
        if not token:
            if path.startswith("/api/"):
                return JSONResponse({"detail": "Authentication required"}, status_code=401)
            return _login_redirect(request)

        auth = AuthService()
        async with get_session() as db:
            session = await auth.get_session(db, token)
            if not session:
                if path.startswith("/api/"):
                    return JSONResponse(
                        {"detail": "Invalid or expired session"}, status_code=401
                    )
                return _login_redirect(request)
            request.state.user_email = session.email
            request.state.user_role = session.role
            request.state.user_portal = session.portal

        return await call_next(request)
