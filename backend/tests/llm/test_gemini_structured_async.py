"""Regression: Gemini structured output must use instructor's async client."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from app.modules.llm.providers.gemini_provider import GeminiProvider, GeminiProviderConfig
from app.modules.llm.types import Message, Role, StructuredOutputRequest
from pydantic import BaseModel, Field


class _Out(BaseModel):
    summary: str = Field(min_length=1)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_structured_uses_async_instructor(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    class _FakeInstructor:
        def __init__(self) -> None:
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

        async def _create(self, **_kwargs: Any) -> _Out:
            return _Out(summary="A short no-spoiler overview of the opening chapters.")

    def _from_genai(*_args: Any, **kwargs: Any) -> _FakeInstructor:
        captured["use_async"] = kwargs.get("use_async")
        return _FakeInstructor()

    import instructor

    monkeypatch.setattr(instructor, "from_genai", _from_genai)

    provider = GeminiProvider(GeminiProviderConfig(api_key="test-key", model_name="gemini-test"))
    out = await provider.generate_structured_output(
        StructuredOutputRequest(
            messages=[Message(role=Role.USER, content="summarize")],
            response_model=_Out,
        )
    )
    assert captured["use_async"] is True
    assert out.summary.startswith("A short")
