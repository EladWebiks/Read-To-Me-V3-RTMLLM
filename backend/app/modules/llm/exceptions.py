"""LLM domain exceptions."""

from __future__ import annotations


class LlmError(Exception):
    """Base LLM error."""


class LlmDisabledError(LlmError):
    """LLM_ENABLED is false."""


class LlmConfigError(LlmError):
    """Missing key or invalid LLM configuration."""


class CapabilityNotSupportedError(LlmError):
    """Requested capability/method not supported by the model."""


class LlmProviderError(LlmError):
    """Upstream provider failure after retries."""


class LlmRateLimitError(LlmProviderError):
    """Provider rate limit / quota exhausted."""


class LlmTimeoutError(LlmProviderError):
    """Provider call timed out."""


class NoCandidateModelError(LlmError):
    """Router found no enabled model for the capability."""


class ConversationNotFoundError(LlmError):
    """Conversation missing or not owned by the caller."""
