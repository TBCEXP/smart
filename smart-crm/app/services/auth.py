from __future__ import annotations

import random
import secrets
import string
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.entities import AuthToken, AuthWhitelist, UserSession
from app.services.config_store import ConfigStore


class AuthService:
    def __init__(self) -> None:
        self.config = ConfigStore()

    async def ensure_default_whitelist(self, db: AsyncSession) -> None:
        defaults = [
            ("admin@example.com", "admin", "admin"),
            ("sales@example.com", "admin", "sales"),
            ("customer@example.com", "portal", "customer"),
        ]
        for email, portal, role in defaults:
            existing = await db.execute(
                select(AuthWhitelist).where(AuthWhitelist.email == email)
            )
            if not existing.scalar_one_or_none():
                db.add(AuthWhitelist(email=email, portal=portal, role=role))
        await db.commit()

    async def is_whitelisted(self, db: AsyncSession, email: str, portal: str) -> bool:
        result = await db.execute(
            select(AuthWhitelist).where(
                AuthWhitelist.email == email.lower(),
                AuthWhitelist.portal == portal,
                AuthWhitelist.active.is_(True),
            )
        )
        return result.scalar_one_or_none() is not None

    def _generate_otp(self) -> str:
        return "".join(random.choices(string.digits, k=6))

    async def send_otp(self, db: AsyncSession, email: str, portal: str) -> dict[str, str]:
        if not await self.is_whitelisted(db, email, portal):
            raise PermissionError("Email not authorized")
        code = self._generate_otp()
        token = AuthToken(
            email=email.lower(),
            portal=portal,
            token_type="otp",
            token_value=code,
            expires_at=datetime.utcnow() + timedelta(minutes=settings.otp_ttl_minutes),
        )
        db.add(token)
        await db.commit()
        await self._send_email(
            email,
            "SMART CRM Login Code",
            f"Your verification code is: {code}\nValid for {settings.otp_ttl_minutes} minutes.",
        )
        return {"status": "sent", "type": "otp"}

    async def send_magic_link(self, db: AsyncSession, email: str, portal: str) -> dict[str, str]:
        if not await self.is_whitelisted(db, email, portal):
            raise PermissionError("Email not authorized")
        token_value = secrets.token_urlsafe(32)
        token = AuthToken(
            email=email.lower(),
            portal=portal,
            token_type="magic",
            token_value=token_value,
            expires_at=datetime.utcnow() + timedelta(minutes=settings.magic_link_ttl_minutes),
        )
        db.add(token)
        await db.commit()
        link = f"{settings.app_base_url}/api/auth/magic?token={token_value}&portal={portal}"
        await self._send_email(
            email,
            "SMART CRM Login Link",
            f"Click to login (valid {settings.magic_link_ttl_minutes} min):\n{link}",
        )
        return {"status": "sent", "type": "magic_link"}

    async def verify_otp(
        self, db: AsyncSession, email: str, code: str, portal: str
    ) -> UserSession:
        result = await db.execute(
            select(AuthToken).where(
                AuthToken.email == email.lower(),
                AuthToken.portal == portal,
                AuthToken.token_type == "otp",
                AuthToken.token_value == code,
                AuthToken.used.is_(False),
                AuthToken.expires_at > datetime.utcnow(),
            )
        )
        token = result.scalar_one_or_none()
        if not token:
            raise ValueError("Invalid or expired code")
        token.used = True
        return await self._create_session(db, email, portal)

    async def verify_magic(self, db: AsyncSession, token_value: str, portal: str) -> UserSession:
        result = await db.execute(
            select(AuthToken).where(
                AuthToken.token_value == token_value,
                AuthToken.portal == portal,
                AuthToken.token_type == "magic",
                AuthToken.used.is_(False),
                AuthToken.expires_at > datetime.utcnow(),
            )
        )
        token = result.scalar_one_or_none()
        if not token:
            raise ValueError("Invalid or expired link")
        token.used = True
        return await self._create_session(db, token.email, portal)

    async def _create_session(self, db: AsyncSession, email: str, portal: str) -> UserSession:
        wl = await db.execute(
            select(AuthWhitelist).where(
                AuthWhitelist.email == email.lower(),
                AuthWhitelist.portal == portal,
            )
        )
        entry = wl.scalar_one_or_none()
        session_token = secrets.token_urlsafe(48)
        session = UserSession(
            email=email.lower(),
            portal=portal,
            role=entry.role if entry else "sales",
            session_token=session_token,
            expires_at=datetime.utcnow() + timedelta(days=settings.session_days),
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)
        return session

    async def get_session(self, db: AsyncSession, session_token: str) -> UserSession | None:
        result = await db.execute(
            select(UserSession).where(
                UserSession.session_token == session_token,
                UserSession.expires_at > datetime.utcnow(),
            )
        )
        return result.scalar_one_or_none()

    async def _send_email(self, to_email: str, subject: str, body: str) -> None:
        resend_key = self.config.get("resend_api_key")
        if resend_key:
            try:
                import resend

                resend.api_key = resend_key
                resend.Emails.send(
                    {
                        "from": self.config.get("resend_from_email", "onboarding@resend.dev"),
                        "to": [to_email],
                        "subject": subject,
                        "text": body,
                    }
                )
                return
            except Exception:
                pass
        # Dev fallback: log to data dir
        log_path = settings.data_dir / "auth_emails.log"
        log_path.write_text(
            f"{datetime.utcnow().isoformat()} | {to_email} | {subject}\n{body}\n\n",
            encoding="utf-8",
        )
