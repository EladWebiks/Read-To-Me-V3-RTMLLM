"""Unit tests for membership tiers and rank ordering."""

import pytest
from app.modules.users import membership as membership_module
from app.modules.users.membership import MEMBERSHIP_RANK, Membership, meets_minimum


@pytest.mark.unit
def test_membership_is_string_backed() -> None:
    # Bound through `str` so mypy compares as strings, not enum literals.
    free: str = Membership.FREE
    assert free == "free"
    assert isinstance(Membership.FREE, str)


@pytest.mark.unit
def test_rank_map_covers_every_tier() -> None:
    assert set(MEMBERSHIP_RANK) == {member.value for member in Membership}
    assert MEMBERSHIP_RANK[Membership.FREE] == 0


@pytest.mark.unit
def test_free_meets_free() -> None:
    assert meets_minimum(Membership.FREE, Membership.FREE) is True


@pytest.mark.unit
def test_ordering_with_future_tier(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(membership_module, "MEMBERSHIP_RANK", {"free": 0, "premium": 1})
    assert meets_minimum("free", "premium") is False
    assert meets_minimum("premium", "free") is True
    assert meets_minimum("premium", "premium") is True


@pytest.mark.unit
def test_unknown_actual_ranks_lowest(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(membership_module, "MEMBERSHIP_RANK", {"free": 0, "premium": 1})
    assert meets_minimum("garbage", "free") is True
    assert meets_minimum("garbage", "premium") is False


@pytest.mark.unit
def test_unknown_minimum_fails_closed() -> None:
    assert meets_minimum(Membership.FREE, "premium") is False
