"""Orchestration domain errors."""

from __future__ import annotations


class OrchestrationError(Exception):
    """Base orchestration error."""


class BudgetExceededError(OrchestrationError):
    """A run budget (iters/tokens/cost/time) was exceeded."""
