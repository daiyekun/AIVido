from __future__ import annotations

from app.services.billing_service import estimate_credit


def test_estimate_by_resolution():
    assert estimate_credit({"1K": 1.0, "2K": 1.5}, resolution="2K") == 1.5


def test_estimate_by_duration():
    assert estimate_credit({"4": 2.0, "8": 4.0}, duration=8) == 4.0


def test_estimate_empty_config():
    assert estimate_credit(None, resolution="2K") == 0.0
    assert estimate_credit({}, resolution="2K") == 0.0


def test_estimate_missing_key():
    assert estimate_credit({"1K": 1.0}, resolution="4K") == 0.0


def test_estimate_resolution_priority_over_duration():
    assert estimate_credit({"2K": 1.5}, resolution="2K", duration=4) == 1.5
