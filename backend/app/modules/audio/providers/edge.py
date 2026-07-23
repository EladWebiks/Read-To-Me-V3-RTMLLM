"""Microsoft Edge neural TTS via edge-tts."""

from __future__ import annotations

import edge_tts

from app.modules.audio.providers.base import VoiceInfo

DEFAULT_EDGE_VOICE = "en-US-AriaNeural"


class EdgeTtsProvider:
    """Portable cloud Edge TTS (works in Linux containers)."""

    @property
    def name(self) -> str:
        return "edge"

    async def list_voices(self) -> list[VoiceInfo]:
        voices = await edge_tts.list_voices()
        result: list[VoiceInfo] = []
        for item in voices:
            locale = str(item.get("Locale", ""))
            if not locale.startswith("en-US"):
                continue
            short = str(item.get("ShortName", ""))
            if not short:
                continue
            result.append(
                VoiceInfo(
                    provider=self.name,
                    id=short,
                    name=str(item.get("FriendlyName") or short),
                    locale=locale,
                )
            )
        return result

    async def synthesize(self, text: str, voice: str, rate: float) -> bytes:
        rate_str = _edge_rate(rate)
        communicate = edge_tts.Communicate(text, voice=voice, rate=rate_str)
        chunks: list[bytes] = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                chunks.append(chunk["data"])
        return b"".join(chunks)


def _edge_rate(rate: float) -> str:
    clamped = max(0.5, min(2.0, rate))
    percent = round((clamped - 1.0) * 100)
    if percent >= 0:
        return f"+{percent}%"
    return f"{percent}%"
