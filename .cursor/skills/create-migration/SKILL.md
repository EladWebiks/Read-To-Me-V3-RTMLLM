---
name: create-migration
description: Create and apply an Alembic database migration for the RTM v3 backend. Use whenever SQLAlchemy models change (new table, column, index, constraint) so the schema stays versioned and reversible.
---

# Create a database migration

All schema changes go through Alembic — never edit the DB by hand. See rule `30-database`.

## Steps

1. **Change the SQLAlchemy models** first (in the owning module's `models.py`). Follow DB conventions: UUID `id`, `created_at`/`updated_at`, `user_id` FK for owned tables, `deleted_at` for soft delete, indexes on FKs + hot columns, no blobs in DB.
2. **Autogenerate** the migration:
   ```bash
   cd backend && uv run alembic revision --autogenerate -m "describe change"
   ```
3. **Review the generated file** — autogenerate is not perfect:
   - Check both `upgrade()` and `downgrade()` are correct and reversible.
   - Verify indexes, unique constraints (`UNIQUE(book_id, chapter_number)`, `UNIQUE(user_id, book_id)`), FKs, and `ON DELETE` behavior.
   - For pgvector columns / GIN(FTS) / hnsw indexes, confirm the DDL is present (may need manual `op.execute`).
   - Handle data backfill explicitly if a new NOT NULL column is added to a populated table.
4. **Apply and test:**
   ```bash
   uv run alembic upgrade head
   uv run alembic downgrade -1 && uv run alembic upgrade head   # verify reversibility
   ```
5. **Add a migration test** if the change involves data transformation.
6. Commit the model change + migration together.

## Guardrails
- One logical change per migration; clear message.
- Never delete/rewrite an already-applied migration — add a new one.
- Ensure required Postgres extensions (`vector`) are enabled by an early migration.
