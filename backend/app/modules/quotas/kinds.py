"""Quota kind registry — the enum lives in code; limits live in membership_quotas.

Adding a dimension = one enum value + one KIND_REGISTRY entry (+ a meter and
an enforcement call in the owning domain module). No migration, no API/UI
change — the admin surface is registry-driven.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal


class QuotaKind(StrEnum):
    """A meterable usage dimension."""

    LLM_TOKENS = "llm_tokens"
    LLM_COST_USD = "llm_cost_usd"
    AUDIO_CHAPTERS = "audio_chapters"
    STORAGE_BYTES = "storage_bytes"
    SCRAPE_CHAPTERS = "scrape_chapters"
    EPUB_IMPORTS = "epub_imports"


@dataclass(frozen=True, slots=True)
class KindMeta:
    """Display + windowing metadata; 'standing' kinds compare a level, no reset."""

    label: str
    unit: str
    window: Literal["month", "standing"]


KIND_REGISTRY: dict[QuotaKind, KindMeta] = {
    QuotaKind.LLM_TOKENS: KindMeta("AI tokens", "tokens", "month"),
    QuotaKind.LLM_COST_USD: KindMeta("AI spend", "USD", "month"),
    QuotaKind.AUDIO_CHAPTERS: KindMeta("Audio chapters", "chapters", "month"),
    QuotaKind.STORAGE_BYTES: KindMeta("Download storage", "bytes", "standing"),
    QuotaKind.SCRAPE_CHAPTERS: KindMeta("Scraped chapters", "chapters", "month"),
    QuotaKind.EPUB_IMPORTS: KindMeta("EPUB imports", "imports", "month"),
}
