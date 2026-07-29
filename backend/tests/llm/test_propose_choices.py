"""Unit tests for propose_choices clarify tool."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from app.modules.tools.base import Mode, ToolContext
from app.modules.tools.definitions.propose_choices import (
    ProposeChoicesInput,
    ProposeChoicesOutput,
    ProposeChoicesTool,
)
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.unit
@pytest.mark.asyncio
async def test_propose_choices_returns_options() -> None:
    tool = ProposeChoicesTool()
    ctx = ToolContext(
        user_id=uuid4(),
        conversation_id=uuid4(),
        run_id=uuid4(),
        mode=Mode.INTERNAL_ONLY,
        session=MagicMock(spec=AsyncSession),
    )
    out = await tool.execute(
        ProposeChoicesInput(prompt="Which one?", options=["Alpha", "Beta"]),
        ctx,
    )
    assert isinstance(out, ProposeChoicesOutput)
    assert out.prompt == "Which one?"
    assert out.options == ["Alpha", "Beta"]
