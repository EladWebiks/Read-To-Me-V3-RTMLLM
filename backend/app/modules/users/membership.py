"""Membership tiers and their in-code rank ordering.

Values are stored as strings in `users.membership` and map directly to
future Stripe product lookup keys. Ordering lives ONLY in MEMBERSHIP_RANK —
never as integers in the DB.
"""

from __future__ import annotations

from enum import StrEnum


class Membership(StrEnum):
    """Product tier. Extend here when a new tier ships."""

    FREE = "free"


MEMBERSHIP_RANK: dict[str, int] = {Membership.FREE: 0}


def meets_minimum(actual: str, minimum: str) -> bool:
    """True when `actual` ranks at least `minimum`; fail-closed on unknowns."""
    required = MEMBERSHIP_RANK.get(minimum)
    if required is None:
        return False
    return MEMBERSHIP_RANK.get(actual, 0) >= required
