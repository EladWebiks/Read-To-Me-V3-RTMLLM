"""Gemini thought_signature round-trip for tool loops."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from app.modules.llm.providers.gemini_provider import (
    _function_call_part,
    _message_to_content,
    _parse_tool_calls,
)
from app.modules.llm.types import Message, Role, ToolCall


@pytest.mark.unit
def test_parse_tool_calls_keeps_thought_signature() -> None:
    raw = SimpleNamespace(
        candidates=[
            SimpleNamespace(
                content=SimpleNamespace(
                    parts=[
                        SimpleNamespace(
                            function_call=SimpleNamespace(
                                name="search_user_books",
                                args={"query": "cultivation"},
                            ),
                            thought_signature=b"sig-bytes",
                        )
                    ]
                )
            )
        ]
    )
    calls = _parse_tool_calls(raw)
    assert len(calls) == 1
    assert calls[0].name == "search_user_books"
    assert calls[0].thought_signature == b"sig-bytes"


@pytest.mark.unit
def test_function_call_part_echoes_thought_signature() -> None:
    from google.genai import types

    call = ToolCall(
        id="c1",
        name="search_user_books",
        arguments={"query": "x"},
        thought_signature=b"sig-bytes",
    )
    part = _function_call_part(types, call)
    assert part.function_call is not None
    assert part.function_call.name == "search_user_books"
    assert part.thought_signature == b"sig-bytes"


@pytest.mark.unit
def test_assistant_tool_message_preserves_signature_in_contents() -> None:
    from google.genai import types

    msg = Message(
        role=Role.ASSISTANT,
        content="",
        tool_calls=(
            ToolCall(
                id="c1",
                name="search_user_books",
                arguments={},
                thought_signature=b"sig-bytes",
            ),
        ),
    )
    content = _message_to_content(msg, types)
    assert content.parts[0].thought_signature == b"sig-bytes"
