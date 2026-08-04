"""SSE streaming of per-user job events."""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

from redis.asyncio import Redis
from redis.asyncio.client import PubSub

from app.core.config import get_settings
from app.core.job_events import user_jobs_channel

logger = logging.getLogger(__name__)

_HEARTBEAT_S = 15.0
_POLL_TIMEOUT_S = 1.0


def encode_sse(event: str, data: str) -> str:
    """Format one SSE frame."""
    return f"event: {event}\ndata: {data}\n\n"


def encode_heartbeat() -> str:
    """SSE comment keep-alive for proxies."""
    return ": heartbeat\n\n"


def _job_frame(message: dict[str, Any] | None) -> str | None:
    if message is None or message.get("type") != "message":
        return None
    raw = message.get("data")
    if not isinstance(raw, str) or not raw:
        return None
    return encode_sse("job", raw)


async def _open_pubsub(user_id: UUID) -> tuple[Redis, PubSub, str]:
    client = Redis.from_url(get_settings().redis.url, decode_responses=True)
    pubsub = client.pubsub()
    channel = user_jobs_channel(user_id)
    await pubsub.subscribe(channel)
    return client, pubsub, channel


async def _close_pubsub(client: Redis, pubsub: PubSub, channel: str) -> None:
    try:
        await pubsub.unsubscribe(channel)
        # redis-asyncio PubSub.aclose is untyped in the stubs we ship with.
        await pubsub.aclose()  # type: ignore[no-untyped-call]
    finally:
        await client.aclose()


async def iter_user_job_events(user_id: UUID) -> AsyncIterator[str]:
    """Subscribe to the user's Redis channel and yield SSE frames."""
    client, pubsub, channel = await _open_pubsub(user_id)
    try:
        yield encode_sse("ready", "{}")
        last_hb = time.monotonic()
        while True:
            message = await pubsub.get_message(
                ignore_subscribe_messages=True,
                timeout=_POLL_TIMEOUT_S,
            )
            frame = _job_frame(message)
            if frame is not None:
                yield frame
            if time.monotonic() - last_hb >= _HEARTBEAT_S:
                yield encode_heartbeat()
                last_hb = time.monotonic()
    finally:
        await _close_pubsub(client, pubsub, channel)
