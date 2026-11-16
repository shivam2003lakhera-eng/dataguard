"""Opt-in loading of valid rows: dataset key columns, dataset_records, run load counts.

Nothing changes for existing data: key_columns is NULL (no loading) and the new
run columns are NULL (not loaded).

Revision ID: 0003_record_loading
Revises: 0002_run_metrics
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003_record_loading"
down_revision = "0002_run_metrics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "datasets", sa.Column("key_columns", postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )

    op.create_table(
        "dataset_records",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("dataset_id", sa.Integer(), nullable=False),
        sa.Column("row_key", sa.String(length=500), nullable=False),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dataset_id", "row_key", name="uq_dataset_records_key"),
    )

    op.add_column("quality_runs", sa.Column("rows_inserted", sa.Integer(), nullable=True))
    op.add_column("quality_runs", sa.Column("rows_updated", sa.Integer(), nullable=True))
    op.add_column("quality_runs", sa.Column("rows_unchanged", sa.Integer(), nullable=True))
    op.add_column("quality_runs", sa.Column("rows_skipped", sa.Integer(), nullable=True))
    op.create_check_constraint(
        "ck_quality_runs_load_accounting",
        "quality_runs",
        "rows_inserted IS NULL OR (rows_inserted >= 0 AND rows_updated >= 0 "
        "AND rows_unchanged >= 0 AND rows_skipped >= 0 "
        "AND rows_inserted + rows_updated + rows_unchanged + rows_skipped = valid_rows)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_quality_runs_load_accounting", "quality_runs", type_="check")
    op.drop_column("quality_runs", "rows_skipped")
    op.drop_column("quality_runs", "rows_unchanged")
    op.drop_column("quality_runs", "rows_updated")
    op.drop_column("quality_runs", "rows_inserted")
    op.drop_table("dataset_records")
    op.drop_column("datasets", "key_columns")
