"""Add webhook_type column to teams_webhooks

Revision ID: 0002
Revises: 0001
Create Date: 2026-02-10 00:00:00.000000

Adds support for both Microsoft Teams and Power Automate webhooks.
Replaces the manual SQL script: migrations/001_add_webhook_type_column.sql
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "teams_webhooks",
        sa.Column(
            "webhook_type",
            sa.String(length=50),
            nullable=False,
            server_default="teams",
        ),
    )


def downgrade() -> None:
    op.drop_column("teams_webhooks", "webhook_type")
