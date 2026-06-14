from __future__ import annotations

import re
from typing import Any

from app.config import settings
from app.services.config_store import ConfigStore
from app.services.tus_upload import TUS_SCHEME, parse_tus_url

R2_SCHEME_RE = re.compile(r"^r2://([^/]+)/(.+)$")


class R2Client:
    """Cloudflare R2（S3 兼容）— 目录 PDF 签名 URL。"""

    def __init__(self, config: ConfigStore | None = None) -> None:
        self.config = config or ConfigStore()

    def configured(self) -> bool:
        return bool(
            self.config.get("r2_account_id", "").strip()
            and self.config.get("r2_access_key_id", "").strip()
            and self.config.get("r2_secret_access_key", "").strip()
        )

    def default_bucket(self) -> str:
        return self.config.get("r2_bucket", "").strip() or "smart-crm"

    def endpoint_url(self) -> str:
        account = self.config.get("r2_account_id", "").strip()
        return f"https://{account}.r2.cloudflarestorage.com"

    @staticmethod
    def parse_r2_url(url: str) -> tuple[str, str] | None:
        match = R2_SCHEME_RE.match(url.strip())
        if not match:
            return None
        return match.group(1), match.group(2)

    def resolve_download_url(self, file_url: str, ttl_seconds: int = 3600) -> dict[str, Any]:
        if not file_url:
            return {
                "storage": "empty",
                "download_url": None,
                "mode": "none",
                "detail": "无文件",
            }

        if file_url.startswith("r2://"):
            parsed = self.parse_r2_url(file_url)
            if not parsed:
                return {
                    "storage": "r2_error",
                    "download_url": None,
                    "mode": "error",
                    "detail": "无效的 r2:// URL",
                }
            bucket, key = parsed
            if not self.configured():
                return {
                    "storage": "r2_pending",
                    "download_url": None,
                    "mode": "mock",
                    "detail": "R2 未配置，PDF 待上传",
                }
            return {
                "storage": "r2",
                "download_url": self.presign_get(bucket, key, ttl_seconds),
                "mode": "live",
                "expires_in": ttl_seconds,
                "detail": "R2 签名下载链接",
            }

        if file_url.startswith("http://") or file_url.startswith("https://"):
            return {
                "storage": "url",
                "download_url": file_url,
                "mode": "public",
                "detail": "直接 HTTPS 链接",
            }

        if file_url.startswith(TUS_SCHEME):
            parsed = parse_tus_url(file_url)
            if not parsed:
                return {
                    "storage": "tus_error",
                    "download_url": None,
                    "mode": "error",
                    "detail": "无效的 tus:// URL",
                }
            upload_id, _ = parsed
            base = settings.app_base_url.rstrip("/")
            return {
                "storage": "tus",
                "download_url": f"{base}/api/files/tus/{upload_id}/content",
                "mode": "local",
                "detail": "断点续传本地文件",
            }

        return {
            "storage": "unknown",
            "download_url": None,
            "mode": "none",
            "detail": "未知存储格式",
        }

    def _s3_client(self):
        import boto3
        from botocore.config import Config

        return boto3.client(
            "s3",
            endpoint_url=self.endpoint_url(),
            aws_access_key_id=self.config.get("r2_access_key_id"),
            aws_secret_access_key=self.config.get("r2_secret_access_key"),
            config=Config(signature_version="s3v4"),
            region_name="auto",
        )

    def presign_get(self, bucket: str, key: str, ttl_seconds: int = 3600) -> str:
        client = self._s3_client()
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=ttl_seconds,
        )

    def presign_put(
        self,
        key: str,
        bucket: str | None = None,
        ttl_seconds: int = 900,
        content_type: str = "application/pdf",
    ) -> dict[str, Any]:
        bucket = bucket or self.default_bucket()
        file_url = f"r2://{bucket}/{key}"
        if not self.configured():
            return {
                "mode": "mock",
                "upload_url": None,
                "file_url": file_url,
                "bucket": bucket,
                "key": key,
                "detail": "R2 未配置",
            }
        client = self._s3_client()
        upload_url = client.generate_presigned_url(
            "put_object",
            Params={"Bucket": bucket, "Key": key, "ContentType": content_type},
            ExpiresIn=ttl_seconds,
        )
        return {
            "mode": "live",
            "upload_url": upload_url,
            "file_url": file_url,
            "bucket": bucket,
            "key": key,
            "expires_in": ttl_seconds,
            "content_type": content_type,
            "detail": "R2 签名上传链接",
        }

    async def probe(self) -> dict[str, Any]:
        if not self.configured():
            return {
                "id": "r2",
                "label": "Cloudflare R2",
                "status": "mock",
                "mock": True,
                "detail": "未配置 Account/Key（Phase 2 目录可选）",
            }
        try:
            client = self._s3_client()
            client.head_bucket(Bucket=self.default_bucket())
            return {
                "id": "r2",
                "label": "Cloudflare R2",
                "status": "ok",
                "mock": False,
                "detail": f"Bucket {self.default_bucket()} 可访问",
            }
        except Exception as exc:
            return {
                "id": "r2",
                "label": "Cloudflare R2",
                "status": "error",
                "mock": False,
                "detail": str(exc)[:200],
            }
