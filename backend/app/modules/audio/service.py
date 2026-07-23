"""Audio / TTS business logic."""

from __future__ import annotations

from typing import cast

from app.modules.audio.exceptions import (
    SynthesisError,
    TextTooLongError,
    UnknownProviderError,
)
from app.modules.audio.providers import default_voice, get_provider, list_all_voices
from app.modules.audio.schemas import ProviderName, SynthesizeRequest, VoiceRead

MAX_SYNTH_CHARS = 4000


class AudioService:
    """Owns TTS voice listing and synthesis."""

    async def list_voices(self) -> list[VoiceRead]:
        """List voices across providers."""
        voices = await list_all_voices()
        result: list[VoiceRead] = []
        for voice in voices:
            if voice.provider not in {"edge", "sapi"}:
                continue
            result.append(
                VoiceRead(
                    provider=cast(ProviderName, voice.provider),
                    id=voice.id,
                    name=voice.name,
                    locale=voice.locale,
                )
            )
        return result

    async def synthesize(self, body: SynthesizeRequest) -> bytes:
        """Synthesize text to MP3 bytes."""
        if len(body.text) > MAX_SYNTH_CHARS:
            raise TextTooLongError(str(len(body.text)))
        try:
            provider = get_provider(body.provider)
        except KeyError as exc:
            raise UnknownProviderError(body.provider) from exc
        voice = body.voice or default_voice(body.provider)
        try:
            return await provider.synthesize(body.text, voice, body.rate)
        except Exception as exc:
            raise SynthesisError(str(exc)) from exc
