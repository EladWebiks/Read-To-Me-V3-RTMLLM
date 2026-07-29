# RTM v3 backend

Python 3.12 + FastAPI modular monolith for RTM.

## Modules

- `library`, `books`, `chapters`, `reader` — owned library and reading progress.
- `audio`, `downloads` — TTS generation, durable MP3 jobs, MinIO signed URLs, TTL cleanup.
- `scraping`, `discovery`, `imports` — four deterministic site adapters, ranked title
  discovery/import, and chunked EPUB import.
- `llm` — provider abstraction, Gemini adapter, telemetry, conversation context.
- `tools`, `orchestration` — authorized/audited assistant tools, budgets, true SSE
  streaming, form HITL, and controlled client actions.
- `summaries` — content-hash-invalidated persisted book summaries.

## Development

```bash
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

Run the complete quality gate:

```bash
uv run ruff check . --fix && uv run ruff format .
uv run ruff check . && uv run ruff format --check .
uv run mypy .
uv run pytest -m "unit or integration"
```

Alembic migrations run through the application/container startup path. Configuration is
defined in `app/core/config.py`; copy the repository `.env.example` for local values.
