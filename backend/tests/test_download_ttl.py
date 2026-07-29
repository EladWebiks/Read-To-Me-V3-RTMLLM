"""Unit tests for download job TTL helpers."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest


@pytest.mark.unit
def test_ttl_deadline_uses_configured_hours(monkeypatch: pytest.MonkeyPatch) -> None:
    """expires_at is now + DOWNLOAD_JOB_TTL_HOURS."""
    from app.modules.downloads import service as downloads_service

    settings = MagicMock()
    settings.download_job_ttl_hours = 24
    monkeypatch.setattr(downloads_service, "get_settings", lambda: settings)

    before = datetime.now(UTC)
    deadline = downloads_service._ttl_deadline()
    after = datetime.now(UTC)

    assert before + timedelta(hours=24) <= deadline <= after + timedelta(hours=24)
