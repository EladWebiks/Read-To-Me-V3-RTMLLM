"""Unit tests for per-turn reply-language detection + LLM injection."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from app.modules.llm.models import ConversationMessage
from app.modules.orchestration.reply_language import (
    first_strong_lang,
    format_reply_language_block,
    reply_lang_from_history,
    reply_lang_from_text,
)
from app.modules.orchestration.service import _to_llm_messages


def _row(role: str, content: str) -> ConversationMessage:
    return ConversationMessage(
        conversation_id=uuid4(),
        role=role,
        content=content,
        created_at=datetime.now(UTC),
    )


@pytest.mark.unit
def test_first_strong_lang_hebrew_and_latin() -> None:
    assert first_strong_lang("איזה ספרים like Against the Gods?") == "he"
    assert first_strong_lang("*** Hello") == "en"
    assert first_strong_lang("مرحبا") == "ar"
    assert reply_lang_from_text("مرحبا") == "en"
    assert reply_lang_from_text("שלום") == "he"


@pytest.mark.unit
def test_reply_lang_from_history_uses_latest_user() -> None:
    history = [
        _row("user", "שלום"),
        _row("assistant", "היי"),
        _row("user", "i would like the 2nd book"),
    ]
    assert reply_lang_from_history(history) == "en"
    assert reply_lang_from_history(history[:-1]) == "he"


@pytest.mark.unit
def test_to_llm_messages_injects_reply_language() -> None:
    history = [
        _row("user", "התחרטתי"),
        _row("assistant", "בסדר"),
        _row("user", "i would like the 2nd book"),
    ]
    contents = [m.content for m in _to_llm_messages(history)]
    blocks = [c for c in contents if c.startswith("REPLY_LANGUAGE")]
    assert len(blocks) == 1
    assert "Reply in English" in blocks[0]
    assert "overrides earlier" in blocks[0]


@pytest.mark.unit
def test_hebrew_reply_language_block() -> None:
    block = format_reply_language_block("he")
    assert "Modern Hebrew" in block
    assert "niqqud" in block.lower() or "nikud" in block.lower()
    assert "NO" in block or "without" in block.lower() or "no marks" in block.lower()
    assert "END_REPLY_LANGUAGE" in block
