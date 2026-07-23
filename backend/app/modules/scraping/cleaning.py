"""Basic HTML/content cleaning utilities for scraped text."""

from __future__ import annotations

import re

_AD_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"(?i)if\s*you\s*find\s*this\s*story\s*on\s*amazon"),
    re.compile(r"(?i)this\s+content\s+is\s+taken\s+from"),
    re.compile(r"(?i)visit\s+.*?for\s+the\s+best\s+novel\s+reading"),
    re.compile(r"(?i)support\s+the\s+author\s+by\s+searching"),
    re.compile(r"(?i)stolen\s+from\s+.*?please\s+report"),
    re.compile(r"(?i)this\s+story\s+has\s+been\s+stolen"),
    re.compile(r"(?i)please\s+read\s+on\s+the\s+original\s+site"),
    re.compile(r"(?i)support\s+the\s+original\s+source"),
]

_WHITESPACE_RUNS = re.compile(r"\n{3,}")


def clean_content(raw: str) -> str:
    """Strip ad lines, collapse whitespace, return cleaned text."""
    lines: list[str] = []
    for line in raw.split("\n"):
        stripped = line.strip()
        if not stripped:
            lines.append("")
            continue
        if _is_ad_line(stripped):
            continue
        lines.append(stripped)
    text = "\n".join(lines).strip()
    return _WHITESPACE_RUNS.sub("\n\n", text)


def _is_ad_line(line: str) -> bool:
    return any(pat.search(line) for pat in _AD_PATTERNS)
