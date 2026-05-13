"""baseline schema

Revision ID: 20260316_01
Revises:
Create Date: 2026-03-16 16:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260316_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "analysis_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("stock_code", sa.String(length=20), nullable=False),
        sa.Column("stock_name", sa.String(length=100), nullable=True),
        sa.Column("analysis_date", sa.Date(), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("final_signal", sa.String(length=10), nullable=False),
        sa.Column("final_confidence", sa.Float(), nullable=False),
        sa.Column("final_reason", sa.Text(), nullable=True),
        sa.Column("opinions_json", sa.Text(), nullable=True),
        sa.Column("stages_json", sa.Text(), nullable=True),
        sa.Column("duration_s", sa.Float(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")
        ),
    )
    op.create_index("ix_analysis_records_id", "analysis_records", ["id"])
    op.create_index(
        "ix_analysis_records_stock_code", "analysis_records", ["stock_code"]
    )
    op.create_index(
        "ix_analysis_records_analysis_date", "analysis_records", ["analysis_date"]
    )

    op.create_table(
        "stocks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("market", sa.String(length=20), nullable=False),
        sa.Column("list_date", sa.Date(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")
        ),
    )
    op.create_index("ix_stocks_id", "stocks", ["id"])
    op.create_index("ix_stocks_code", "stocks", ["code"], unique=True)

    op.create_table(
        "strategies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("strategy_type", sa.String(length=50), nullable=False),
        sa.Column("parameters", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")
        ),
    )
    op.create_index("ix_strategies_id", "strategies", ["id"])

    op.create_table(
        "daily_klines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("stock_code", sa.String(length=20), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("open", sa.Float(), nullable=False),
        sa.Column("high", sa.Float(), nullable=False),
        sa.Column("low", sa.Float(), nullable=False),
        sa.Column("close", sa.Float(), nullable=False),
        sa.Column("volume", sa.Float(), nullable=False),
        sa.Column("amount", sa.Float(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")
        ),
        sa.ForeignKeyConstraint(["stock_code"], ["stocks.code"]),
    )
    op.create_index("ix_daily_klines_id", "daily_klines", ["id"])
    op.create_index("ix_daily_klines_stock_code", "daily_klines", ["stock_code"])
    op.create_index("ix_daily_klines_date", "daily_klines", ["date"])
    op.create_index(
        "idx_stock_date", "daily_klines", ["stock_code", "date"], unique=True
    )

    op.create_table(
        "backtest_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("strategy_id", sa.Integer(), nullable=False),
        sa.Column("stock_code", sa.String(length=20), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("initial_capital", sa.Float(), nullable=False),
        sa.Column("final_capital", sa.Float(), nullable=False),
        sa.Column("total_return", sa.Float(), nullable=False),
        sa.Column("annual_return", sa.Float(), nullable=False),
        sa.Column("sharpe_ratio", sa.Float(), nullable=True),
        sa.Column("max_drawdown", sa.Float(), nullable=True),
        sa.Column("win_rate", sa.Float(), nullable=True),
        sa.Column("total_trades", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")
        ),
        sa.ForeignKeyConstraint(["stock_code"], ["stocks.code"]),
        sa.ForeignKeyConstraint(["strategy_id"], ["strategies.id"]),
    )
    op.create_index("ix_backtest_results_id", "backtest_results", ["id"])

    op.create_table(
        "backtest_trades",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("backtest_result_id", sa.Integer(), nullable=False),
        sa.Column("stock_code", sa.String(length=20), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("action", sa.String(length=10), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")
        ),
        sa.ForeignKeyConstraint(["backtest_result_id"], ["backtest_results.id"]),
        sa.ForeignKeyConstraint(["stock_code"], ["stocks.code"]),
    )
    op.create_index("ix_backtest_trades_id", "backtest_trades", ["id"])


def downgrade() -> None:
    op.drop_index("ix_backtest_trades_id", table_name="backtest_trades")
    op.drop_table("backtest_trades")
    op.drop_index("ix_backtest_results_id", table_name="backtest_results")
    op.drop_table("backtest_results")
    op.drop_index("idx_stock_date", table_name="daily_klines")
    op.drop_index("ix_daily_klines_date", table_name="daily_klines")
    op.drop_index("ix_daily_klines_stock_code", table_name="daily_klines")
    op.drop_index("ix_daily_klines_id", table_name="daily_klines")
    op.drop_table("daily_klines")
    op.drop_index("ix_strategies_id", table_name="strategies")
    op.drop_table("strategies")
    op.drop_index("ix_stocks_code", table_name="stocks")
    op.drop_index("ix_stocks_id", table_name="stocks")
    op.drop_table("stocks")
    op.drop_index("ix_analysis_records_analysis_date", table_name="analysis_records")
    op.drop_index("ix_analysis_records_stock_code", table_name="analysis_records")
    op.drop_index("ix_analysis_records_id", table_name="analysis_records")
    op.drop_table("analysis_records")
