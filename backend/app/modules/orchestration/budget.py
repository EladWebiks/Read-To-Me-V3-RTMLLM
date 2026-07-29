"""Per-run budgets for the tool loop."""

from __future__ import annotations

import time
from dataclasses import dataclass

from app.core.config import Settings
from app.modules.llm.types import Usage
from app.modules.orchestration.exceptions import BudgetExceededError


@dataclass
class RunBudget:
    """Mutable counters for one orchestration run."""

    max_iters: int
    max_external_calls: int
    max_tokens_in: int
    max_tokens_out: int
    max_cost_usd: float
    deadline_mono: float
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    external_calls: int = 0
    iters: int = 0

    @classmethod
    def from_settings(cls, settings: Settings) -> RunBudget:
        """Build budget from app settings."""
        return cls(
            max_iters=settings.llm_max_tool_iters,
            max_external_calls=settings.llm_max_external_calls,
            max_tokens_in=settings.llm_max_turn_tokens_in,
            max_tokens_out=settings.llm_max_turn_tokens_out,
            max_cost_usd=settings.llm_max_turn_cost_usd,
            deadline_mono=time.monotonic() + settings.llm_run_deadline_seconds,
        )

    def begin_iter(self) -> None:
        """Count one LLM round and enforce caps."""
        self.iters += 1
        if self.iters > self.max_iters:
            raise BudgetExceededError("max tool iterations exceeded")
        self.check_walltime()

    def check_walltime(self) -> None:
        """Raise if the wall-clock deadline passed."""
        if time.monotonic() > self.deadline_mono:
            raise BudgetExceededError("run deadline exceeded")

    def add_usage(
        self,
        usage: Usage,
        *,
        cost_usd: float = 0.0,
        enforce_limits: bool = True,
    ) -> None:
        """Accumulate usage; final answers may record overage without being discarded."""
        self.tokens_in += usage.tokens_in
        self.tokens_out += usage.tokens_out
        self.cost_usd += cost_usd
        if not enforce_limits:
            return
        if self.tokens_in > self.max_tokens_in or self.tokens_out > self.max_tokens_out:
            raise BudgetExceededError(
                "token budget exceeded "
                f"(in={self.tokens_in}/{self.max_tokens_in}, "
                f"out={self.tokens_out}/{self.max_tokens_out})"
            )
        if self.cost_usd > self.max_cost_usd:
            raise BudgetExceededError(
                f"cost budget exceeded ({self.cost_usd:.4f}/{self.max_cost_usd})"
            )

    def add_external(self) -> None:
        """Count one external tool call."""
        self.external_calls += 1
        if self.external_calls > self.max_external_calls:
            raise BudgetExceededError("external call budget exceeded")

    def summary(self) -> dict[str, float | int]:
        """Payload for the done event."""
        return {
            "iters": self.iters,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "cost_usd": round(self.cost_usd, 6),
            "external_calls": self.external_calls,
        }
