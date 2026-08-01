"""Membership helpers (post-enum): meets_minimum lives on the registry snapshot."""

from __future__ import annotations

import pytest
from app.modules.users import membership_registry as reg
from app.modules.users.membership import DEFAULT_SLUG, meets_minimum


@pytest.mark.unit
def test_default_slug() -> None:
    assert DEFAULT_SLUG == "free"


@pytest.mark.unit
def test_meets_minimum_is_importable_and_fail_closed_when_cold() -> None:
    # Force a cold snapshot rather than relying on module run order: other
    # test files warm/invalidate this same process-global registry.
    reg.invalidate()
    assert meets_minimum("free", "free") is False  # cold snapshot fails closed, no crash
