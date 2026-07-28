"""Model capability enum — callers request these, never model names."""

from __future__ import annotations

from enum import StrEnum


class ModelCapability(StrEnum):
    """What a model (or request) can do."""

    FAST_CHAT = "FAST_CHAT"
    TOOL_CALLING = "TOOL_CALLING"
    STRUCTURED_EXTRACTION = "STRUCTURED_EXTRACTION"
    LONG_CONTEXT_SUMMARIZATION = "LONG_CONTEXT_SUMMARIZATION"
    RERANKING = "RERANKING"
    EMBEDDING = "EMBEDDING"
    LOCAL_PRIVATE_INFERENCE = "LOCAL_PRIVATE_INFERENCE"
