from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet

from app.config import ConfigPayload, settings

SENSITIVE_KEYS = {
    "exa_api_key",
    "firecrawl_api_key",
    "openai_api_key",
    "feishu_app_secret",
    "tbcexp_api_token",
    "resend_api_key",
    "apollo_api_key",
    "r2_access_key_id",
    "r2_secret_access_key",
    "importgenius_api_key",
    "smtp_password",
}


class ConfigStore:
    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = data_dir or settings.data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.config_path = self.data_dir / "config.json"
        self.secret_path = self.data_dir / "secret.key"
        self._fernet = self._load_fernet()

    def _load_fernet(self) -> Fernet:
        if self.secret_path.exists():
            key = self.secret_path.read_bytes()
        else:
            key = Fernet.generate_key()
            self.secret_path.write_bytes(key)
            os.chmod(self.secret_path, 0o600)
        return Fernet(key)

    def _encrypt(self, value: str) -> str:
        if not value:
            return ""
        return self._fernet.encrypt(value.encode()).decode()

    def _decrypt(self, value: str) -> str:
        if not value:
            return ""
        try:
            return self._fernet.decrypt(value.encode()).decode()
        except Exception:
            return value

    def load(self) -> dict[str, Any]:
        if not self.config_path.exists():
            return ConfigPayload().model_dump()
        raw = json.loads(self.config_path.read_text())
        for key in SENSITIVE_KEYS:
            if key in raw and raw[key]:
                raw[key] = self._decrypt(raw[key])
        return raw

    def save(self, payload: ConfigPayload) -> dict[str, Any]:
        data = payload.model_dump()
        stored = data.copy()
        for key in SENSITIVE_KEYS:
            if stored.get(key):
                stored[key] = self._encrypt(stored[key])
        self.config_path.write_text(json.dumps(stored, indent=2))
        os.chmod(self.config_path, 0o600)
        return self.masked(data)

    def masked(self, data: dict[str, Any] | None = None) -> dict[str, Any]:
        data = data or self.load()
        masked = data.copy()
        for key in SENSITIVE_KEYS:
            val = masked.get(key, "")
            if val:
                masked[key] = f"{val[:4]}...{val[-4:]}" if len(val) > 8 else "****"
        return masked

    def get(self, key: str, default: str = "") -> str:
        return self.load().get(key, default)
