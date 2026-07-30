"""Google OAuth settings exist and default to unset."""

import pytest

from tests.factories import make_settings


@pytest.mark.unit
def test_google_settings_default_to_none(monkeypatch: pytest.MonkeyPatch) -> None:
    # The developer's real `.env` may export these; the defaults are what's
    # under test, so clear them first.
    for var in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REDIRECT_URI"):
        monkeypatch.delenv(var, raising=False)
    settings = make_settings()
    assert settings.google_client_id is None
    assert settings.google_client_secret is None
    assert settings.google_redirect_uri is None
