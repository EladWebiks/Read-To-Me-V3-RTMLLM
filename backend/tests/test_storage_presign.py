"""Unit tests for MinIO URL signing host selection."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from app.core import storage

from tests.factories import make_settings


@pytest.mark.unit
def test_presign_uses_public_endpoint_not_internal() -> None:
    storage.get_minio_client.cache_clear()
    storage.get_minio_presign_client.cache_clear()
    settings = make_settings(
        minio_endpoint="minio:9000",
        minio_public_endpoint="localhost:9000",
        minio_access_key="rtm",
        minio_secret_key="rtmsecret",
        minio_bucket="rtm",
        minio_secure=False,
    )
    fake = MagicMock()
    fake.presigned_get_object.return_value = "http://localhost:9000/rtm/key?X-Amz-Signature=abc"
    with (
        patch("app.core.storage.get_settings", return_value=settings),
        patch("app.core.storage.Minio", return_value=fake) as minio_ctor,
    ):
        client = storage.get_minio_presign_client()
        assert client is fake
        minio_ctor.assert_called_with(
            "localhost:9000",
            access_key="rtm",
            secret_key="rtmsecret",
            secure=False,
            region="us-east-1",
        )
    storage.get_minio_client.cache_clear()
    storage.get_minio_presign_client.cache_clear()
