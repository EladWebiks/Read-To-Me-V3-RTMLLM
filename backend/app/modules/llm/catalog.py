"""DB-backed effective model catalog: async snapshot refresh, sync reads.

Same per-process TTL pattern as modules/runtime_config/cache.py: writers
call invalidate() so the writing process sees changes immediately; other
processes (arq worker, other API workers) converge within the TTL. Sync
readers (ModelRouter.candidates) see the last loaded snapshot; LlmService
entry points await ensure_loaded() first, so a cold cache is only ever
observable as an empty catalog — which surfaces as NoCandidateModelError,
never a crash. Upgrade path if TTL lag ever matters: Redis pub/sub calling
invalidate(); this module is the single seam for that.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from time import monotonic
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.llm.capabilities import ModelCapability
from app.modules.llm.providers import has_adapter
from app.modules.llm.registry import ModelSpec
from app.modules.llm.repository import CatalogRow, LlmRepository

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 30.0

_state: dict[str, Any] = {"snapshot": None, "expires_at": 0.0}


def current_snapshot() -> tuple[ModelSpec, ...]:
    """Sync view of the effective catalog; empty when cold or expired."""
    snapshot = _state["snapshot"]
    if snapshot is None or monotonic() >= float(_state["expires_at"]):
        return ()
    return tuple(snapshot)


def put_snapshot(specs: Sequence[ModelSpec]) -> None:
    """Cache a snapshot for the TTL window (also a test hook)."""
    _state["snapshot"] = tuple(specs)
    _state["expires_at"] = monotonic() + CACHE_TTL_SECONDS


def invalidate() -> None:
    """Drop the snapshot now (every catalog write calls this; test hook)."""
    _state["snapshot"] = None
    _state["expires_at"] = 0.0


async def ensure_loaded(session: AsyncSession) -> tuple[ModelSpec, ...]:
    """Return a warm snapshot, loading from the DB when cold or expired."""
    snapshot = _state["snapshot"]
    if snapshot is not None and monotonic() < float(_state["expires_at"]):
        return tuple(snapshot)
    rows = await LlmRepository(session).list_catalog_rows()
    specs = build_snapshot(rows)
    put_snapshot(specs)
    return specs


def build_snapshot(rows: Sequence[CatalogRow]) -> tuple[ModelSpec, ...]:
    """Convert rows to specs, skipping unserveable rows (public for tests)."""
    return tuple(spec for row in rows if (spec := _to_spec(row)) is not None)


def _to_spec(row: CatalogRow) -> ModelSpec | None:
    """Row → ModelSpec; skip-with-warning when no adapter can serve it."""
    if not has_adapter(row.provider_name):
        logger.warning(
            "skipping catalog model with no adapter",
            extra={"provider": row.provider_name, "model": row.model_name},
        )
        return None
    return ModelSpec(
        provider=row.provider_name,
        model_name=row.model_name,
        capabilities=_parse_capabilities(row),
        context_window=row.context_window,
        supports_tools=row.supports_tools,
        supports_structured=row.supports_structured,
        supports_streaming=row.supports_streaming,
        enabled=row.provider_enabled and row.model_enabled,
        input_cost_per_1m=row.input_cost_per_1m,
        output_cost_per_1m=row.output_cost_per_1m,
    )


def _parse_capabilities(row: CatalogRow) -> frozenset[ModelCapability]:
    """Tolerate-and-warn on unknown capability strings (forward compat)."""
    parsed: set[ModelCapability] = set()
    for value in row.capabilities:
        try:
            parsed.add(ModelCapability(value))
        except ValueError:
            logger.warning(
                "ignoring unknown capability on catalog model",
                extra={"model": row.model_name, "capability": value},
            )
    return frozenset(parsed)


def list_models(*, enabled_only: bool = True) -> list[ModelSpec]:
    """Snapshot entries (effective-enabled only by default)."""
    snapshot = current_snapshot()
    if enabled_only:
        return [m for m in snapshot if m.enabled]
    return list(snapshot)


def get_model(provider: str, model_name: str) -> ModelSpec | None:
    """Lookup a snapshot entry."""
    for model in current_snapshot():
        if model.provider == provider and model.model_name == model_name:
            return model
    return None


def models_for_capability(
    capability: ModelCapability,
    *,
    prefer_provider: str | None = None,
    prefer_model: str | None = None,
) -> list[ModelSpec]:
    """Ordered enabled candidates for capability (preferred model first)."""
    matches = [m for m in current_snapshot() if m.enabled and capability in m.capabilities]
    if prefer_model and prefer_provider:
        preferred = [
            m for m in matches if m.provider == prefer_provider and m.model_name == prefer_model
        ]
        rest = [m for m in matches if m not in preferred]
        return preferred + rest
    if prefer_provider:
        preferred = [m for m in matches if m.provider == prefer_provider]
        rest = [m for m in matches if m not in preferred]
        return preferred + rest
    return matches
