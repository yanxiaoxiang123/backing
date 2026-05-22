import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional, Callable, TYPE_CHECKING

import pandas as pd

from app.services.realtime_service import realtime_service
from app.services.strategy.factors import TechnicalFactors

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from app.models.models import Stock

logger = logging.getLogger(__name__)


class ScreenerService:
    """选股服务 — 并行扫描全市场 + 计算技术指标 + 综合评分排序"""

    def __init__(self):
        self.indicators_weights = {
            'valuation': 0.30,
            'profit': 0.25,
            'technical': 0.25,
            'dividend': 0.20,
        }

    def parallel_scan_stocks(
        self,
        stocks: List["Stock"],
        offset: int = 120,
        max_workers: int = 10,
        progress_callback: Optional[Callable[[str, int, int, str], None]] = None,
    ) -> List[Dict[str, Any]]:
        """并行扫描全市场股票，计算技术指标"""
        results: List[Dict[str, Any]] = []
        total = len(stocks)
        completed = 0

        def process_one(stock: "Stock") -> Optional[Dict[str, Any]]:
            try:
                symbol = stock.code.split('.')[-1] if '.' in stock.code else stock.code
                bars = realtime_service.normalise_bars(symbol=symbol, frequency=9, offset=offset)
                if bars is None or len(bars) < 30:
                    return None
                df = pd.DataFrame(bars)
                df = df.rename(columns={'vol': 'volume'})
                indicators = self._compute_indicators(df)
                indicators['stock_code'] = stock.code
                indicators['stock_name'] = stock.name
                return indicators
            except Exception as e:
                logger.debug(f"Failed to process {stock.code}: {e}")
                return None

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(process_one, s): s for s in stocks}
            for future in as_completed(futures):
                try:
                    result = future.result()
                    completed += 1
                    if result:
                        results.append(result)
                except Exception as e:
                    logger.error(f"Error processing stock: {e}")
                    completed += 1
                    continue  # don't crash the whole scan
                if progress_callback and completed % 50 == 0:
                    progress_callback(
                        'scanning',
                        completed,
                        total,
                        f'正在扫描全市场股票... ({completed}/{total})'
                    )

        return results

    def _compute_indicators(self, df: pd.DataFrame) -> Dict[str, Any]:
        """计算单只股票的所有技术指标"""
        close = df['close']
        volume = df['volume']
        results: Dict[str, Any] = {}

        # 安全获取 Series 最后一个有效值，空/NaN 时返回 None
        def _last(s: pd.Series) -> Optional[float]:
            if s.empty:
                return None
            val = s.iloc[-1]
            return None if pd.isna(val) else float(val)

        # 均线
        results['ma5'] = _last(TechnicalFactors.SMA(close, 5))
        results['ma10'] = _last(TechnicalFactors.SMA(close, 10))
        results['ma20'] = _last(TechnicalFactors.SMA(close, 20))

        # MACD
        macd = TechnicalFactors.MACD(close, 12, 26, 9)
        results['macd_dif'] = _last(macd['dif'])
        results['macd_dea'] = _last(macd['dea'])
        results['macd_hist'] = _last(macd['histogram'])

        # RSI
        results['rsi'] = _last(TechnicalFactors.RSI(close, 14))

        # 成交量比
        vol_ma = TechnicalFactors.VolumeMA(volume, 20)
        latest_vol_ma = _last(vol_ma)
        if latest_vol_ma and latest_vol_ma > 0:
            results['volume_ratio'] = round(_last(volume) / latest_vol_ma, 2) if _last(volume) else 0.0
        else:
            results['volume_ratio'] = 0.0

        # 最新价格和成交量
        results['close'] = _last(df['close'])
        results['volume'] = _last(df['volume'])

        # 涨跌幅
        if len(df) >= 2:
            prev_close = _last(df['close'].iloc[:-1])
            cur_close = _last(df['close'])
            if prev_close and prev_close > 0:
                results['change_pct'] = round((cur_close - prev_close) / prev_close * 100, 2)
            else:
                results['change_pct'] = 0.0
        else:
            results['change_pct'] = 0.0

        # 综合评分
        results['composite_score'] = self._calc_composite_score(results)

        return results

    def _calc_composite_score(self, indicators: Dict[str, Any]) -> float:
        """计算综合评分（0-100）"""
        score = 0.0

        # None → 安全默认值
        ma5 = indicators.get('ma5') or 0
        ma10 = indicators.get('ma10') or 0
        ma20 = indicators.get('ma20') or 0
        macd_hist = indicators.get('macd_hist') or 0
        rsi = indicators.get('rsi') or 50
        volume_ratio = indicators.get('volume_ratio') or 0

        # 技术面 25%
        tech_score = 0
        if ma5 > ma10 > ma20:
            tech_score += 10  # 均线多头
        if macd_hist > 0:
            tech_score += 8  # MACD 红柱
        if rsi < 30:
            tech_score += 7  # RSI 超卖
        elif rsi > 70:
            tech_score += 2  # RSI 超买（轻微负面）
        if volume_ratio > 1.5:
            tech_score += 5  # 成交量放大
        score += tech_score * 0.25 / 30 * 100

        return round(score, 2)

    def filter_and_rank(
        self,
        results: List[Dict[str, Any]],
        progress_callback: Optional[Callable[[str, int, int, str], None]] = None,
    ) -> List[Dict[str, Any]]:
        """过滤 + 评分排序，返回 TOP 5"""
        # 过滤：MA 多头 + MACD 红柱 + 成交量放大
        filtered = [
            r for r in results
            if r.get('ma5', 0) > r.get('ma10', 0) > r.get('ma20', 0)
            and r.get('macd_hist', 0) > 0
            and r.get('volume_ratio', 0) > 1.5
        ]

        logger.info(f"Screener: filtered {len(filtered)} stocks from {len(results)} total")

        if progress_callback:
            progress_callback('scoring', 0, 1, f'符合条件的股票: {len(filtered)} 只')

        # 排序：综合评分降序（不修改原列表）
        sorted_results = sorted(filtered, key=lambda x: x.get('composite_score', 0), reverse=True)

        return sorted_results[:5]


# Singleton
screener_service = ScreenerService()