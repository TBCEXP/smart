"""Tus resumable upload tests."""

import tempfile
from pathlib import Path

from app.config import settings
from app.services.tus_upload import (
    append_chunk,
    create_session,
    load_session,
    resolve_tus_download,
    tus_available,
)


def test_tus_available():
    assert tus_available() is True


def test_create_append_and_complete():
    with tempfile.TemporaryDirectory() as tmp:
        settings.data_dir = Path(tmp)
        session = create_session("transfer-1", upload_length=10, filename="demo.bin")
        assert session.offset == 0

        r1 = append_chunk(session.upload_id, 0, b"hello")
        assert r1["ok"] is True
        assert r1["offset"] == 5
        assert r1["completed"] is False

        r2 = append_chunk(session.upload_id, 5, b"world")
        assert r2["ok"] is True
        assert r2["completed"] is True
        assert r2["file_url"].startswith("tus://")

        loaded = load_session(session.upload_id)
        assert loaded is not None
        assert loaded.status == "completed"
        assert loaded.offset == 10

        path = resolve_tus_download(session.upload_id)
        assert path is not None
        assert path.read_bytes() == b"helloworld"


def test_offset_mismatch():
    with tempfile.TemporaryDirectory() as tmp:
        settings.data_dir = Path(tmp)
        session = create_session("transfer-2", upload_length=4)
        append_chunk(session.upload_id, 0, b"ab")
        bad = append_chunk(session.upload_id, 5, b"cd")
        assert bad["ok"] is False
        assert bad["status"] == 409
