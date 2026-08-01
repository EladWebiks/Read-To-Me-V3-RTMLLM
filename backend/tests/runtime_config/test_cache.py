"""TTL cache semantics: warm hit, expiry, explicit invalidation."""

import pytest
from app.modules.runtime_config import cache


@pytest.fixture(autouse=True)
def _fresh() -> None:
    cache.invalidate()


@pytest.mark.unit
def test_cold_cache_returns_none() -> None:
    assert cache.get_cached() is None


@pytest.mark.unit
def test_put_then_get_returns_copy() -> None:
    cache.put({"llm_runtime.max_tool_iters": 4})
    first = cache.get_cached()
    assert first == {"llm_runtime.max_tool_iters": 4}
    assert first is not None
    first["llm_runtime.max_tool_iters"] = 999  # mutating the copy is harmless
    assert cache.get_cached() == {"llm_runtime.max_tool_iters": 4}


@pytest.mark.unit
def test_entries_expire_after_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = {"now": 100.0}
    monkeypatch.setattr(cache, "monotonic", lambda: clock["now"])
    cache.put({"scrape.delay_seconds": 0.5})
    clock["now"] = 100.0 + cache.CACHE_TTL_SECONDS - 0.01
    assert cache.get_cached() is not None
    clock["now"] = 100.0 + cache.CACHE_TTL_SECONDS + 0.01
    assert cache.get_cached() is None


@pytest.mark.unit
def test_invalidate_drops_immediately() -> None:
    cache.put({"scrape.delay_seconds": 0.5})
    cache.invalidate()
    assert cache.get_cached() is None
