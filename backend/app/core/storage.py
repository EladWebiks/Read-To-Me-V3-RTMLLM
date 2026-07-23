"""MinIO object storage helpers."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from functools import lru_cache
from io import BytesIO

from minio import Minio

from app.core.config import get_settings


@lru_cache
def get_minio_client() -> Minio:
    """Return a cached MinIO client for server-side put/get (internal endpoint)."""
    settings = get_settings()
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )


@lru_cache
def get_minio_presign_client() -> Minio:
    """Client whose endpoint matches the browser Host used for signed URLs.

    SigV4 binds the signature to the host. Signing against ``minio:9000`` and then
    rewriting the URL to ``localhost:9000`` causes SignatureDoesNotMatch in the browser.

    ``region`` is set so the SDK does not HTTP-probe the public host (unreachable from
    inside the compose network).
    """
    settings = get_settings()
    endpoint = settings.minio_public_endpoint or settings.minio_endpoint
    return Minio(
        endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
        region="us-east-1",
    )


async def put_bytes(key: str, data: bytes, content_type: str) -> None:
    """Upload bytes to the configured bucket."""
    settings = get_settings()
    client = get_minio_client()

    def _put() -> None:
        client.put_object(
            settings.minio_bucket,
            key,
            BytesIO(data),
            length=len(data),
            content_type=content_type,
        )

    await asyncio.to_thread(_put)


async def delete_prefix(prefix: str) -> None:
    """Delete all objects under a key prefix."""
    settings = get_settings()
    client = get_minio_client()

    def _delete() -> None:
        for obj in client.list_objects(
            settings.minio_bucket,
            prefix=prefix,
            recursive=True,
        ):
            if obj.object_name:
                client.remove_object(settings.minio_bucket, obj.object_name)

    await asyncio.to_thread(_delete)


async def presigned_get(key: str, expires_seconds: int = 3600) -> str:
    """Return a short-lived GET URL for an object (browser-reachable host)."""
    settings = get_settings()
    client = get_minio_presign_client()

    def _presign() -> str:
        return client.presigned_get_object(
            settings.minio_bucket,
            key,
            expires=timedelta(seconds=expires_seconds),
        )

    return await asyncio.to_thread(_presign)
