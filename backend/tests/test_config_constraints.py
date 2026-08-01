"""Runtime-tunable fields reject out-of-range values (env AND future overrides)."""

import pytest
from pydantic import ValidationError

from tests.factories import make_settings


@pytest.mark.unit
def test_llm_runtime_bounds() -> None:
    with pytest.raises(ValidationError):
        make_settings(llm_max_tool_iters=0)
    with pytest.raises(ValidationError):
        make_settings(llm_max_turn_cost_usd=0)
    with pytest.raises(ValidationError):
        make_settings(llm_max_external_calls=-1)
    assert make_settings(llm_max_hitl_rounds=0).llm_runtime.max_hitl_rounds == 0


@pytest.mark.unit
def test_assistant_mode_is_constrained() -> None:
    with pytest.raises(ValidationError):
        make_settings(llm_assistant_mode="freeform")
    settings = make_settings(llm_assistant_mode="external_allowed")
    assert settings.llm_runtime.assistant_mode == "external_allowed"


@pytest.mark.unit
def test_scrape_and_storage_bounds() -> None:
    with pytest.raises(ValidationError):
        make_settings(scrape_timeout_seconds=0)
    with pytest.raises(ValidationError):
        make_settings(scrape_max_bytes=100)
    with pytest.raises(ValidationError):
        make_settings(scrape_delay_seconds=-0.1)
    with pytest.raises(ValidationError):
        make_settings(download_job_ttl_hours=0)
    with pytest.raises(ValidationError):
        make_settings(signed_url_expires_seconds=30)
