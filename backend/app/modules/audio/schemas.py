"""Audio request/response schemas."""

from typing import Literal

from pydantic import BaseModel, Field

ProviderName = Literal["edge", "sapi"]


class VoiceRead(BaseModel):
    """Selectable TTS voice."""

    provider: ProviderName
    id: str
    name: str
    locale: str | None = None


class SynthesizeRequest(BaseModel):
    """Synthesize one text segment to MP3."""

    text: str = Field(min_length=1, max_length=4000)
    provider: ProviderName = "edge"
    voice: str | None = None
    rate: float = Field(default=1.0, ge=0.5, le=2.0)
