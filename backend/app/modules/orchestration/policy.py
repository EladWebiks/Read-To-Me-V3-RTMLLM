"""Per-tier policy resolution: specificity-wins over effective settings.

Chain (spec §3.2): tier row field if NOT NULL, else the effective runtime
setting. The Settings instance handed in must already be runtime-config
effective (the chat path builds services via `get_effective_settings`), so
the runtime-override and env-default layers are pre-collapsed here.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.modules.orchestration.models import MembershipPolicy
from app.modules.orchestration.repository import MembershipPolicyRepository
from app.modules.orchestration.schemas import MembershipPolicyPatch
from app.modules.users.membership import Membership
from app.modules.users.schemas import UserRead

logger = logging.getLogger(__name__)

# Per-turn caps. Names match BOTH LlmRuntimeSettings fields and
# MembershipPolicy columns, so one list drives the whole chain.
_PER_TURN_FIELDS = (
    "max_tool_iters",
    "max_external_calls",
    "max_turn_tokens_in",
    "max_turn_tokens_out",
    "max_turn_cost_usd",
    "run_deadline_seconds",
    "max_hitl_rounds",
)


@dataclass(frozen=True, slots=True)
class ResolvedPolicy:
    """Frozen per-turn policy for one user, resolved once at turn start.

    Per-turn caps only. Monthly/standing quotas resolve through the quotas
    module (Part B) — deliberately NOT carried here.
    """

    membership: str
    is_admin: bool
    max_tool_iters: int
    max_external_calls: int
    max_turn_tokens_in: int
    max_turn_tokens_out: int
    max_turn_cost_usd: float
    run_deadline_seconds: int
    max_hitl_rounds: int
    tier_overridden: tuple[str, ...]


class PolicyService:
    """Resolves and administers per-tier AI policies."""

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._repo = MembershipPolicyRepository(session)
        self._settings = settings

    async def resolve(self, user: UserRead) -> ResolvedPolicy:
        """Frozen policy for this user's tier. Missing row = inherit all."""
        row = await self._repo.get_by_membership(user.membership.value)
        if row is None:
            logger.warning(
                "no membership_policies row; inheriting all defaults",
                extra={"membership": user.membership.value},
            )
        caps, overridden = self._per_turn_caps(row)
        policy = ResolvedPolicy(
            membership=user.membership.value,
            is_admin=user.is_admin,
            tier_overridden=tuple(overridden),
            **caps,
        )
        # Policy values are not secrets — log freely (spec §4.3).
        logger.info(
            "tier policy resolved",
            extra={
                "membership": policy.membership,
                "tier_overridden": overridden,
                **caps,
            },
        )
        return policy

    async def list_policies(self) -> list[MembershipPolicy]:
        """All tier rows, ordered by membership."""
        return await self._repo.list_all()

    def inherited_defaults(self) -> dict[str, float | int]:
        """Current effective per-turn values (what NULL inherits right now)."""
        runtime = self._settings.llm_runtime
        return {field: getattr(runtime, field) for field in _PER_TURN_FIELDS}

    async def patch_policy(
        self,
        membership: Membership,
        patch: MembershipPolicyPatch,
        *,
        actor_id: UUID,
    ) -> MembershipPolicy:
        """Apply supplied fields (explicit null clears). Self-heals a missing row."""
        row = await self._repo.get_by_membership(membership.value)
        if row is None:
            row = MembershipPolicy(membership=membership.value)
            self._repo.add(row)
        changes = patch.model_dump(exclude_unset=True)
        for field, value in changes.items():
            setattr(row, field, value)
        saved = await self._repo.save(row)
        logger.info(
            "membership policy updated",
            extra={
                "membership": membership.value,
                "actor": str(actor_id),
                "changes": changes,
            },
        )
        return saved

    def _per_turn_caps(self, row: MembershipPolicy | None) -> tuple[dict[str, Any], list[str]]:
        """Collapse tier row over effective runtime settings. NULL = inherit."""
        runtime = self._settings.llm_runtime
        caps: dict[str, Any] = {}
        overridden: list[str] = []
        for field in _PER_TURN_FIELDS:
            tier_value = getattr(row, field) if row is not None else None
            if tier_value is None:
                caps[field] = getattr(runtime, field)
            else:
                caps[field] = tier_value
                overridden.append(field)
        return caps, overridden
