"""add job idempotency key, lease and retry columns

Revision ID: 20260321_01
Revises: 20260320_01
Create Date: 2026-03-21 00:00:00

Background jobs were previously executed in web-process threads and died with
the process; the task executor now claims jobs from the database, so each job
gains: an idempotency key (dedupe), retry bookkeeping (transient provider
failures) and a lease refreshed by the executing worker's heartbeat (lets a
dead executor's jobs be reclaimed by another instance).
"""

import sqlalchemy as sa
from alembic import op

revision = "20260321_01"
down_revision = "20260320_01"
branch_labels = None
depends_on = None

_NEW_COLUMNS = (
    ("job_key", sa.String(length=100), True),
    ("retry_count", sa.Integer(), False),
    ("max_retries", sa.Integer(), False),
    ("lease_until", sa.DateTime(), True),
    ("next_retry_at", sa.DateTime(), True),
)


def _column_names(bind) -> set:
    return {c["name"] for c in sa.inspect(bind).get_columns("jobs")}


def upgrade() -> None:
    bind = op.get_bind()
    existing = _column_names(bind)

    with op.batch_alter_table("jobs") as batch_op:
        for name, col_type, nullable in _NEW_COLUMNS:
            if name not in existing:
                batch_op.add_column(
                    sa.Column(
                        name,
                        col_type,
                        nullable=nullable,
                        server_default=sa.text("0") if name in (
                            "retry_count", "max_retries"
                        ) else None,
                    )
                )

    inspector = sa.inspect(bind)
    indexes = {ix["name"] for ix in inspector.get_indexes("jobs")}
    if "uq_jobs_job_key" not in indexes:
        op.create_index("uq_jobs_job_key", "jobs", ["job_key"], unique=True)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    indexes = {ix["name"] for ix in inspector.get_indexes("jobs")}
    if "uq_jobs_job_key" in indexes:
        op.drop_index("uq_jobs_job_key", table_name="jobs")

    existing = _column_names(bind)
    with op.batch_alter_table("jobs") as batch_op:
        for name, _col_type, _nullable in _NEW_COLUMNS:
            if name in existing:
                batch_op.drop_column(name)
