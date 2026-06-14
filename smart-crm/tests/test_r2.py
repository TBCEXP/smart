"""R2 client helpers."""

from app.services.r2_client import R2Client


def test_parse_r2_url():
    parsed = R2Client.parse_r2_url("r2://smart-crm/catalogs/demo.pdf")
    assert parsed == ("smart-crm", "catalogs/demo.pdf")
    assert R2Client.parse_r2_url("https://example.com/a.pdf") is None


def test_resolve_mock_pending():
    client = R2Client()
    out = client.resolve_download_url("r2://smart-crm/catalogs/demo.pdf")
    assert out["storage"] == "r2_pending"
    assert out["download_url"] is None
    assert out["mode"] == "mock"


def test_resolve_public_https():
    client = R2Client()
    url = "https://cdn.example.com/catalog.pdf"
    out = client.resolve_download_url(url)
    assert out["storage"] == "url"
    assert out["download_url"] == url
    assert out["mode"] == "public"


def test_presign_put_mock():
    client = R2Client()
    out = client.presign_put("catalogs/test.pdf")
    assert out["mode"] == "mock"
    assert out["file_url"] == "r2://smart-crm/catalogs/test.pdf"
    assert out["upload_url"] is None
