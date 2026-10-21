"""Admin user list query (filters + sort + page)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Literal

from fastapi import Depends, Query

AdminUserStatus = Literal["all", "active", "deleted"]
AdminUserSort = Literal["created_desc", "created_asc", "username_asc", "username_desc"]
AdminFlagFilter = Literal["any", "admin", "user"]


@dataclass(frozen=True, slots=True)
class AdminUserListQuery:
    """Filters for backoffice user listing."""

    limit: int
    offset: int
    q: str | None
    membership: str | None
    status: AdminUserStatus
    admin: AdminFlagFilter
    sort: AdminUserSort


def _parse_admin_user_list(  # noqa: PLR0913 — FastAPI Query injection surface
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    q: Annotated[str | None, Query(max_length=128)] = None,
    membership: Annotated[str | None, Query(max_length=32)] = None,
    status: Annotated[AdminUserStatus, Query()] = "all",
    admin: Annotated[AdminFlagFilter, Query()] = "any",
    sort: Annotated[AdminUserSort, Query()] = "created_desc",
) -> AdminUserListQuery:
    cleaned = q.strip() if q else None
    return AdminUserListQuery(
        limit=limit,
        offset=offset,
        q=cleaned or None,
        membership=membership or None,
        status=status,
        admin=admin,
        sort=sort,
    )


AdminUserListParams = Annotated[AdminUserListQuery, Depends(_parse_admin_user_list)]
