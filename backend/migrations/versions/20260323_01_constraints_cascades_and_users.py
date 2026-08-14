"""users table, watchlist user_id, check constraints, ondelete cascades

Revision ID: 20260323_01
Revises: 20260322_01
Create Date: 2026-03-23 00:00:00

- 新增 users 表并写入默认用户（id=1, username='default'），为多用户就绪：
  user_watchlist 增加 user_id（FK -> users.id, ondelete CASCADE），
  唯一约束改为 (user_id, stock_code)
- 命名外键并显式 ondelete=CASCADE（stocks/strategies/backtest_results 删除时
  级联清理子表，SQLite 需整表重建）
- CheckConstraint 防脏数据：job status、trade action、数量/资金非负、
  日期区间、kline 非负、analysis signal
"""

import sqlalchemy as sa
from alembic import op

revision = "20260323_01"
down_revision = "20260322_01"
branch_labels = None
depends_on = None


def _table_names(bind) -> set:
    return set(sa.inspect(bind).get_table_names())


def _index_names(bind, table: str) -> set:
    return {ix["name"] for ix in sa.inspect(bind).get_indexes(table)}


def _check_names(bind, table: str) -> set:
    return {c["name"] for c in sa.inspect(bind).get_check_constraints(table)}


def upgrade() -> None:
    bind = op.get_bind()

    # ------------------------------------------------------------------
    # 1. users 表 + 默认用户（先于 user_watchlist 的外键重建）
    # ------------------------------------------------------------------
    if "users" not in _table_names(bind):
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("username", sa.String(length=50), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
        )
        op.create_index("ix_users_id", "users", ["id"])
        op.create_index("ix_users_username", "users", ["username"], unique=True)

    count = op.get_bind().execute(
        sa.text("SELECT COUNT(*) FROM users")
    ).scalar()
    if count == 0:
        op.execute(
            "INSERT INTO users (id, username) VALUES (1, 'default')"
        )

    # ------------------------------------------------------------------
    # 2. user_watchlist：user_id + (user_id, stock_code) 唯一 + 命名级联外键
    # ------------------------------------------------------------------
    # 2a. 新增 user_id（copy_from 无法处理新增列，先用反射式 batch 重建，
    #      已有行通过 server_default=1 回填到默认用户）
    if "user_id" not in {
        c["name"] for c in sa.inspect(bind).get_columns("user_watchlist")
    }:
        with op.batch_alter_table("user_watchlist") as batch_op:
            batch_op.add_column(
                sa.Column(
                    "user_id",
                    sa.Integer(),
                    nullable=False,
                    server_default="1",
                )
            )

    # 2b. 外键：加 user_id -> users.id，并给 stock_code 外键补 ondelete CASCADE
    fk_names = {
        fk["name"] for fk in sa.inspect(bind).get_foreign_keys("user_watchlist")
    }
    if "fk_watchlist_user_id" not in fk_names:
        with op.batch_alter_table("user_watchlist") as batch_op:
            if "fk_watchlist_stock_code" in fk_names:
                batch_op.drop_constraint("fk_watchlist_stock_code", type_="foreignkey")
            batch_op.create_foreign_key(
                "fk_watchlist_stock_code",
                "stocks",
                ["stock_code"],
                ["code"],
                ondelete="CASCADE",
            )
            batch_op.create_foreign_key(
                "fk_watchlist_user_id",
                "users",
                ["user_id"],
                ["id"],
                ondelete="CASCADE",
            )

    # 2c. 唯一约束改为 (user_id, stock_code)：先去掉 stock_code 的全局唯一索引，
    #     再建复合唯一索引
    if "ix_user_watchlist_stock_code" in _index_names(bind, "user_watchlist"):
        op.drop_index("ix_user_watchlist_stock_code", table_name="user_watchlist")
    if "ix_user_watchlist_stock_code" not in _index_names(bind, "user_watchlist"):
        op.create_index(
            "ix_user_watchlist_stock_code", "user_watchlist", ["stock_code"]
        )
    if "uq_watchlist_user_stock" not in _index_names(bind, "user_watchlist"):
        op.create_index(
            "uq_watchlist_user_stock",
            "user_watchlist",
            ["user_id", "stock_code"],
            unique=True,
        )

    # ------------------------------------------------------------------
    # 3. 命名级联外键 + 非负/枚举 CheckConstraint（整表重建）
    # ------------------------------------------------------------------
    md2 = sa.MetaData()
    kline_new = sa.Table(
        "daily_klines",
        md2,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "stock_code",
            sa.String(length=20),
            sa.ForeignKey(
                "stocks.code", name="fk_daily_klines_stock_code", ondelete="CASCADE"
            ),
            nullable=False,
        ),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("open", sa.Numeric(12, 4), nullable=False),
        sa.Column("high", sa.Numeric(12, 4), nullable=False),
        sa.Column("low", sa.Numeric(12, 4), nullable=False),
        sa.Column("close", sa.Numeric(12, 4), nullable=False),
        sa.Column("volume", sa.Numeric(18, 2), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Index("ix_daily_klines_id", "id"),
        sa.Index("ix_daily_klines_date", "date"),
        sa.Index("ix_daily_klines_stock_code", "stock_code"),
        sa.Index("idx_stock_date", "stock_code", "date", unique=True),
        sa.CheckConstraint(
            "open >= 0 AND high >= 0 AND low >= 0 AND close >= 0 AND volume >= 0 "
            "AND (amount IS NULL OR amount >= 0)",
            name="ck_daily_klines_nonneg",
        ),
    )
    with op.batch_alter_table(
        "daily_klines", recreate="always", copy_from=kline_new
    ) as batch_op:
        pass

    result_new = sa.Table(
        "backtest_results",
        md2,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "strategy_id",
            sa.Integer(),
            sa.ForeignKey(
                "strategies.id",
                name="fk_backtest_results_strategy_id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "stock_code",
            sa.String(length=20),
            sa.ForeignKey(
                "stocks.code",
                name="fk_backtest_results_stock_code",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("initial_capital", sa.Numeric(16, 2), nullable=False),
        sa.Column("final_capital", sa.Numeric(16, 2), nullable=False),
        sa.Column("total_return", sa.Numeric(10, 4), nullable=False),
        sa.Column("annual_return", sa.Numeric(10, 4), nullable=False),
        sa.Column("sharpe_ratio", sa.Numeric(10, 4), nullable=True),
        sa.Column("max_drawdown", sa.Numeric(10, 4), nullable=True),
        sa.Column("win_rate", sa.Numeric(10, 4), nullable=True),
        sa.Column("total_trades", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Index("ix_backtest_results_id", "id"),
        sa.Index("idx_backtest_stock_created", "stock_code", "created_at"),
        sa.CheckConstraint(
            "initial_capital > 0 AND final_capital >= 0",
            name="ck_backtest_results_capital",
        ),
        sa.CheckConstraint(
            "start_date <= end_date", name="ck_backtest_results_date_range"
        ),
        sa.CheckConstraint(
            "total_trades >= 0", name="ck_backtest_results_trades_nonneg"
        ),
    )
    with op.batch_alter_table(
        "backtest_results", recreate="always", copy_from=result_new
    ) as batch_op:
        pass

    trade_new = sa.Table(
        "backtest_trades",
        md2,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "backtest_result_id",
            sa.Integer(),
            sa.ForeignKey(
                "backtest_results.id",
                name="fk_backtest_trades_result_id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "stock_code",
            sa.String(length=20),
            sa.ForeignKey(
                "stocks.code",
                name="fk_backtest_trades_stock_code",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("action", sa.String(length=10), nullable=False),
        sa.Column("price", sa.Numeric(12, 4), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(16, 2), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Index("ix_backtest_trades_id", "id"),
        sa.Index(
            "idx_backtest_trades_result_stock",
            "backtest_result_id",
            "stock_code",
        ),
        sa.CheckConstraint(
            "action IN ('buy', 'sell')", name="ck_backtest_trades_action"
        ),
        sa.CheckConstraint("price >= 0", name="ck_backtest_trades_price_nonneg"),
        sa.CheckConstraint(
            "quantity >= 0", name="ck_backtest_trades_quantity_nonneg"
        ),
        sa.CheckConstraint("amount >= 0", name="ck_backtest_trades_amount_nonneg"),
    )
    with op.batch_alter_table(
        "backtest_trades", recreate="always", copy_from=trade_new
    ) as batch_op:
        pass

    # ------------------------------------------------------------------
    # 4. jobs / analysis_records 的状态与信号 CheckConstraint
    # ------------------------------------------------------------------
    if "jobs" in _table_names(bind) and "ck_jobs_status" not in _check_names(bind, "jobs"):
        with op.batch_alter_table("jobs") as batch_op:
                batch_op.create_check_constraint(
                    "ck_jobs_status",
                    "status IN ('pending', 'running', 'completed', 'failed', 'cancelled')",
                )

    if "analysis_records" in _table_names(bind) and "ck_analysis_final_signal" not in _check_names(
        bind, "analysis_records"
    ):
        with op.batch_alter_table("analysis_records") as batch_op:
                batch_op.create_check_constraint(
                    "ck_analysis_final_signal",
                    "final_signal IN ('buy', 'sell', 'hold')",
                )


def downgrade() -> None:
    bind = op.get_bind()
    tables = _table_names(bind)

    # 移除 jobs / analysis_records 的 CheckConstraint
    if "jobs" in tables and "ck_jobs_status" in _check_names(bind, "jobs"):
        with op.batch_alter_table("jobs") as batch_op:
            batch_op.drop_constraint("ck_jobs_status", type_="check")
    if "analysis_records" in tables and "ck_analysis_final_signal" in _check_names(
        bind, "analysis_records"
    ):
        with op.batch_alter_table("analysis_records") as batch_op:
            batch_op.drop_constraint("ck_analysis_final_signal", type_="check")

    # user_watchlist 恢复为 20260322 形状：无 user_id、stock_code 唯一
    if "user_watchlist" in tables:
        md = sa.MetaData()
        watchlist_old = sa.Table(
            "user_watchlist",
            md,
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "stock_code",
                sa.String(length=20),
                sa.ForeignKey(
                    "stocks.code", name="fk_watchlist_stock_code", ondelete="CASCADE"
                ),
                nullable=False,
            ),
            sa.Column(
                "added_at",
                sa.DateTime(),
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Index("ix_user_watchlist_id", "id"),
            sa.Index("ix_user_watchlist_stock_code", "stock_code", unique=True),
            sa.Index("idx_added_at", "added_at"),
        )
        with op.batch_alter_table(
            "user_watchlist", recreate="always", copy_from=watchlist_old
        ) as batch_op:
            pass

    if "users" in tables:
        op.drop_index("ix_users_username", table_name="users")
        op.drop_index("ix_users_id", table_name="users")
        op.drop_table("users")
