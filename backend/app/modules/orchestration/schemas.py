"""Pydantic DTOs for the membership-policies admin API."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class MembershipPolicyRead(BaseModel):
    """One tier row of per-turn cap overrides. None = inherit."""

    model_config = ConfigDict(from_attributes=True)

    membership: str
    max_tool_iters: int | None
    max_external_calls: int | None
    max_turn_tokens_in: int | None
    max_turn_tokens_out: int | None
    max_turn_cost_usd: float | None
    run_deadline_seconds: int | None
    max_hitl_rounds: int | None
    updated_at: datetime


class MembershipPolicyPatch(BaseModel):
    """PATCH body — omitted fields unchanged; explicit null = inherit.

    Bounds mirror LlmRuntimeSettings so a tier override can never carry a
    value the settings layer itself would reject.
    """

    max_tool_iters: Annotated[int, Field(ge=1)] | None = None
    max_external_calls: Annotated[int, Field(ge=0)] | None = None
    max_turn_tokens_in: Annotated[int, Field(ge=1)] | None = None
    max_turn_tokens_out: Annotated[int, Field(ge=1)] | None = None
    max_turn_cost_usd: Annotated[float, Field(gt=0)] | None = None
    run_deadline_seconds: Annotated[int, Field(ge=1)] | None = None
    max_hitl_rounds: Annotated[int, Field(ge=0)] | None = None


class MembershipPoliciesResponse(BaseModel):
    """GET payload: all tier rows + current inherited per-turn defaults."""

    policies: list[MembershipPolicyRead]
    inherited: dict[str, float | int]
