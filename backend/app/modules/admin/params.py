"""Reusable admin query-parameter dependency groups."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import Query


class PageParams:
    """limit/offset pagination inputs shared by every admin list route."""

    def __init__(
        self,
        limit: Annotated[int, Query(ge=1, le=200)] = 50,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> None:
        self.limit = limit
        self.offset = offset


class PeriodParams:
    """Required [from, to) date range for usage aggregates."""

    def __init__(
        self,
        period_start: Annotated[datetime, Query(alias="from")],
        period_end: Annotated[datetime, Query(alias="to")],
    ) -> None:
        self.period_start = period_start
        self.period_end = period_end
