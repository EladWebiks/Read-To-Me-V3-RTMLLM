"""Auth HTTP routes: login, logout, me."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.deps import get_current_user, get_db
from app.modules.auth.schemas import LoginRequest, LoginResponse, MeResponse
from app.modules.auth.service import AuthService
from app.modules.users.schemas import UserRead

router = APIRouter(prefix="/auth", tags=["auth"])

COOKIE_NAME = "rtm_token"


def _auth_service(
    session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthService:
    return AuthService(session, settings)


def _set_auth_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=settings.jwt_expire_days * 24 * 60 * 60,
        path="/",
    )


@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    response: Response,
    service: Annotated[AuthService, Depends(_auth_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> LoginResponse:
    """Authenticate and set the session cookie."""
    user, token = await service.login(body.username, body.password)
    _set_auth_cookie(response, token, settings)
    return LoginResponse(user=user)


@router.post("/logout", status_code=204)
async def logout(response: Response) -> None:
    """Clear the session cookie."""
    response.delete_cookie(key=COOKIE_NAME, path="/")


@router.get("/me", response_model=MeResponse)
async def me(
    current_user: Annotated[UserRead, Depends(get_current_user)],
) -> MeResponse:
    """Return the currently authenticated user."""
    return MeResponse(user=current_user)
