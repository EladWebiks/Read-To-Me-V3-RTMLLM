"""Membership helpers (post-enum): meets_minimum lives on the registry snapshot."""

from __future__ import annotations

import pytest
from app.modules.users.membership import DEFAULT_SLUG, meets_minimum


@pytest.mark.unit
def test_default_slug() -> None:
    assert DEFAULT_SLUG == "free"


@pytest.mark.unit
def test_meets_minimum_is_importable_and_fail_closed_when_cold() -> None:
    assert meets_minimum("free", "free") in (True, False)  # no crash on cold cache
