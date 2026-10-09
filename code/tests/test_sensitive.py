from __future__ import annotations

import pytest

from app.core.exceptions import SensitiveWordError
from app.infrastructure.filter import sensitive


def test_check_sensitive_hit(monkeypatch):
    monkeypatch.setattr(sensitive, "_words", {"暴力", "色情"})
    assert sensitive.check_sensitive("包含暴力内容") == "暴力"


def test_check_sensitive_miss(monkeypatch):
    monkeypatch.setattr(sensitive, "_words", {"暴力"})
    assert sensitive.check_sensitive("正常内容") is None


def test_check_sensitive_empty(monkeypatch):
    monkeypatch.setattr(sensitive, "_words", set())
    assert sensitive.check_sensitive("任意内容") is None
    assert sensitive.check_sensitive("") is None


def test_assert_clean(monkeypatch):
    monkeypatch.setattr(sensitive, "_words", {"暴力"})
    with pytest.raises(SensitiveWordError):
        sensitive.assert_clean("有暴力")
    sensitive.assert_clean("正常")
