---
name: add-backend-module
description: Scaffold a new FastAPI bounded-context module in the RTM v3 backend with the standard router/service/repository/schemas/models/tests layout. Use when adding a new backend module or feature area (e.g. library, downloads, discovery) to the Python modular monolith.
---

# Add a backend module

Create a new bounded context under `backend/app/modules/<name>/` following RTM v3's modular-monolith conventions (see rules `10-architecture`, `20-python`, `30-database`).

## Steps

1. **Confirm ownership.** Verify no existing module should own this feature. Pick a singular, lowercase `<name>`.
2. **Create the package** with these files:
   ```
   modules/<name>/
     __init__.py
     router.py        # APIRouter, thin routes, pydantic in/out, authz via Depends
     service.py       # all business logic
     repository.py    # DB access for THIS module's tables only
     schemas.py       # pydantic request/response DTOs
     models.py        # SQLAlchemy models for THIS module
     exceptions.py    # typed domain exceptions
     tests/__init__.py
     tests/test_service.py
   ```
3. **Models** (`models.py`): UUID `id`, `created_at`/`updated_at`; `user_id` FK if user-owned; `deleted_at` for soft delete; indexes on FKs + hot query columns. No blobs in DB.
4. **Migration:** generate an Alembic migration for the new tables (use the `create-migration` skill). Never create tables by hand.
5. **Repository:** async session via a `core` dependency; return typed objects; filter `deleted_at` by default; enforce `user_id` in queries.
6. **Service:** pure business logic; raise typed exceptions from `exceptions.py`; no FastAPI or raw SQL imports.
7. **Router:** delegate to service; validate with `schemas.py`; apply auth/ownership dependency; no logic inline. Map exceptions in the central handler (add mapping if new).
8. **Register** the router in the app router registry / `main.py`.
9. **Tests:** unit-test the service (primary target); add integration test for the router if it has non-trivial wiring.
10. **Verify:** `ruff`, `mypy`, and `pytest` pass. Update `docs/phase-0-discovery.md` §11 if this is a genuinely new module.

## Guardrails
- Do NOT access another module's repository/models — call its service.
- Do NOT put business logic in the router or DB access in the service.
- If the module does LLM/scraping work, route through `modules/llm` / `modules/scraping` — never import SDKs or `httpx`-to-source directly here.
