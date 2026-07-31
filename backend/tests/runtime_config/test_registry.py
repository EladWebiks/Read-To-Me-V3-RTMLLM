"""The whitelist registry: coverage, exclusions, and typed validation."""

import pytest
from app.core.config import LlmRuntimeSettings, ScrapeSettings, Settings, UsageSettings
from app.modules.runtime_config.registry import TUNABLE_FIELDS, section_of
from pydantic import ValidationError

FORBIDDEN_PREFIXES = ("database.", "redis.", "auth.", "google.", "llm.", "app.")
# Sections registered wholesale; every other key must come from the pin below.
FULL_SECTION_PREFIXES = ("llm_runtime.", "usage.")
FORBIDDEN_KEYS = {
    "storage.endpoint",
    "storage.access_key",
    "storage.secret_key",
    "storage.bucket",
    "storage.secure",
    "storage.public_endpoint",
}


@pytest.mark.unit
def test_every_llm_runtime_field_is_tunable() -> None:
    expected = {f"llm_runtime.{name}" for name in LlmRuntimeSettings.model_fields}
    actual = {key for key in TUNABLE_FIELDS if key.startswith("llm_runtime.")}
    assert actual == expected  # a new LlmRuntimeSettings field auto-registers


@pytest.mark.unit
def test_every_usage_field_is_tunable() -> None:
    expected = {f"usage.{name}" for name in UsageSettings.model_fields}
    actual = {key for key in TUNABLE_FIELDS if key.startswith("usage.")}
    assert actual == expected  # a new UsageSettings field auto-registers


@pytest.mark.unit
def test_partial_sections_pin_exact_contents() -> None:
    non_llm = {key for key in TUNABLE_FIELDS if not key.startswith(FULL_SECTION_PREFIXES)}
    assert non_llm == {
        "scrape.timeout_seconds",
        "scrape.max_bytes",
        "scrape.delay_seconds",
        "storage.download_job_ttl_hours",
        "storage.signed_url_expires_seconds",
        "audio.sapi_proxy_enabled",
    }


@pytest.mark.unit
def test_registry_matches_the_pydantic_models() -> None:
    for field in TUNABLE_FIELDS.values():
        assert Settings.model_fields[field.section].annotation is field.group_cls
        assert field.field_name in field.group_cls.model_fields
        assert field.key == f"{field.section}.{field.field_name}"


@pytest.mark.unit
def test_infrastructure_and_secrets_are_never_tunable() -> None:
    for key in TUNABLE_FIELDS:
        assert not key.startswith(FORBIDDEN_PREFIXES), key
        assert key not in FORBIDDEN_KEYS, key


@pytest.mark.unit
def test_adapters_enforce_type_and_constraints() -> None:
    iters = TUNABLE_FIELDS["llm_runtime.max_tool_iters"].adapter
    assert iters.validate_python(4) == 4
    with pytest.raises(ValidationError):
        iters.validate_python("many")
    with pytest.raises(ValidationError):
        iters.validate_python(0)  # ge=1 from Task 2
    mode = TUNABLE_FIELDS["llm_runtime.assistant_mode"].adapter
    assert mode.validate_python("external_allowed") == "external_allowed"
    with pytest.raises(ValidationError):
        mode.validate_python("freeform")


@pytest.mark.unit
def test_section_of_resolves_tunable_groups_only() -> None:
    assert section_of(LlmRuntimeSettings) == "llm_runtime"
    assert section_of(ScrapeSettings) == "scrape"
    with pytest.raises(KeyError):
        section_of(Settings)
