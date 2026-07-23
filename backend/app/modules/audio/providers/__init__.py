"""Resolve TTS providers by name."""

from __future__ import annotations

from app.modules.audio.providers.base import TtsProvider, VoiceInfo
from app.modules.audio.providers.edge import DEFAULT_EDGE_VOICE, EdgeTtsProvider
from app.modules.audio.providers.sapi import SapiTtsProvider
from app.modules.audio.providers.sapi_local import DEFAULT_SAPI_VOICE

_PROVIDERS: dict[str, TtsProvider] = {
    "edge": EdgeTtsProvider(),
    "sapi": SapiTtsProvider(),
}


def get_provider(name: str) -> TtsProvider:
    """Return a provider or raise KeyError."""
    provider = _PROVIDERS.get(name)
    if provider is None:
        raise KeyError(name)
    return provider


def default_voice(provider: str) -> str:
    """Default voice id for a provider."""
    if provider == "sapi":
        return DEFAULT_SAPI_VOICE
    return DEFAULT_EDGE_VOICE


async def list_all_voices() -> list[VoiceInfo]:
    """Union of voices from all providers."""
    voices: list[VoiceInfo] = []
    for provider in _PROVIDERS.values():
        voices.extend(await provider.list_voices())
    return voices
