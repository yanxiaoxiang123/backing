"""money columns as Numeric, JSON unification, schema_version, kline archive

Revision ID: 20260322_01
Revises: 20260321_01
Create Date: 2026-03-22 00:00:00

- 资金/价格/收益从 Float 改为 Numeric(precision, scale)，避免累计舍入误差
  （daily_klines、backtest_results、backtest_trades、jobs.progress、
  analysis_records.final_confidence）
- JSON 统一：strategies.parameters、analysis_records.opinions_json /
  stages_json 从 Text 改为 JSON 类型（与 jobs.payload/result 一致）
- 新增 schema_version（默认 1）到 strategies / analysis_records / jobs
- 新增 daily_klines_archive 归档表（数据生命周期）
"""

import sqlalchemy as sa
from alembic import op

revision = "20260322_01"
down_revision = "20260321_01"
branch_labels = None
depends_on = None

# 表 -> {列: (新类型, nullable)}
_NUMERIC_CHANGES = {
    "daily_klines": {
        "open": (sa.Numeric(12, 4), False),
        "high": (sa.Numeric(12, 4), False),
        "low": (sa.Numeric(12, 4), False),
        "close": (sa.Numeric(12, 4), False),
        "volume": (sa.Numeric(18, 2), False),
        "amount": (sa.Numeric(18, 2), True),
    },
    "backtest_results": {
        "initial_capital": (sa.Numeric(16, 2), False),
        "final_capital": (sa.Numeric(16, 2), False),
        "total_return": (sa.Numeric(10, 4), False),
        "annual_return": (sa.Numeric(10, 4), False),
        "sharpe_ratio": (sa.Numeric(10, 4), True),
        "max_drawdown": (sa.Numeric(10, 4), True),
        "win_rate": (sa.Numeric(10, 4), True),
    },
    "backtest_trades": {
        "price": (sa.Numeric(12, 4), False),
        "amount": (sa.Numeric(16, 2), False),
    },
    "jobs": {
        "progress": (sa.Numeric(5, 4), False),
    },
    "analysis_records": {
        "final_confidence": (sa.Numeric(5, 4), False),
    },
}

# 表 -> [列]：Text -> JSON
_JSON_CHANGES = {
    "strategies": ["parameters"],
    "analysis_records": ["opinions_json", "stages_json"],
}

_SCHEMA_VERSION_TABLES = ("strategies", "analysis_records", "jobs")


def _columns(bind, table: str) -> set:
    return {c["name"] for c in sa.inspect(bind).get_columns(table)}


def _table_names(bind) -> set:
    return set(sa.inspect(bind).get_table_names())


def upgrade() -> None:
    bind = op.get_bind()

    # -- Numeric conversions (batch mode rebuilds the table on SQLite) -------
    for table, changes in _NUMERIC_CHANGES.items():
        if table not in _table_names(bind):
            continue
        cols = _columns(bind, table)
        with op.batch_alter_table(table) as batch_op:
            for col, (new_type, nullable) in changes.items():
                if col in cols:
                    batch_op.alter_column(
                        col,
                        existing_type=sa.Float(),
                        type_=new_type,
                        existing_nullable=nullable,
                        nullable=nullable,
                    )

    # -- Text -> JSON --------------------------------------------------------
    for table, cols in _JSON_CHANGES.items():
        if table not in _table_names(bind):
            continue
        existing = _columns(bind, table)
        with op.batch_alter_table(table) as batch_op:
            for col in cols:
                if col in existing:
                    batch_op.alter_column(
                        col,
                        existing_type=sa.Text(),
                        type_=sa.JSON(),
                        existing_nullable=True,
                        nullable=True,
                    )

    # -- schema_version (default 1) ------------------------------------------
    for table in _SCHEMA_VERSION_TABLES:
        if table not in _table_names(bind):
            continue
        if "schema_version" not in _columns(bind, table):
            with op.batch_alter_table(table) as batch_op:
                batch_op.add_column(
                    sa.Column(
                        "schema_version",
                        sa.Integer(),
                        nullable=False,
                        server_default="1",
                    )
                )

    # -- daily_klines_archive (data lifecycle) --------------------------------
    if "daily_klines_archive" not in _table_names(bind):
        op.create_table(
            "daily_klines_archive",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("stock_code", sa.String(length=20), nullable=False),
            sa.Column("date", sa.Date(), nullable=False),
            sa.Column("open", sa.Numeric(12, 4), nullable=False),
            sa.Column("high", sa.Numeric(12, 4), nullable=False),
            sa.Column("low", sa.Numeric(12, 4), nullable=False),
            sa.Column("close", sa.Numeric(12, 4), nullable=False),
            sa.Column("volume", sa.Numeric(18, 2), nullable=False),
            sa.Column("amount", sa.Numeric(18, 2), nullable=True),
            sa.Column(
                "archived_at",
                sa.DateTime(),
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
        )
        op.create_index(
            "idx_archive_stock_date", "daily_klines_archive", ["stock_code", "date"]
        )
        op.create_index(
            "ix_daily_klines_archive_stock_code",
            "daily_klines_archive",
            ["stock_code"],
        )
        op.create_index(
            "ix_daily_klines_archive_date", "daily_klines_archive", ["date"]
        )


def downgrade() -> None:
    bind = op.get_bind()
    tables = _table_names(bind)

    # -- archive table --------------------------------------------------------
    if "daily_klines_archive" in tables:
        op.drop_index("idx_archive_stock_date", table_name="daily_klines_archive")
        op.drop_index(
            "ix_daily_klines_archive_stock_code", table_name="daily_klines_archive"
        )
        op.drop_index(
            "ix_daily_klines_archive_date", table_name="daily_klines_archive"
        )
        op.drop_table("daily_klines_archive")

    # -- schema_version -------------------------------------------------------
    for table in reversed(_SCHEMA_VERSION_TABLES):
        if table in tables and "schema_version" in _columns(bind, table):
            with op.batch_alter_table(table) as batch_op:
                batch_op.drop_column("schema_version")

    # -- JSON -> Text ---------------------------------------------------------
    for table, cols in _JSON_CHANGES.items():
        if table not in tables:
            continue
        existing = _columns(bind, table)
        with op.batch_alter_table(table) as batch_op:
            for col in cols:
                if col in existing:
                    batch_op.alter_column(
                        col,
                        existing_type=sa.JSON(),
                        type_=sa.Text(),
                        existing_nullable=True,
                        nullable=True,
                    )

    # -- Numeric -> Float -----------------------------------------------------
    for table, changes in _NUMERIC_CHANGES.items():
        if table not in tables:
            continue
        cols = _columns(bind, table)
        with op.batch_alter_table(table) as batch_op:
            for col, (_new_type, nullable) in changes.items():
                if col in cols:
                    batch_op.alter_column(
                        col,
                        existing_type=_new_type,
                        type_=sa.Float(),
                        existing_nullable=nullable,
                        nullable=nullable,
                    )
