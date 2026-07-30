"""Google OAuth settings exist and default to unset."""

import pytest
from app.core.config import Settings


@pytest.mark.unit
def test_google_settings_default_to_none() -> None:
    settings = Settings(_env_file=None)
    assert settings.google_client_id is None
    assert settings.google_client_secret is None
    assert settings.google_redirect_uri is None
