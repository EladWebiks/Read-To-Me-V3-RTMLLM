"""Auth request/response schemas."""

from pydantic import BaseModel

from app.modules.users.schemas import UserRead


class MeResponse(BaseModel):
    """Current authenticated user."""

    user: UserRead
    membership_label: str  # admin-authored display label for user.membership
