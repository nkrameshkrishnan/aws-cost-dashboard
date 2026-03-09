"""Initial schema — aws_accounts, budgets, teams_webhooks, business_metrics, async_jobs

Revision ID: 0001
Revises:
Create Date: 2026-01-01 00:00:00.000000

This migration represents the baseline schema that was previously created by
Base.metadata.create_all().  If you are migrating an existing database that
was bootstrapped with create_all(), stamp it at this revision first:

    alembic stamp 0001

Then apply any subsequent migrations:

    alembic upgrade head
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------ #
    # aws_accounts                                                         #
    # ------------------------------------------------------------------ #
    op.create_table(
        "aws_accounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("encrypted_access_key_id", sa.String(length=500), nullable=False),
        sa.Column("encrypted_secret_access_key", sa.String(length=500), nullable=False),
        sa.Column("account_id", sa.String(length=12), nullable=True),
        sa.Column("region", sa.String(length=50), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("last_validated", sa.DateTime(timezone=True), nullable=True),
        sa.Column("validation_error", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_aws_accounts_id"), "aws_accounts", ["id"], unique=False)
    op.create_index(op.f("ix_aws_accounts_name"), "aws_accounts", ["name"], unique=True)

    # ------------------------------------------------------------------ #
    # budgets                                                              #
    # ------------------------------------------------------------------ #
    op.create_table(
        "budgets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("aws_account_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column(
            "period",
            sa.Enum("monthly", "quarterly", "yearly", name="budgetperiod"),
            nullable=False,
        ),
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("threshold_warning", sa.Float(), nullable=True),
        sa.Column("threshold_critical", sa.Float(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["aws_account_id"], ["aws_accounts.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_budgets_aws_account_id"), "budgets", ["aws_account_id"], unique=False)
    op.create_index(op.f("ix_budgets_id"), "budgets", ["id"], unique=False)
    op.create_index(op.f("ix_budgets_is_active"), "budgets", ["is_active"], unique=False)

    # ------------------------------------------------------------------ #
    # teams_webhooks                                                        #
    # ------------------------------------------------------------------ #
    op.create_table(
        "teams_webhooks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("webhook_url", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("send_budget_alerts", sa.Boolean(), nullable=False),
        sa.Column("send_cost_summaries", sa.Boolean(), nullable=False),
        sa.Column("send_audit_reports", sa.Boolean(), nullable=False),
        sa.Column("budget_threshold_percentage", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_teams_webhooks_id"), "teams_webhooks", ["id"], unique=False)
    op.create_index(op.f("ix_teams_webhooks_name"), "teams_webhooks", ["name"], unique=False)

    # ------------------------------------------------------------------ #
    # business_metrics                                                      #
    # ------------------------------------------------------------------ #
    op.create_table(
        "business_metrics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("profile_name", sa.String(length=100), nullable=False),
        sa.Column("metric_date", sa.Date(), nullable=False),
        sa.Column("active_users", sa.Integer(), nullable=True),
        sa.Column("total_transactions", sa.Integer(), nullable=True),
        sa.Column("api_calls", sa.Integer(), nullable=True),
        sa.Column("data_processed_gb", sa.Float(), nullable=True),
        sa.Column("custom_metric_1", sa.Float(), nullable=True),
        sa.Column("custom_metric_1_name", sa.String(length=100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_name", "metric_date", name="_profile_date_uc"),
    )
    op.create_index(
        op.f("ix_business_metrics_id"), "business_metrics", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_business_metrics_metric_date"),
        "business_metrics",
        ["metric_date"],
        unique=False,
    )
    op.create_index(
        op.f("ix_business_metrics_profile_name"),
        "business_metrics",
        ["profile_name"],
        unique=False,
    )

    # ------------------------------------------------------------------ #
    # async_jobs                                                            #
    # ------------------------------------------------------------------ #
    op.create_table(
        "async_jobs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column(
            "job_type",
            sa.Enum(
                "unit_cost_calculate",
                "unit_cost_trend",
                name="jobtype",
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("pending", "running", "completed", "failed", name="jobstatus"),
            nullable=False,
        ),
        sa.Column("parameters", sa.Text(), nullable=False),
        sa.Column("result", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_async_jobs_id"), "async_jobs", ["id"], unique=False)
    op.create_index(
        op.f("ix_async_jobs_status"), "async_jobs", ["status"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_async_jobs_status"), table_name="async_jobs")
    op.drop_index(op.f("ix_async_jobs_id"), table_name="async_jobs")
    op.drop_table("async_jobs")

    op.drop_index(op.f("ix_business_metrics_profile_name"), table_name="business_metrics")
    op.drop_index(op.f("ix_business_metrics_metric_date"), table_name="business_metrics")
    op.drop_index(op.f("ix_business_metrics_id"), table_name="business_metrics")
    op.drop_table("business_metrics")

    op.drop_index(op.f("ix_teams_webhooks_name"), table_name="teams_webhooks")
    op.drop_index(op.f("ix_teams_webhooks_id"), table_name="teams_webhooks")
    op.drop_table("teams_webhooks")

    op.drop_index(op.f("ix_budgets_is_active"), table_name="budgets")
    op.drop_index(op.f("ix_budgets_id"), table_name="budgets")
    op.drop_index(op.f("ix_budgets_aws_account_id"), table_name="budgets")
    op.drop_table("budgets")
    op.execute("DROP TYPE IF EXISTS budgetperiod")

    op.drop_index(op.f("ix_aws_accounts_name"), table_name="aws_accounts")
    op.drop_index(op.f("ix_aws_accounts_id"), table_name="aws_accounts")
    op.drop_table("aws_accounts")

    op.execute("DROP TYPE IF EXISTS jobtype")
    op.execute("DROP TYPE IF EXISTS jobstatus")
