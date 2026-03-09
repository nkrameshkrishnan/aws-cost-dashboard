# Database Migrations — Legacy (Archived)

> ⚠️ **This directory is archived.**  Alembic is now the source of truth for all
> schema changes.  Do not add new SQL files here.  See `backend/alembic/` instead.

The SQL file in this directory (`001_add_webhook_type_column.sql`) has been
superseded by Alembic migration `0002_add_webhook_type_column`.

## Migrating an Existing Database

If your database was created with `create_all()` before Alembic was introduced,
stamp it at the baseline revision and then apply any outstanding migrations:

```bash
# From the backend/ directory:
alembic stamp 0001   # marks DB as already at the initial-schema baseline
alembic upgrade head  # applies 0002 (webhook_type column) and any future migrations
```

After this, new deployments will run `alembic upgrade head` automatically on
startup via `upgrade_db()` in `app/database/base.py`.

## Common Alembic Commands

```bash
# Apply all pending migrations
alembic upgrade head

# Roll back one revision
alembic downgrade -1

# Show current revision on the live database
alembic current

# Show migration history
alembic history --verbose

# Auto-generate a new migration from model changes
alembic revision --autogenerate -m "describe your change here"
```

## Migration History

| Revision | Date       | Description                                      |
|----------|------------|--------------------------------------------------|
| 0001     | 2026-01-01 | Initial schema (aws_accounts, budgets, teams_webhooks, business_metrics, async_jobs) |
| 0002     | 2026-02-10 | Add webhook_type column to teams_webhooks        |
