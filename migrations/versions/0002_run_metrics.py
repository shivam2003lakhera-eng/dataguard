"""Run metrics (row accounting, duration, file hash) and result category.

Existing rows are kept. New run columns are NULL for old runs ("not measured").
Old results are classified: configuration failures and required_columns results
become "schema"; everything else stays "quality".

Revision ID: 0002_run_metrics
Revises: 0001_baseline
"""
import sqlalchemy as sa
from alembic import op

revision = "0002_run_metrics"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("quality_runs", sa.Column("source_rows", sa.Integer(), nullable=True))
    op.add_column("quality_runs", sa.Column("valid_rows", sa.Integer(), nullable=True))
    op.add_column("quality_runs", sa.Column("rejected_rows", sa.Integer(), nullable=True))
    op.add_column("quality_runs", sa.Column("duration_ms", sa.Integer(), nullable=True))
    op.add_column("quality_runs", sa.Column("loadable", sa.Boolean(), nullable=True))
    op.add_column("quality_runs", sa.Column("file_sha256", sa.String(length=64), nullable=True))
    op.create_check_constraint("ck_quality_runs_source_rows", "quality_runs", "source_rows >= 0")
    op.create_check_constraint("ck_quality_runs_duration", "quality_runs", "duration_ms >= 0")
    op.create_check_constraint(
        "ck_quality_runs_row_accounting",
        "quality_runs",
        "source_rows IS NULL OR (valid_rows >= 0 AND rejected_rows >= 0 "
        "AND valid_rows + rejected_rows = source_rows)",
    )

    op.add_column(
        "quality_results",
        sa.Column("category", sa.String(length=10), server_default="quality", nullable=False),
    )
    op.add_column("quality_results", sa.Column("rows_rejected", sa.Integer(), nullable=True))
    op.create_check_constraint(
        "ck_quality_results_category", "quality_results", "category IN ('schema', 'quality')"
    )
    op.create_check_constraint("ck_quality_results_rejected", "quality_results", "rows_rejected >= 0")

    # Classify results saved before categories existed.
    op.execute(
        """
        UPDATE quality_results
        SET category = 'schema'
        WHERE details ->> 'error' = 'configuration'
           OR rule_id IN (SELECT id FROM quality_rules WHERE rule_type = 'required_columns')
        """
    )


def downgrade() -> None:
    op.drop_constraint("ck_quality_results_rejected", "quality_results", type_="check")
    op.drop_constraint("ck_quality_results_category", "quality_results", type_="check")
    op.drop_column("quality_results", "rows_rejected")
    op.drop_column("quality_results", "category")

    op.drop_constraint("ck_quality_runs_row_accounting", "quality_runs", type_="check")
    op.drop_constraint("ck_quality_runs_duration", "quality_runs", type_="check")
    op.drop_constraint("ck_quality_runs_source_rows", "quality_runs", type_="check")
    op.drop_column("quality_runs", "file_sha256")
    op.drop_column("quality_runs", "loadable")
    op.drop_column("quality_runs", "duration_ms")
    op.drop_column("quality_runs", "rejected_rows")
    op.drop_column("quality_runs", "valid_rows")
    op.drop_column("quality_runs", "source_rows")
