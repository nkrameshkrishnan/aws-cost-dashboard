# Database Migrations

This directory contains manual SQL migrations for the AWS Cost Dashboard database.

## How to Apply Migrations

### Using Docker

To apply a migration to the database running in Docker:

```bash
docker exec aws-cost-db psql -U postgres -d aws_cost_dashboard -f /path/to/migration.sql
```

Or copy the SQL file into the container and run it:

```bash
docker cp migrations/001_add_webhook_type_column.sql aws-cost-db:/tmp/
docker exec aws-cost-db psql -U postgres -d aws_cost_dashboard -f /tmp/001_add_webhook_type_column.sql
```

### Using psql Directly

If you have direct access to the database:

```bash
psql -U postgres -d aws_cost_dashboard -f migrations/001_add_webhook_type_column.sql
```

## Migration History

| # | Date | Description | Applied |
|---|------|-------------|---------|
| 001 | 2026-02-10 | Add webhook_type column for Power Automate support | ✅ |

## Future: Alembic Integration

For production deployments, consider migrating to Alembic for automated schema migrations:

```bash
# Install Alembic
pip install alembic

# Initialize Alembic
alembic init alembic

# Auto-generate migrations from models
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head
```

See [Alembic documentation](https://alembic.sqlalchemy.org/) for more details.
