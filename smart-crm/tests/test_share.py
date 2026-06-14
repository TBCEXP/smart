"""Share link helpers."""

from app.services.share import _new_token


def test_new_token_unique():
    a = _new_token()
    b = _new_token()
    assert a != b
    assert len(a) >= 16
