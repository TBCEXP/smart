from __future__ import annotations

from datetime import datetime

from app.config import settings
from app.services.config_store import ConfigStore


async def send_notification_email(
    to_email: str,
    subject: str,
    body: str,
    config: ConfigStore | None = None,
) -> dict[str, str]:
    """Resend 或写入 auth_emails.log（与 OTP 相同回退）。"""
    if not to_email:
        return {"mode": "skipped", "detail": "无收件人"}
    cfg = config or ConfigStore()
    resend_key = cfg.get("resend_api_key")
    if resend_key:
        try:
            import resend

            resend.api_key = resend_key
            resend.Emails.send(
                {
                    "from": cfg.get("resend_from_email", "onboarding@resend.dev"),
                    "to": [to_email],
                    "subject": subject,
                    "text": body,
                }
            )
            return {"mode": "live", "detail": f"已发送至 {to_email}"}
        except Exception as exc:
            return {"mode": "error", "detail": str(exc)[:200]}
    log_path = settings.data_dir / "auth_emails.log"
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(f"{datetime.utcnow().isoformat()} | {to_email} | {subject}\n{body}\n\n")
    return {"mode": "mock", "detail": f"已写入 {log_path.name}"}


async def notify_share_link(
    to_email: str,
    share_url: str,
    resource_type: str,
    message: str = "",
    config: ConfigStore | None = None,
) -> dict[str, str]:
    labels = {
        "order": "订单",
        "catalog": "目录",
        "file": "大文件",
        "factories": "工厂列表",
    }
    label = labels.get(resource_type, resource_type)
    body = f"您好，\n\nSMART CRM 向您分享了{label}查看链接：\n{share_url}\n\n"
    if message:
        body += f"{message}\n\n"
    body += "链接有效期内可多次打开。如有疑问请联系您的业务员。"
    return await send_notification_email(
        to_email,
        f"SMART CRM — {label}分享链接",
        body,
        config,
    )
