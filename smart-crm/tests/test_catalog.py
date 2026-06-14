"""Catalog document doc_type tests."""

from app.services.catalog import catalog_dict
from app.models.entities import CatalogDocument, Factory


def test_catalog_dict_includes_doc_type():
    doc = CatalogDocument(title="Test Quote", doc_type="quote", file_url="r2://b/k.pdf")
    factory = Factory(code="F-01", name_zh="测试厂")
    out = catalog_dict(doc, factory)
    assert out["doc_type"] == "quote"
