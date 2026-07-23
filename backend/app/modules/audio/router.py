"""Audio HTTP routes."""

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from app.core.deps import get_current_user
from app.modules.audio.schemas import SynthesizeRequest, VoiceRead
from app.modules.audio.service import AudioService
from app.modules.users.schemas import UserRead

router = APIRouter(prefix="/audio", tags=["audio"])


def _audio() -> AudioService:
    return AudioService()


@router.get("/voices", response_model=list[VoiceRead])
async def list_voices(
    _user: Annotated[UserRead, Depends(get_current_user)],
    service: Annotated[AudioService, Depends(_audio)],
) -> list[VoiceRead]:
    """List TTS voices for Edge and SAPI."""
    return await service.list_voices()


@router.post("/synthesize")
async def synthesize(
    body: SynthesizeRequest,
    _user: Annotated[UserRead, Depends(get_current_user)],
    service: Annotated[AudioService, Depends(_audio)],
) -> Response:
    """Synthesize text to an MP3 response body."""
    audio = await service.synthesize(body)
    return Response(content=audio, media_type="audio/mpeg")
