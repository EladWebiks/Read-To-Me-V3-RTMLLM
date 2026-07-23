"""Auth request/response schemas."""

from pydantic import BaseModel, Field

from app.modules.users.schemas import UserRead


class LoginRequest(BaseModel):
    """Login credentials."""

    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class LoginResponse(BaseModel):
    """Successful login payload."""

    user: UserRead


class MeResponse(BaseModel):
    """Current authenticated user."""

    user: UserRead
