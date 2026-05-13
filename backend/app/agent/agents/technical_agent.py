# -*- coding: utf-8 -*-
"""Technical Agent - 技术分析 Agent"""

import logging
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.agent.agents.base_agent import BaseAgent
from app.agent.llm_adapter import LLMToolAdapter
from app.agent.protocols import AgentContext, AgentOpinion
from app.agent.tools.registry import ToolRegistry
from app.config import SessionLocal
from app.models.models import DailyKline

logger = logging.getLogger(__name__)


class TechnicalAgent(BaseAgent):
    """技术分析 Agent"""

    agent_name = "technical"

    def __init__(
        self,
        tool_registry: ToolRegistry,
        llm_adapter: LLMToolAdapter,
    ):
        super().__init__(tool_registry, llm_adapter)

    def system_prompt(self, ctx: AgentContext) -> str:
        return """你是技术分析专家。你需要分析股票的技术面数据，包括：

1. 移动平均线 (MA5, MA10, MA20, MA60)
2. MACD 指标
3. KDJ 指标
4. RSI 指标
5. 成交量分析
6. 均线排列判断

请根据提供的 K 线数据，进行技术分析并给出：
- 技术面信号：buy（买入）/ sell（卖出）/ hold（持有）
- 置信度：0-1 之间
- 分析理由：详细的技术分析说明

输出格式要求：
请以 JSON 格式输出，包含以下字段：
{
    "signal": "buy/sell/hold",
    "confidence": 0.0-1.0,
    "reason": "分析理由",
    "indicators": {各项技术指标}
}"""

    def build_user_message(self, ctx: AgentContext) -> str:
        stock_code = ctx.stock_code

        # 从数据库获取 K 线数据
        kline_data = self._get_kline_data(stock_code)

        return f"""请分析股票 {stock_code} 的技术面：

{kline_data}

请给出技术分析结论，包括信号、置信度和理由。"""

    def _get_kline_data(self, stock_code: str, days: int = 60) -> str:
        """获取 K 线数据"""
        db = SessionLocal()
        try:
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days)

            klines = (
                db.query(DailyKline)
                .filter(
                    DailyKline.stock_code == stock_code,
                    DailyKline.date >= start_date,
                )
                .order_by(DailyKline.date.desc())
                .limit(days)
                .all()
            )

            if not klines:
                return f"未找到股票 {stock_code} 的 K 线数据"

            # 计算技术指标
            data = self._calculate_indicators(klines)

            return json.dumps(data, ensure_ascii=False, indent=2, default=str)

        finally:
            db.close()

    def _calculate_indicators(self, klines: List[DailyKline]) -> Dict[str, Any]:
        """计算技术指标"""
        # 按日期正序排列
        sorted_klines = sorted(klines, key=lambda x: x.date)

        closes = [k.close for k in sorted_klines]
        volumes = [k.volume for k in sorted_klines]
        highs = [k.high for k in sorted_klines]
        lows = [k.low for k in sorted_klines]

        # 计算 MA
        ma5 = self._ma(closes, 5)
        ma10 = self._ma(closes, 10)
        ma20 = self._ma(closes, 20)
        ma60 = self._ma(closes, 60) if len(closes) >= 60 else None

        # 计算 MACD
        macd = self._macd(closes)

        # 计算 KDJ
        kdj = self._kdj(highs, lows, closes)

        # 计算 RSI
        rsi6 = self._rsi(closes, 6)
        rsi12 = self._rsi(closes, 12)

        # 成交量变化
        vol_change = 0
        if len(volumes) >= 2:
            vol_change = (
                (volumes[0] - volumes[1]) / volumes[1] * 100 if volumes[1] else 0
            )

        # 均线排列
        ma_arrangement = "unknown"
        if ma5 and ma10 and ma20:
            if ma5 > ma10 > ma20:
                ma_arrangement = "bullish"  # 多头排列
            elif ma5 < ma10 < ma20:
                ma_arrangement = "bearish"  # 空头排列
            else:
                ma_arrangement = "mixed"  # 混乱

        # 最近5天数据
        recent = []
        for k in sorted_klines[:5]:
            recent.append(
                {
                    "date": str(k.date),
                    "open": k.open,
                    "high": k.high,
                    "low": k.low,
                    "close": k.close,
                    "volume": k.volume,
                }
            )

        return {
            "recent_klines": recent,
            "ma": {
                "MA5": round(ma5, 2) if ma5 else None,
                "MA10": round(ma10, 2) if ma10 else None,
                "MA20": round(ma20, 2) if ma20 else None,
                "MA60": round(ma60, 2) if ma60 else None,
                "arrangement": ma_arrangement,
            },
            "macd": {
                "dif": round(macd["dif"], 2) if macd.get("dif") else None,
                "dea": round(macd["dea"], 2) if macd.get("dea") else None,
                "histogram": round(macd["histogram"], 2)
                if macd.get("histogram")
                else None,
            },
            "kdj": {
                "k": round(kdj["k"], 2) if kdj.get("k") else None,
                "d": round(kdj["d"], 2) if kdj.get("d") else None,
                "j": round(kdj["j"], 2) if kdj.get("j") else None,
            },
            "rsi": {
                "rsi6": round(rsi6, 2) if rsi6 else None,
                "rsi12": round(rsi12, 2) if rsi12 else None,
            },
            "volume": {
                "latest": volumes[0] if volumes else 0,
                "change_pct": round(vol_change, 2),
            },
            "price": {
                "latest": closes[0] if closes else 0,
                "change_pct": round((closes[0] - closes[1]) / closes[1] * 100, 2)
                if len(closes) >= 2
                else 0,
            },
        }

    def _ma(self, data: List[float], period: int) -> Optional[float]:
        """计算移动平均"""
        if len(data) < period:
            return None
        return sum(data[:period]) / period

    def _macd(
        self, data: List[float], fast: int = 12, slow: int = 26, signal: int = 9
    ) -> Dict[str, float]:
        """计算 MACD"""
        if len(data) < slow:
            return {"dif": None, "dea": None, "histogram": None}

        ema_fast = self._ema(data, fast)
        ema_slow = self._ema(data, slow)

        dif = ema_fast - ema_slow

        # 简化计算 DEA
        dea = dif * 0.9  # 简化

        return {
            "dif": dif,
            "dea": dea,
            "histogram": dif - dea,
        }

    def _ema(self, data: List[float], period: int) -> float:
        """计算指数移动平均"""
        if len(data) < period:
            return sum(data) / len(data)
        multiplier = 2 / (period + 1)
        ema = sum(data[:period]) / period
        for price in data[period:]:
            ema = (price - ema) * multiplier + ema
        return ema

    def _kdj(
        self,
        highs: List[float],
        lows: List[float],
        closes: List[float],
        period: int = 9,
    ) -> Dict[str, float]:
        """计算 KDJ"""
        if len(closes) < period:
            return {"k": 50, "d": 50, "j": 50}

        recent_highs = highs[:period]
        recent_lows = lows[:period]

        highest_high = max(recent_highs)
        lowest_low = min(recent_lows)

        if highest_high == lowest_low:
            rsv = 50
        else:
            rsv = (closes[0] - lowest_low) / (highest_high - lowest_low) * 100

        # 简化 K, D 计算
        k = rsv
        d = k * 0.9 + 50 * 0.1
        j = 3 * k - 2 * d

        return {"k": k, "d": d, "j": j}

    def _rsi(self, data: List[float], period: int = 6) -> Optional[float]:
        """计算 RSI"""
        if len(data) <= period:
            return None

        gains = []
        losses = []
        for i in range(1, period + 1):
            change = data[i - 1] - data[i]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))

        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period

        if avg_loss == 0:
            return 100

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def post_process(self, ctx: AgentContext, raw_text: str) -> Optional[AgentOpinion]:
        """后处理 LLM 响应"""
        try:
            # 尝试解析 JSON
            import re

            match = re.search(r"\{.*\}", raw_text, re.DOTALL)
            if match:
                data = json.loads(match.group())
                return AgentOpinion(
                    agent_name=self.agent_name,
                    signal=data.get("signal", "hold"),
                    confidence=data.get("confidence", 0.5),
                    reason=data.get("reason", ""),
                    metadata=data.get("indicators", {}),
                )
        except Exception as e:
            logger.error(f"Failed to parse technical analysis: {e}")

        # 回退：基于指标生成简单结论
        return self._fallback_opinion(ctx)

    def _fallback_opinion(self, ctx: AgentContext) -> AgentOpinion:
        """回退：基于数据生成结论"""
        # 这里可以添加简单的规则来生成结论
        return AgentOpinion(
            agent_name=self.agent_name,
            signal="hold",
            confidence=0.5,
            reason="需要进一步分析",
            metadata={},
        )
