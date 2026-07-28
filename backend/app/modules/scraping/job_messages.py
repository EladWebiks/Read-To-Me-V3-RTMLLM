"""User-facing scrape job error / status copy."""

from __future__ import annotations

_INTERNAL_MARKERS = (
    "missinggreenlet",
    "validation error for chapterread",
    "greenlet_spawn",
)
_MAX_ERROR_LEN = 140
_INTERNAL_MSG = "Couldn't save a chapter (internal error). Remove this job and try again."


def public_scrape_error(raw: str | None) -> str | None:
    """Collapse stack-ish worker errors into a short UI string."""
    if raw is None:
        return None
    compact = " ".join(raw.split())
    if not compact:
        return None
    low = compact.lower()
    if any(marker in low for marker in _INTERNAL_MARKERS):
        compact = _INTERNAL_MSG
    elif len(compact) > _MAX_ERROR_LEN:
        compact = f"{compact[: _MAX_ERROR_LEN - 1]}..."
    return compact
