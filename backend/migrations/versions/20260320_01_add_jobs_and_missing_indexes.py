"""add persistent jobs table and backfill missing indexes

Revision ID: 20260320_01
Revises: 20260319_01
Create Date: 2026-03-20 00:00:00
"""

import sqlalchemy as sa
from alembic import op

revision = "20260320_01"
down_revision = "20260319_01"
branch_labels = None
depends_on = None


def _table_names(bind) -> set:
    return set(sa.inspect(bind).get_table_names())


def upgrade() -> None:
    bind = op.get_bind()

    # jobs table (model: JobDbRecord). Drifted databases may already have it
    # from the former startup create_all(); create only when missing.
    if "jobs" not in _table_names(bind):
        op.create_table(
            "jobs",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("job_type", sa.String(length=50), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("progress", sa.Float(), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=True),
            sa.Column("result", sa.JSON(), nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
        )

    # Indexes declared on the models but missing from the migration chain.
    # Create only when absent so drifted databases repair in place.
    inspector = sa.inspect(bind)

    if "jobs" in _table_names(bind):
        existing = {idx["name"] for idx in inspector.get_indexes("jobs")}
        if "ix_jobs_job_type" not in existing:
            op.create_index("ix_jobs_job_type", "jobs", ["job_type"])
        if "ix_jobs_status" not in existing:
            op.create_index("ix_jobs_status", "jobs", ["status"])

    if "backtest_results" in _table_names(bind):
        existing = {idx["name"] for idx in inspector.get_indexes("backtest_results")}
        if "idx_backtest_stock_created" not in existing:
            op.create_index(
                "idx_backtest_stock_created",
                "backtest_results",
                ["stock_code", "created_at"],
            )

    if "analysis_records" in _table_names(bind):
        existing = {idx["name"] for idx in inspector.get_indexes("analysis_records")}
        if "idx_analysis_stock_date" not in existing:
            op.create_index(
                "idx_analysis_stock_date",
                "analysis_records",
                ["stock_code", "analysis_date"],
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "backtest_results" in _table_names(bind):
        existing = {idx["name"] for idx in inspector.get_indexes("backtest_results")}
        if "idx_backtest_stock_created" in existing:
            op.drop_index("idx_backtest_stock_created", table_name="backtest_results")

    if "analysis_records" in _table_names(bind):
        existing = {idx["name"] for idx in inspector.get_indexes("analysis_records")}
        if "idx_analysis_stock_date" in existing:
            op.drop_index("idx_analysis_stock_date", table_name="analysis_records")

    if "jobs" in _table_names(bind):
        existing = {idx["name"] for idx in inspector.get_indexes("jobs")}
        if "ix_jobs_job_type" in existing:
            op.drop_index("ix_jobs_job_type", table_name="jobs")
        if "ix_jobs_status" in existing:
            op.drop_index("ix_jobs_status", table_name="jobs")
        op.drop_table("jobs")
