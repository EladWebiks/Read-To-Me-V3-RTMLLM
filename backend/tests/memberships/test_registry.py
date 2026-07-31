"""Membership registry snapshot: TTL, invalidate, rank lookup (unit)."""

from __future__ import annotations

import pytest
from app.modules.users import membership_registry as reg
from app.modules.users.membership import meets_minimum
from app.modules.users.membership_registry import TierSpec


@pytest.fixture(autouse=True)
def _clean_registry():
    reg.invalidate()
    yield
    reg.invalidate()


def _tier(slug: str, rank: int, *, active: bool = True, default: bool = False) -> TierSpec:
    return TierSpec(
        slug=slug,
        label=slug.title(),
        description=None,
        price_label=None,
        rank=rank,
        is_active=active,
        is_default=default,
    )


@pytest.mark.unit
def test_cold_snapshot_is_empty() -> None:
    assert reg.current_snapshot() == ()


@pytest.mark.unit
def test_put_then_read_and_invalidate() -> None:
    reg.put_snapshot([_tier("free", 0, default=True), _tier("premium", 1)])
    assert [t.slug for t in reg.current_snapshot()] == ["free", "premium"]
    reg.invalidate()
    assert reg.current_snapshot() == ()


@pytest.mark.unit
def test_rank_of_unknown_is_none() -> None:
    reg.put_snapshot([_tier("free", 0, default=True)])
    assert reg.rank_of("free") == 0
    assert reg.rank_of("nope") is None


@pytest.mark.unit
def test_meets_minimum_fail_closed() -> None:
    reg.put_snapshot([_tier("free", 0, default=True), _tier("premium", 1)])
    assert meets_minimum("premium", "free") is True
    assert meets_minimum("free", "premium") is False
    assert meets_minimum("premium", "premium") is True
    assert meets_minimum("garbage", "free") is True  # unknown actual ranks 0
    assert meets_minimum("garbage", "premium") is False
    assert meets_minimum("free", "unknown-minimum") is False  # fail-closed


@pytest.mark.unit
def test_meets_minimum_cold_snapshot_fails_closed() -> None:
    assert meets_minimum("free", "free") is False
