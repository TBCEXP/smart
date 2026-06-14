"""Artwork diff tests."""

from app.services.artwork_diff import combined_verdict, text_diff


def test_text_diff_detects_change():
    out = text_diff("line one\nline two", "line one\nline THREE")
    assert out["similarity"] < 1.0
    assert out["status"] in ("warn", "fail")


def test_combined_verdict_fail():
    assert combined_verdict([{"status": "pass"}, {"status": "fail"}]) == "failed"
