export type StrategyCategory = 'trend' | 'reversal' | 'breakout' | 'ai'

export interface StrategyMeta {
  name: string
  description: string
  color: string
  category: StrategyCategory
}

/**
 * 策略展示元数据（中文名/说明 + 分类）。
 * key 与后端注册名一致（见 backend/app/services/strategy/strategies.py），
 * 未在此登记的策略回退到后端返回的 name/description。
 */
export const STRATEGY_METADATA: Record<string, StrategyMeta> = {
  ma_cross: {
    name: '均线交叉',
    description: '短期均线上穿长期均线买入，下穿卖出，顺势跟踪趋势',
    color: '#0071e3',
    category: 'trend'
  },
  mean_reversion: {
    name: '均值回归',
    description: '价格偏离均线过远时反向交易，等待回归均值',
    color: '#34c759',
    category: 'reversal'
  },
  momentum: {
    name: '动量策略',
    description: '跟踪强势上涨趋势，动量强劲时顺势持有',
    color: '#ff9500',
    category: 'trend'
  },
  breakout: {
    name: '突破策略',
    description: '价格突破关键阻力位买入，跌破支撑位卖出',
    color: '#ff3b30',
    category: 'breakout'
  },
  rsi_reversal: {
    name: 'RSI 反转',
    description: 'RSI 超卖（<30）买入、超买（>70）卖出，捕捉反转',
    color: '#af52de',
    category: 'reversal'
  },
  macd_cross: {
    name: 'MACD 交叉',
    description: 'MACD 快慢线金叉买入、死叉卖出',
    color: '#5856d6',
    category: 'trend'
  },
  dual_thrust: {
    name: '双重推进',
    description: '经典日内突破策略，基于昨日价格区间设定上下轨',
    color: '#ff2d55',
    category: 'breakout'
  },
  turtle_trading: {
    name: '海龟交易',
    description: '趋势跟随经典策略：通道突破入场，移动止损出场',
    color: '#00c7be',
    category: 'trend'
  },
  bollinger_breakout: {
    name: '布林带突破',
    description: '价格突破布林带上轨/下轨时顺势入场',
    color: '#ff9f0a',
    category: 'breakout'
  },
  donchian_channel: {
    name: '唐奇安通道',
    description: '突破 N 日最高价买入、跌破 N 日最低价卖出',
    color: '#bf5af2',
    category: 'breakout'
  },
  aberration: {
    name: '奇异波动',
    description: '通道与波动率结合的突破型策略',
    color: '#64d2ff',
    category: 'breakout'
  },
  keltner_channel: {
    name: '肯特纳通道',
    description: '利用肯特纳通道判断趋势方向并捕捉突破',
    color: '#ff6b6b',
    category: 'breakout'
  },
  macd_divergence: {
    name: 'MACD 背离',
    description: '价格与 MACD 柱状图背离时捕捉反转信号',
    color: '#8e8e93',
    category: 'reversal'
  },
  lstm_5d: {
    name: 'LSTM 5日预测',
    description: '深度学习预测未来 5 日收盘价，按阈值生成买卖信号',
    color: '#0a84ff',
    category: 'ai'
  }
}

export const STRATEGY_CATEGORIES: { key: StrategyCategory; label: string }[] = [
  { key: 'trend', label: '趋势' },
  { key: 'reversal', label: '震荡' },
  { key: 'breakout', label: '突破' },
  { key: 'ai', label: 'AI' }
]

export const COMPARE_COLORS = ['#0071e3', '#34c759', '#ff9500', '#ff3b30', '#af52de', '#5856d6', '#ff2d55', '#0a84ff']
