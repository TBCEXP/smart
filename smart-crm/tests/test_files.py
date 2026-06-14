"""File transfer helpers."""

from app.models.entities import FileTransfer
from app.services.files import file_dict


def test_file_dict_structure():
    transfer = FileTransfer(
        title="Packaging ZIP",
        file_url="r2://smart-crm/files/pack.zip",
        file_size_mb=12.5,
        content_type="application/zip",
    )
    out = file_dict(transfer)
    assert out["title"] == "Packaging ZIP"
    assert out["file_size_mb"] == 12.5
    assert "download_url" in out
    assert out["storage"] in ("r2_pending", "r2", "empty", "r2_error")
