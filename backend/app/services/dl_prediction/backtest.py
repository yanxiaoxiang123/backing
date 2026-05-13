"""
回测逻辑模块
基于预测结果进行回测
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Tuple
import logging

from app.services.baostock_service import BaostockService
from app.services.dl_prediction.features import DLFeatures
from app.services.dl_prediction.model_loader import DLModelLoader

logger = logging.getLogger(__name__)


class TradingStrategy:
    """智能交易策略"""

    def __init__(
        self,
        initial_capital=100000,
        atr_period=14,
        atr_multiplier=2.0,
        trailing_stop_pct=0.05,
    ):
        """
        Args:
            initial_capital: 初始资金
            atr_period: ATR计算周期
            atr_multiplier: ATR止损倍数（止损 = 买入价 - atr_multiplier * ATR）
            trailing_stop_pct: 跟踪止损回撤百分比（从最高点回撤超过此比例则卖出）
        """
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.position = 0
        self.position_cost = 0
        self.trades = []
        self.portfolio_values = []
        self.dates = []
        self.close_prices = []
        # 动态止损参数
        self.atr_period = atr_period
        self.atr_multiplier = atr_multiplier
        self.trailing_stop_pct = trailing_stop_pct
        # 跟踪止损状态
        self.entry_price = 0.0
        self.highest_price_since_entry = 0.0
        self.stop_loss_price = 0.0

    def open_position(self, price) -> None:
        """开仓时初始化跟踪止损状态"""
        self.entry_price = price
        self.highest_price_since_entry = price

    def update_trailing_stop(self, current_price, atr) -> None:
        """更新跟踪止损价格"""
        if self.position == 0:
            return

        # 更新持仓期间最高价
        if current_price > self.highest_price_since_entry:
            self.highest_price_since_entry = current_price

        # 计算跟踪止损：最高价回撤 trailing_stop_pct
        trailing_stop = self.highest_price_since_entry * (1 - self.trailing_stop_pct)

        # 计算ATR止损：买入价 - atr_multiplier * ATR
        atr_stop = self.entry_price - self.atr_multiplier * atr if atr > 0 else 0

        # 取两者中较高的作为止损价（更保守）
        self.stop_loss_price = max(trailing_stop, atr_stop)

    def should_buy(
        self, current_price, predicted_price, ma5, ma20, rsi
    ) -> Tuple[bool, float]:
        """买入信号判断"""
        predicted_return = (predicted_price - current_price) / current_price

        if predicted_return <= 0:
            return False, 0

        trend_ok = current_price > ma5 * 0.98 and ma5 > ma20 * 0.99 and rsi < 75

        if not trend_ok and predicted_return < 0.02:
            return False, 0

        return True, predicted_return

    def should_sell(self, current_price, predicted_price, ma5, rsi, atr=0) -> bool:
        """
        卖出信号判断（包含动态止损）

        Args:
            current_price: 当前价格
            predicted_price: 预测价格
            ma5: 5日均线
            rsi: RSI指标
            atr: ATR值（用于动态止损）
        """
        if self.position == 0:
            return False

        holding_return = (current_price - self.position_cost) / self.position_cost
        predicted_return = (predicted_price - current_price) / current_price

        # 1. 预测价格下跌
        if predicted_return < -0.005:
            return True

        # 2. 固定止盈（8%）
        if holding_return > 0.08:
            return True

        # 3. 固定止损（5%）- 作为保底
        if holding_return < -0.05:
            return True

        # 4. 更新并检查动态跟踪止损
        self.update_trailing_stop(current_price, atr)
        if self.stop_loss_price > 0 and current_price <= self.stop_loss_price:
            logger.debug(
                f"触发动态止损: 当前价={current_price}, 止损价={self.stop_loss_price}, 持仓收益={holding_return:.2%}"
            )
            return True

        # 5. 技术面卖出信号
        if current_price < ma5 * 0.97 and rsi > 70:
            return True

        return False

    def execute_trade(self, date, price, action, quantity=0) -> None:
        """执行交易"""
        if action == "buy" and quantity > 0:
            cost = quantity * price
            if cost <= self.cash:
                self.position += quantity
                self.cash -= cost
                self.position_cost = price

                # 开仓时初始化跟踪止损
                self.open_position(price)

                self.trades.append(
                    {
                        "date": date,
                        "action": "BUY",
                        "price": float(price),
                        "quantity": quantity,
                        "cost": float(cost),
                        "cash": float(self.cash),
                        "position": self.position,
                    }
                )

        elif action == "sell" and self.position > 0:
            quantity = self.position
            revenue = quantity * price
            self.cash += revenue

            self.trades.append(
                {
                    "date": date,
                    "action": "SELL",
                    "price": float(price),
                    "quantity": quantity,
                    "revenue": float(revenue),
                    "cash": float(self.cash),
                    "position": 0,
                }
            )

            self.position = 0
            self.position_cost = 0

    def update_portfolio_value(self, date, price) -> None:
        """更新组合价值"""
        total_value = self.cash + self.position * price
        self.portfolio_values.append(float(total_value))
        self.dates.append(date)
        self.close_prices.append(float(price))


class DLBacktester:
    """基于预测结果的回测"""

    def __init__(self):
        self.baostock = BaostockService()
        self.features = DLFeatures()
        self.model_loader = DLModelLoader()
        self._model_loaded = False

    def _ensure_model_loaded(self) -> None:
        """确保模型已加载（懒加载）"""
        if not self._model_loaded:
            try:
                self.model_loader.load_model()
                self._model_loaded = True
                logger.info("模型加载成功")
            except Exception as e:
                logger.warning(f"模型加载失败: {e}")
                raise

    def run_backtest(
        self,
        stock_code: str,
        start_date: str,
        end_date: str,
        initial_capital: float = 100000,
    ) -> Dict[str, Any]:
        """
        运行回测

        Args:
            stock_code: 股票代码
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            initial_capital: 初始资金

        Returns:
            回测结果
        """
        try:
            # 获取历史数据
            logger.info(f"获取回测数据: {stock_code} {start_date} - {end_date}")

            # 转换为 baostock 格式
            bs_code = self._convert_to_baostock_code(stock_code)
            df = self.baostock.get_daily_kline(bs_code, start_date, end_date)

            if df is None or df.empty:
                raise ValueError("未获取到数据")

            if len(df) < 60:
                raise ValueError(f"数据不足: {len(df)} 条")

            # DataFrame 已获取
            df["trade_date"] = pd.to_datetime(df["date"])
            df = df.sort_values("trade_date")

            # 计算技术指标
            df["ma5"] = df["close"].rolling(5).mean()
            df["ma20"] = df["close"].rolling(20).mean()
            df["rsi"] = self._calculate_rsi(df["close"])
            df["atr"] = self._calculate_atr(df)

            # 初始化策略
            strategy = TradingStrategy(initial_capital=initial_capital)

            # 回测参数
            time_steps = 60  # 模型输入的时间步长

            # 需要前60天数据作为输入
            for i in range(time_steps, len(df)):
                current_data = df.iloc[i]
                current_date = current_data["trade_date"].strftime("%Y-%m-%d")
                current_price = current_data["close"]

                ma5 = current_data["ma5"]
                ma20 = current_data["ma20"]
                rsi = current_data["rsi"]
                atr = current_data.get("atr", 0)

                # 跳过无效数据
                if pd.isna(ma5) or pd.isna(ma20) or pd.isna(rsi):
                    strategy.update_portfolio_value(current_date, current_price)
                    continue

                # 使用模型进行真实预测
                try:
                    # 确保模型已加载
                    self._ensure_model_loaded()

                    # 获取历史60天数据
                    history_data = df.iloc[i - time_steps : i].copy()

                    # 计算技术指标特征
                    df_features = self.features.compute_features(history_data)

                    # 获取特征列
                    feature_cols = self.features.get_feature_columns()

                    # 获取最后60天的特征
                    if len(df_features) >= time_steps:
                        features = df_features[feature_cols].values[-time_steps:]
                    else:
                        features = df_features[feature_cols].values

                    # 模型预测
                    predicted_prices = self.model_loader.predict(features)
                    # 使用第一天的预测价格
                    predicted_price = float(predicted_prices[0])

                except Exception as e:
                    logger.warning(f"模型预测失败: {e}，使用简化预测")
                    # 如果模型预测失败，使用简化预测
                    predicted_price = current_price * 1.01

                # 交易决策
                if strategy.position == 0:
                    # 没有持仓，检查是否买入
                    should_buy, predicted_return = strategy.should_buy(
                        current_price, predicted_price, ma5, ma20, rsi
                    )
                    if should_buy:
                        # 使用半仓
                        quantity = (
                            int((strategy.cash * 0.5) / current_price / 100) * 100
                        )
                        if quantity > 0:
                            strategy.execute_trade(
                                current_date, current_price, "buy", quantity
                            )
                else:
                    # 有持仓，检查是否卖出（传入ATR用于动态止损）
                    should_sell = strategy.should_sell(
                        current_price, predicted_price, ma5, rsi, atr
                    )
                    if should_sell:
                        strategy.execute_trade(current_date, current_price, "sell")

                # 更新组合价值
                strategy.update_portfolio_value(current_date, current_price)

            # 计算回测指标
            result = self._calculate_metrics(strategy, initial_capital)
            logger.info(f"回测完成: 总收益率={result['total_return']:.2f}%")

            # 回测完成后清除模型，释放显存
            self.model_loader.clear_model()

            return result

        except Exception as e:
            logger.error(f"回测失败: {e}")
            raise

    def _calculate_rsi(self, series: pd.Series, period: int = 14) -> pd.Series:
        """计算RSI"""
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """
        计算ATR（平均真实波幅）

        ATR = Average(True Range)
        True Range = max(当日高点-当日低点, |当日高点-前日收盘|, |当日低点-前日收盘|)
        """
        high = df["high"]
        low = df["low"]
        prev_close = df["close"].shift(1)

        tr1 = high - low
        tr2 = abs(high - prev_close)
        tr3 = abs(low - prev_close)

        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = true_range.rolling(period).mean()

        return atr

    def _calculate_metrics(
        self, strategy: TradingStrategy, initial_capital: float
    ) -> Dict[str, Any]:
        """计算回测指标"""
        if not strategy.portfolio_values:
            return {
                "total_return": 0,
                "annualized_return": 0,
                "sharpe_ratio": 0,
                "max_drawdown": 0,
                "win_rate": 0,
                "total_trades": 0,
                "trades": [],
                "portfolio_values": [],
                "dates": [],
                "close_prices": [],
            }

        portfolio_values = np.array(strategy.portfolio_values)
        dates = strategy.dates
        close_prices = strategy.close_prices

        # 总收益率（转换为百分比）
        final_value = portfolio_values[-1]
        total_return = (final_value - initial_capital) / initial_capital * 100

        # 年化收益率
        if len(dates) > 1:
            days = (pd.to_datetime(dates[-1]) - pd.to_datetime(dates[0])).days
            years = days / 365
            annualized_return = (
                (final_value / initial_capital) ** (1 / years) - 1 if years > 0 else 0
            )
        else:
            annualized_return = 0

        # 夏普比率 (简化版)
        returns = np.diff(portfolio_values) / portfolio_values[:-1]
        sharpe_ratio = (
            np.mean(returns) / np.std(returns) * np.sqrt(252)
            if np.std(returns) > 0
            else 0
        )

        # 最大回撤
        cummax = np.maximum.accumulate(portfolio_values)
        drawdowns = (cummax - portfolio_values) / cummax
        max_drawdown = np.max(drawdowns)

        # 胜率 & 计算每笔交易的盈亏
        winning_trades = 0
        total_trades = len(strategy.trades)
        enriched_trades = []
        for i in range(len(strategy.trades) - 1):
            if strategy.trades[i]["action"] == "BUY":
                buy_trade = dict(strategy.trades[i])
                buy_price = buy_trade["price"]
                for j in range(i + 1, len(strategy.trades)):
                    if strategy.trades[j]["action"] == "SELL":
                        sell_trade = dict(strategy.trades[j])
                        sell_price = sell_trade["price"]
                        trade_return = (sell_price - buy_price) / buy_price * 100
                        sell_trade["return"] = round(trade_return, 2)
                        sell_trade["profit"] = round(
                            (sell_price - buy_price) * sell_trade["quantity"], 2
                        )
                        enriched_trades.append(buy_trade)
                        enriched_trades.append(sell_trade)
                        if sell_price > buy_price:
                            winning_trades += 1
                        break

        win_rate = winning_trades / (total_trades / 2) if total_trades > 0 else 0

        return {
            "total_return": float(total_return),
            "annualized_return": float(annualized_return),
            "sharpe_ratio": float(sharpe_ratio),
            "max_drawdown": float(max_drawdown),
            "win_rate": float(win_rate),
            "total_trades": total_trades,
            "trades": enriched_trades if enriched_trades else strategy.trades,
            "portfolio_values": strategy.portfolio_values,
            "dates": dates,
            "close_prices": close_prices,
        }

    def _convert_to_baostock_code(self, stock_code: str) -> str:
        """转换股票代码为 baostock 格式"""
        if stock_code.startswith("6"):
            return f"{stock_code}.sh"
        elif stock_code.startswith(("0", "3")):
            return f"{stock_code}.sz"
        else:
            return stock_code
