"""TTS provider protocol and voice DTO."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class VoiceInfo:
    """One selectable TTS voice."""

    provider: str
    id: str
    name: str
    locale: str | None = None


class TtsProvider(Protocol):
    """Synthesize speech to MP3 bytes."""

    @property
    def name(self) -> str:
        """Provider id: edge or sapi."""

    async def list_voices(self) -> list[VoiceInfo]:
        """List available voices for this provider."""

    async def synthesize(self, text: str, voice: str, rate: float) -> bytes:
        """Return MP3 bytes for text."""
