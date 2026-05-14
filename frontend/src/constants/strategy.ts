export const STRATEGY_METADATA: Record<string, { name: string; description: string; color: string }> = {
  'MA Cross': {
    name: 'MA Cross',
    description: 'Moving Average Crossover strategy using short and long period MA signals',
    color: '#0071e3'
  },
  'Mean Reversion': {
    name: 'Mean Reversion',
    description: 'Buy when price deviates below moving average, sell when above',
    color: '#34c759'
  },
  'Momentum': {
    name: 'Momentum',
    description: 'Follow strong price trends using momentum indicators',
    color: '#ff9500'
  },
  'Breakout': {
    name: 'Breakout',
    description: 'Trade price breakouts above resistance or below support levels',
    color: '#ff3b30'
  },
  'RSI Reversal': {
    name: 'RSI Reversal',
    description: 'Buy oversold (RSI<30) and sell overbought (RSI>70) conditions',
    color: '#af52de'
  },
  'MACD Cross': {
    name: 'MACD Cross',
    description: 'Trade MACD line crossovers with signal line',
    color: '#5856d6'
  },
  'Dual Thrust': {
    name: 'Dual Thrust',
    description: 'Classic breakout strategy using yesterday\'s price range',
    color: '#ff2d55'
  },
  'lstm_5d': {
    name: 'LSTM 5D',
    description: 'Predict 5-day close price and generate threshold-based signals',
    color: '#0a84ff'
  }
}

export const COMPARE_COLORS = ['#0071e3', '#34c759', '#ff9500', '#ff3b30', '#af52de', '#5856d6', '#ff2d55', '#0a84ff']