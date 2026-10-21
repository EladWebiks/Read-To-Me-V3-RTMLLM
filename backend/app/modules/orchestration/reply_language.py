"""Detect reply language from the latest user message (first strong script)."""

from __future__ import annotations

import unicodedata
from collections.abc import Sequence
from typing import Literal, Protocol

ReplyLang = Literal["en", "he"]


class _HistoryRow(Protocol):
    role: str
    content: str


def first_strong_lang(text: str) -> ReplyLang | Literal["ar"] | None:
    """Skip marks/numbers/punctuation; return first alphabetic letter's script."""
    for char in text:
        if not char.isalpha():
            continue
        name = unicodedata.name(char, "")
        if name.startswith("HEBREW"):
            return "he"
        if name.startswith("ARABIC"):
            return "ar"
        if name.startswith("LATIN"):
            return "en"
    return None


def reply_lang_from_text(text: str) -> ReplyLang:
    return "he" if first_strong_lang(text) == "he" else "en"


def reply_lang_from_history(history: Sequence[_HistoryRow]) -> ReplyLang:
    """Nearest preceding user message; English if none / non-Hebrew."""
    for row in reversed(history):
        if row.role == "user" and row.content.strip():
            return reply_lang_from_text(row.content)
    return "en"


def format_reply_language_block(lang: ReplyLang) -> str:
    """Authoritative per-turn language instruction for the LLM."""
    if lang == "he":
        body = (
            "Reply in everyday Modern Hebrew (like a native chat app): consonants "
            "only — NO niqqud/nikud/vowel points (no marks in U+0591-U+05C7). "
            "Never use Arabic letters or lookalike scripts. Keep book titles and "
            "tool values exactly as provided (do not translate titles)."
        )
    else:
        body = (
            "Reply in English. Keep book titles and tool values exactly as "
            "provided (do not translate titles)."
        )
    return (
        "REPLY_LANGUAGE (authoritative for this turn — overrides earlier "
        f"conversation language):\n{body}\nEND_REPLY_LANGUAGE"
    )
