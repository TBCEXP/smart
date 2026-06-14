"""Tus-style resumable uploads for large files (local staging → R2 or tus:// URL)."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from app.config import settings

TUS_SCHEME = "tus://"
DEFAULT_CHUNK_SIZE = 1024 * 1024  # 1 MiB


@dataclass
class TusSession:
    upload_id: str
    transfer_id: str
    offset: int
    length: int | None
    filename: str
    content_type: str
    status: str  # uploading | completed
    created_at: str
    completed_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def tus_root() -> Path:
    root = settings.data_dir / "tus"
    root.mkdir(parents=True, exist_ok=True)
    return root


def tus_available() -> bool:
    try:
        tus_root()
        return True
    except Exception:
        return False


def _meta_path(upload_id: str) -> Path:
    return tus_root() / f"{upload_id}.json"


def _data_path(upload_id: str) -> Path:
    return tus_root() / f"{upload_id}.partial"


def _save_meta(session: TusSession) -> None:
    _meta_path(session.upload_id).write_text(
        json.dumps(session.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_session(upload_id: str) -> TusSession | None:
    path = _meta_path(upload_id)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return TusSession(**data)


def create_session(
    transfer_id: str,
    *,
    upload_length: int | None = None,
    filename: str = "upload.bin",
    content_type: str = "application/octet-stream",
) -> TusSession:
    upload_id = str(uuid.uuid4())
    session = TusSession(
        upload_id=upload_id,
        transfer_id=transfer_id,
        offset=0,
        length=upload_length,
        filename=filename,
        content_type=content_type,
        status="uploading",
        created_at=datetime.utcnow().isoformat(),
    )
    _data_path(upload_id).touch()
    _save_meta(session)
    return session


def append_chunk(upload_id: str, offset: int, data: bytes) -> dict[str, Any]:
    session = load_session(upload_id)
    if not session:
        return {"ok": False, "detail": "upload not found", "status": 404}
    if session.status == "completed":
        return {"ok": False, "detail": "upload already completed", "status": 409}
    if offset != session.offset:
        return {
            "ok": False,
            "detail": f"offset mismatch (expected {session.offset}, got {offset})",
            "status": 409,
            "expected_offset": session.offset,
        }
    if session.length is not None and offset + len(data) > session.length:
        return {"ok": False, "detail": "chunk exceeds Upload-Length", "status": 413}

    data_path = _data_path(upload_id)
    with data_path.open("ab") as fh:
        fh.write(data)
    session.offset += len(data)

    if session.length is not None and session.offset >= session.length:
        session.status = "completed"
        session.completed_at = datetime.utcnow().isoformat()
        final_name = f"{upload_id}_{session.filename}"
        final_path = tus_root() / final_name
        if final_path.exists():
            final_path.unlink()
        data_path.rename(final_path)
        _save_meta(session)
        return {
            "ok": True,
            "offset": session.offset,
            "completed": True,
            "file_url": f"{TUS_SCHEME}{upload_id}/{session.filename}",
            "local_path": str(final_path),
        }

    _save_meta(session)
    return {"ok": True, "offset": session.offset, "completed": False}


def parse_tus_url(file_url: str) -> tuple[str, str] | None:
    if not file_url.startswith(TUS_SCHEME):
        return None
    rest = file_url[len(TUS_SCHEME) :]
    if "/" not in rest:
        return None
    upload_id, filename = rest.split("/", 1)
    return upload_id, filename


def resolve_tus_download(upload_id: str) -> Path | None:
    session = load_session(upload_id)
    if not session or session.status != "completed":
        return None
    final_path = tus_root() / f"{upload_id}_{session.filename}"
    return final_path if final_path.exists() else None


def tus_status() -> dict[str, Any]:
    return {
        "available": tus_available(),
        "protocol": "tus-1.0.0-subset",
        "chunk_size": DEFAULT_CHUNK_SIZE,
        "storage": str(tus_root()),
    }
