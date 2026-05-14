# backend/app/agents/tools/stock_data.py
from langchain_core.tools import tool
from typing import Annotated
from app.services.baostock_service import baostock_service
from app.config import SessionLocal


@tool
def get_stock_price(
    symbol: Annotated[str, "股票代码，如 000001"],
    days: Annotated[int, "获取天数，默认 30"] = 30
) -> str:
    """获取股票近期价格数据"""
    db = SessionLocal()
    try:
        from datetime import datetime, timedelta
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=days * 2)).strftime("%Y-%m-%d")

        df = baostock_service.get_stock_daily(
            db=db,
            stock_code=symbol,
            start_date=start_date,
            end_date=end_date
        )

        if df is None or df.empty:
            return f"无法获取 {symbol} 的数据"

        # 取最近 days 天
        df = df.tail(days)

        result = f"{symbol} 近 {days} 天数据:\n"
        result += "日期\t\t收盘\t\t涨跌幅\n"
        for _, row in df.iterrows():
            change = row.get('pct_change', 0)
            result += f"{row['date']}\t{row['close']:.2f}\t{change:+.2f}%\n"

        return result
    finally:
        db.close()


@tool
def get_stock_indicators(
    symbol: Annotated[str, "股票代码"],
    period: Annotated[str, "周期 daily/weekly"] = "daily"
) -> str:
    """获取股票技术指标"""
    db = SessionLocal()
    try:
        from datetime import datetime, timedelta
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")

        df = baostock_service.get_stock_daily(
            db=db,
            stock_code=symbol,
            start_date=start_date,
            end_date=end_date
        )

        if df is None or df.empty:
            return f"无法获取 {symbol} 的指标数据"

        # 计算简单指标
        closes = df['close'].values
        if len(closes) >= 5:
            ma5 = sum(closes[-5:]) / 5
        else:
            ma5 = closes[-1] if len(closes) > 0 else 0

        if len(closes) >= 10:
            ma10 = sum(closes[-10:]) / 10
        else:
            ma10 = closes[-1] if len(closes) > 0 else 0

        if len(closes) >= 20:
            ma20 = sum(closes[-20:]) / 20
        else:
            ma20 = closes[-1] if len(closes) > 0 else 0

        latest = closes[-1]
        change_pct = (latest - closes[-2]) / closes[-2] * 100 if len(closes) >= 2 else 0

        result = f"{symbol} 技术指标 (最近数据 {df.iloc[-1]['date']}):\n"
        result += f"最新价: {latest:.2f} ({change_pct:+.2f}%)\n"
        result += f"MA5: {ma5:.2f}\n"
        result += f"MA10: {ma10:.2f}\n"
        result += f"MA20: {ma20:.2f}\n"

        return result
    finally:
        db.close()