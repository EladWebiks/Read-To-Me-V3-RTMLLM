"""Membership ordering helpers over the runtime tier registry.

Tiers live in the `memberships` table (users module) and are served from
membership_registry's cached snapshot. Ordering lives ONLY in each tier's
`rank` — never as integers scattered through code.
"""

from __future__ import annotations

from app.modules.users.membership_registry import rank_of

DEFAULT_SLUG = "free"


def meets_minimum(actual: str, minimum: str) -> bool:
    """True when `actual` ranks at least `minimum`; fail-closed on unknowns."""
    required = rank_of(minimum)
    if required is None:
        return False
    actual_rank = rank_of(actual)
    return (actual_rank if actual_rank is not None else 0) >= required
