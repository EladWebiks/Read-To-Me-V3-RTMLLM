"""ensure_ready: catalog emptiness degrades like llm-disabled."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from app.modules.llm import catalog
from app.modules.llm.exceptions import LlmDisabledError, NoCandidateModelError
from app.modules.llm.service import LlmService

from tests.factories import make_settings


@pytest.mark.unit
async def test_ensure_ready_passes_with_enabled_catalog() -> None:
    service = LlmService(AsyncMock(), make_settings(llm_enabled=True, gemini_api_key="k"))
    await service.ensure_ready()  # autouse fixture pre-warmed the snapshot


@pytest.mark.unit
async def test_ensure_ready_raises_when_llm_disabled() -> None:
    service = LlmService(AsyncMock(), make_settings(llm_enabled=False))
    with pytest.raises(LlmDisabledError):
        await service.ensure_ready()


@pytest.mark.unit
async def test_ensure_ready_raises_when_all_models_disabled() -> None:
    catalog.put_snapshot(())
    service = LlmService(AsyncMock(), make_settings(llm_enabled=True, gemini_api_key="k"))
    with pytest.raises(NoCandidateModelError):
        await service.ensure_ready()
