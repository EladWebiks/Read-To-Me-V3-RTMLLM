"""User API / service schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    """Input for creating a user."""

    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=8, max_length=128)
    email: EmailStr | None = None
    role: str = "admin"


class UserRead(BaseModel):
    """Public user representation (never includes password)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    email: str | None
    role: str
    created_at: datetime
