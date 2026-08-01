"""Budget unit tests."""

from __future__ import annotations

import pytest
from app.modules.llm.types import Usage
from app.modules.orchestration.budget import RunBudget
from app.modules.orchestration.exceptions import BudgetExceededError

from tests.factories import make_settings


@pytest.mark.unit
def test_budget_iters_exceeded() -> None:
    budget = RunBudget.from_settings(make_settings(llm_max_tool_iters=1))
    budget.begin_iter()
    with pytest.raises(BudgetExceededError, match="iterations"):
        budget.begin_iter()


@pytest.mark.unit
def test_budget_tokens_exceeded() -> None:
    budget = RunBudget.from_settings(
        make_settings(llm_max_turn_tokens_in=5, llm_max_turn_tokens_out=5)
    )
    with pytest.raises(BudgetExceededError, match="token"):
        budget.add_usage(Usage(10, 1))


@pytest.mark.unit
def test_final_usage_overage_is_recorded_without_raising() -> None:
    budget = RunBudget.from_settings(make_settings(llm_max_turn_tokens_in=5))

    budget.add_usage(Usage(10, 1), enforce_limits=False)

    assert budget.tokens_in == 10
