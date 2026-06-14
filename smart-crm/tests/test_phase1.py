"""Phase 1 catalog and factory helpers."""

from app.services.phase1 import DEFAULT_FACTORIES, catalog_tree, seed_factories


def test_catalog_tree_has_l3():
    tree = catalog_tree()
    assert "l3" in tree
    codes = [c["code"] for c in tree["l3"]]
    assert "bakeware" in codes
    assert "cookware-commercial" in codes


def test_default_factories_seed_data():
    assert len(DEFAULT_FACTORIES) >= 3
    assert all("code" in f for f in DEFAULT_FACTORIES)
