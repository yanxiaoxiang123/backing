"""Bind paper orders to immutable risk assessments; old rows remain auditable."""

import sqlalchemy as sa
from alembic import op

revision = "20261030_06"
down_revision = "20261030_05"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("paper_orders") as batch:
        batch.add_column(sa.Column("risk_artifact_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_paper_order_risk_artifact", "artifacts", ["risk_artifact_id"], ["id"], ondelete="SET NULL")
        batch.create_index("ix_paper_orders_risk_artifact_id", ["risk_artifact_id"])


def downgrade() -> None:
    with op.batch_alter_table("paper_orders") as batch:
        batch.drop_index("ix_paper_orders_risk_artifact_id")
        batch.drop_constraint("fk_paper_order_risk_artifact", type_="foreignkey")
        batch.drop_column("risk_artifact_id")
