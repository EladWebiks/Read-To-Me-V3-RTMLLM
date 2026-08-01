"""Usage metric registry — metrics live in code; daily amounts in usage_daily.

Adding a metric = enum value + METRIC_REGISTRY entry + a fact source in the
owning module's daily_usage_facts(). No migration (same keyed philosophy as
membership_quotas). This file imports NO domain modules.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from app.modules.quotas.kinds import QuotaKind


class UsageMetric(StrEnum):
    """One meterable daily amount per (user, day)."""

    LLM_TOKENS_IN = "llm_tokens_in"
    LLM_TOKENS_OUT = "llm_tokens_out"
    LLM_COST_USD = "llm_cost_usd"
    LLM_EXECUTIONS = "llm_executions"
    LLM_FAILURES = "llm_failures"
    AUDIO_CHAPTERS = "audio_chapters"
    AUDIO_JOBS = "audio_jobs"
    AUDIO_JOBS_FAILED = "audio_jobs_failed"
    SCRAPE_CHAPTERS = "scrape_chapters"
    SCRAPE_JOBS = "scrape_jobs"
    SCRAPE_JOBS_FAILED = "scrape_jobs_failed"
    EPUB_IMPORTS = "epub_imports"
    EPUB_IMPORTS_FAILED = "epub_imports_failed"
    REJECTED_LLM_TOKENS = "rejected_llm_tokens"
    REJECTED_LLM_COST_USD = "rejected_llm_cost_usd"
    REJECTED_AUDIO_CHAPTERS = "rejected_audio_chapters"
    REJECTED_STORAGE_BYTES = "rejected_storage_bytes"
    REJECTED_SCRAPE_CHAPTERS = "rejected_scrape_chapters"
    REJECTED_EPUB_IMPORTS = "rejected_epub_imports"


@dataclass(frozen=True, slots=True)
class MetricMeta:
    """Display metadata for one metric."""

    label: str
    unit: str


METRIC_REGISTRY: dict[UsageMetric, MetricMeta] = {
    UsageMetric.LLM_TOKENS_IN: MetricMeta("AI tokens in", "tokens"),
    UsageMetric.LLM_TOKENS_OUT: MetricMeta("AI tokens out", "tokens"),
    UsageMetric.LLM_COST_USD: MetricMeta("AI spend", "USD"),
    UsageMetric.LLM_EXECUTIONS: MetricMeta("AI calls", "calls"),
    UsageMetric.LLM_FAILURES: MetricMeta("AI failures", "calls"),
    UsageMetric.AUDIO_CHAPTERS: MetricMeta("Audio chapters", "chapters"),
    UsageMetric.AUDIO_JOBS: MetricMeta("Audio jobs", "jobs"),
    UsageMetric.AUDIO_JOBS_FAILED: MetricMeta("Audio jobs failed", "jobs"),
    UsageMetric.SCRAPE_CHAPTERS: MetricMeta("Scraped chapters", "chapters"),
    UsageMetric.SCRAPE_JOBS: MetricMeta("Scrape jobs", "jobs"),
    UsageMetric.SCRAPE_JOBS_FAILED: MetricMeta("Scrape jobs failed", "jobs"),
    UsageMetric.EPUB_IMPORTS: MetricMeta("EPUB imports", "imports"),
    UsageMetric.EPUB_IMPORTS_FAILED: MetricMeta("EPUB imports failed", "imports"),
    UsageMetric.REJECTED_LLM_TOKENS: MetricMeta("Blocked: AI tokens", "events"),
    UsageMetric.REJECTED_LLM_COST_USD: MetricMeta("Blocked: AI spend", "events"),
    UsageMetric.REJECTED_AUDIO_CHAPTERS: MetricMeta("Blocked: audio", "events"),
    UsageMetric.REJECTED_STORAGE_BYTES: MetricMeta("Blocked: storage", "events"),
    UsageMetric.REJECTED_SCRAPE_CHAPTERS: MetricMeta("Blocked: scraping", "events"),
    UsageMetric.REJECTED_EPUB_IMPORTS: MetricMeta("Blocked: imports", "events"),
}

# Quota kind -> metrics summed for its monthly usage. STORAGE_BYTES is a
# LEVEL meter (live stored_bytes query) and is deliberately absent.
KIND_METRICS: dict[QuotaKind, tuple[UsageMetric, ...]] = {
    QuotaKind.LLM_TOKENS: (UsageMetric.LLM_TOKENS_IN, UsageMetric.LLM_TOKENS_OUT),
    QuotaKind.LLM_COST_USD: (UsageMetric.LLM_COST_USD,),
    QuotaKind.AUDIO_CHAPTERS: (UsageMetric.AUDIO_CHAPTERS,),
    QuotaKind.SCRAPE_CHAPTERS: (UsageMetric.SCRAPE_CHAPTERS,),
    QuotaKind.EPUB_IMPORTS: (UsageMetric.EPUB_IMPORTS,),
}

REJECTION_METRICS: dict[QuotaKind, UsageMetric] = {
    QuotaKind.LLM_TOKENS: UsageMetric.REJECTED_LLM_TOKENS,
    QuotaKind.LLM_COST_USD: UsageMetric.REJECTED_LLM_COST_USD,
    QuotaKind.AUDIO_CHAPTERS: UsageMetric.REJECTED_AUDIO_CHAPTERS,
    QuotaKind.STORAGE_BYTES: UsageMetric.REJECTED_STORAGE_BYTES,
    QuotaKind.SCRAPE_CHAPTERS: UsageMetric.REJECTED_SCRAPE_CHAPTERS,
    QuotaKind.EPUB_IMPORTS: UsageMetric.REJECTED_EPUB_IMPORTS,
}


@dataclass(frozen=True, slots=True)
class UsageFact:
    """One (user, metric, amount) fact for one day; produced by owning modules."""

    user_id: UUID
    metric: UsageMetric
    amount: float


@dataclass(frozen=True, slots=True)
class LlmModelFact:
    """Cross-user daily LLM aggregate for one (provider, model)."""

    provider: str
    model: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    executions: int


@dataclass(frozen=True, slots=True)
class LlmTaskFact:
    """Cross-user daily LLM aggregate for one task."""

    task: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    executions: int
