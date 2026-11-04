"""Baseline: the V2 schema (users, sessions, datasets, rules, runs, results).

Revision ID: 0001_baseline
Revises:
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def _created_at() -> sa.Column:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        _created_at(),
        sa.CheckConstraint("email = lower(email)", name="ck_users_email_lowercase"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )

    op.create_table(
        "user_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        _created_at(),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])
    op.create_index("ix_user_sessions_expires_at", "user_sessions", ["expires_at"])

    op.create_table(
        "datasets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("column_count", sa.Integer(), nullable=False),
        _created_at(),
        sa.CheckConstraint("row_count >= 0", name="ck_datasets_row_count"),
        sa.CheckConstraint("column_count >= 0", name="ck_datasets_column_count"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_datasets_user_id", "datasets", ["user_id"])

    op.create_table(
        "dataset_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("dataset_id", sa.Integer(), nullable=False),
        sa.Column("profile_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        _created_at(),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dataset_profiles_dataset_id", "dataset_profiles", ["dataset_id"])

    op.create_table(
        "quality_rules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("dataset_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("rule_type", sa.String(length=50), nullable=False),
        sa.Column("configuration", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("severity", sa.String(length=10), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        _created_at(),
        sa.CheckConstraint("severity IN ('LOW', 'MEDIUM', 'HIGH')", name="ck_quality_rules_severity"),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_quality_rules_dataset_id", "quality_rules", ["dataset_id"])

    op.create_table(
        "quality_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("dataset_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("checks_passed", sa.Integer(), server_default="0", nullable=False),
        sa.Column("checks_failed", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status IN ('SUCCESS', 'COMPLETED_WITH_ISSUES', 'FAILED')", name="ck_quality_runs_status"
        ),
        sa.CheckConstraint("checks_passed >= 0", name="ck_quality_runs_passed"),
        sa.CheckConstraint("checks_failed >= 0", name="ck_quality_runs_failed"),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_quality_runs_dataset_id", "quality_runs", ["dataset_id"])
    op.create_index("ix_quality_runs_started_at", "quality_runs", ["started_at"])

    op.create_table(
        "quality_results",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("rule_id", sa.Integer(), nullable=True),
        sa.Column("rule_name", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("severity", sa.String(length=10), nullable=False),
        sa.Column("rows_evaluated", sa.Integer(), nullable=False),
        sa.Column("rows_failed", sa.Integer(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        _created_at(),
        sa.CheckConstraint("status IN ('PASS', 'FAIL')", name="ck_quality_results_status"),
        sa.CheckConstraint("severity IN ('LOW', 'MEDIUM', 'HIGH')", name="ck_quality_results_severity"),
        sa.CheckConstraint("rows_evaluated >= 0", name="ck_quality_results_evaluated"),
        sa.CheckConstraint("rows_failed >= 0", name="ck_quality_results_failed"),
        sa.ForeignKeyConstraint(["run_id"], ["quality_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["rule_id"], ["quality_rules.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_quality_results_run_id", "quality_results", ["run_id"])
    op.create_index("ix_quality_results_rule_id", "quality_results", ["rule_id"])


def downgrade() -> None:
    # Reverse order of creation. Never run this against the development database:
    # it deletes every table. The tests run it on the test database only.
    op.drop_table("quality_results")
    op.drop_table("quality_runs")
    op.drop_table("quality_rules")
    op.drop_table("dataset_profiles")
    op.drop_table("datasets")
    op.drop_table("user_sessions")
    op.drop_table("users")
