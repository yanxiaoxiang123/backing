import type { Page } from '@playwright/test'

// Browser verification only. Application screens continue to use their existing APIs.
export const stocks = [
  {
    id: 1,
    code: 'sh.600000',
    name: '浦发银行',
    market: 'sh',
    list_date: '1999-11-10',
    created_at: '2026-01-01',
  },
  {
    id: 2,
    code: 'sz.000002',
    name: '万科A',
    market: 'sz',
    list_date: '1991-01-29',
    created_at: '2026-01-01',
  },
  {
    id: 3,
    code: 'sh.600036',
    name: '招商银行',
    market: 'sh',
    list_date: '2002-04-09',
    created_at: '2026-01-01',
  },
]
export const bars = Array.from({ length: 30 }, (_, index) => ({
  date: `2026-10-${String(index + 1).padStart(2, '0')}`,
  open: 10 + index * 0.02,
  close: 10.05 + index * 0.02 + Math.sin(index) * 0.06,
  high: 10.2 + index * 0.02,
  low: 9.9 + index * 0.02,
  volume: 1200000 + index * 10000,
  amount: 12000000 + index * 100000,
}))
export const strategies = [
  {
    name: 'ma_cross',
    description: '均线交叉趋势跟踪',
    parameters: {
      short_window: {
        type: 'input',
        default: 5,
        min: 2,
        max: 30,
        description: '短期窗口',
      },
      long_window: {
        type: 'input',
        default: 20,
        min: 10,
        max: 120,
        description: '长期窗口',
      },
    },
  },
  {
    name: 'momentum',
    description: '跟随价格动量',
    parameters: {
      lookback: { type: 'input', default: 20, min: 5, max: 60 },
    },
  },
  {
    name: 'rsi_reversal',
    description: 'RSI 超买超卖',
    parameters: {
      period: { type: 'input', default: 14, min: 5, max: 30 },
    },
  },
]
const metrics = {
  total_return: 5.2,
  annual_return: 5.2,
  sharpe_ratio: 0.87,
  max_drawdown: 3.1,
  win_rate: 50,
  total_trades: 2,
  profit_factor: 1.4,
  total_fees: 13,
}
export const trades = [
  {
    id: 1,
    date: '2026-10-03',
    trade_date: '2026-10-03',
    action: 'buy',
    price: 10.1,
    quantity: 1000,
    amount: 10100,
    fees: 5,
  },
  {
    id: 2,
    date: '2026-10-28',
    trade_date: '2026-10-28',
    action: 'sell',
    price: 10.7,
    quantity: 1000,
    amount: 10700,
    fees: 8,
  },
]
const values = bars.map((bar, index) => ({
  date: bar.date,
  total_value: 100000 + index * 180,
  cash: 89900,
  receivable: 0,
  position_value: 10100 + index * 180,
  position: 1000,
  positions: { 'sh.600000': { quantity: 1000, pending_shares: 0, close: bar.close } },
}))
export const backtest = {
  id: 41,
  result_id: 41,
  success: true,
  stock_code: 'sh.600000',
  strategy_name: 'ma_cross',
  start_date: '2025-11-04',
  end_date: '2026-11-04',
  initial_capital: 100000,
  final_capital: 105200,
  created_at: '2026-11-05T04:30:00Z',
  ...metrics,
  metrics,
  trades,
  portfolio_values: values,
  parameters: { short_window: 5, long_window: 20 },
  execution_metadata: {
    corporate_action_mode: 'verified',
    dividend_tax_rate: 0,
    data_provenance: { adjustment: 'raw' },
  },
}
export const portfolio = {
  experiment_id: 'portfolio-review',
  name: '银行股配置研究',
  created_at: '2026-11-05T04:30:00Z',
  snapshot_sha256: 'saved-experiment-snapshot-for-browser-verification',
  request: {
    name: '银行股配置研究',
    weights: { 'sh.600000': 0.5, 'sh.600036': 0.5 },
    start_date: '2025-11-04',
    end_date: '2026-11-04',
    initial_capital: 100000,
    rebalance: 'monthly',
    corporate_action_mode: 'verified',
    dividend_tax_rate: 0,
    costs: {
      commission_rate: 0.00025,
      minimum_commission: 5,
      sell_tax_rate: 0.0005,
      transfer_rate: 0.00001,
      slippage_rate: 0.0001,
      max_participation: 0.1,
      lot_size: 100,
    },
  },
  metrics,
  result: {
    initial_capital: 100000,
    final_capital: 105200,
    engine_version: 'native',
    metrics,
    portfolio_values: values,
    trades: trades.map((trade) => ({ ...trade, stock_code: 'sh.600000' })),
    unfilled_orders: [],
    limitations: [],
  },
}
const selection = {
  stock_code: 'sh.600000',
  stock_name: '浦发银行',
  close: 10.7,
  volume: 1200000,
  change_pct: 1.1,
  ma5: 10.6,
  ma10: 10.4,
  ma20: 10.2,
  macd_dif: 0.2,
  macd_dea: 0.1,
  macd_hist: 0.2,
  rsi: 56,
  volume_ratio: 1.2,
  composite_score: 78,
  ai_signal: 'hold',
  ai_confidence: 0.72,
  ai_reason: '价格处于短期均线上方，继续核对量能与回撤。',
}

export async function mockResearchApi(page: Page, options: { empty?: boolean } = {}) {
  const requests: Array<{
    path: string
    method: string
    body: Record<string, unknown> | null
  }> = []
  let watchlist = options.empty
    ? []
    : stocks.slice(0, 2).map((stock) => ({
        id: stock.id,
        stock_code: stock.code,
        stock_name: stock.name,
        added_at: '2026-11-04T00:00:00Z',
      }))
  await page.routeWebSocket('**/api/v1/ws/**', (socket) => socket.close())
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname.replace(/\/$/, '')
    const method = request.method()
    const body = request.postData()
      ? (request.postDataJSON() as Record<string, unknown>)
      : null
    requests.push({ path, method, body })
    let data: unknown = {}
    let headers: Record<string, string> | undefined
    if (path.endsWith('/auth/me')) data = { authenticated: true }
    else if (path.endsWith('/paper/alerts')) data = { alerts: [] }
    else if (path.endsWith('/jobs/metrics'))
      data = { counters: [], durations: [], started_at: '2026-11-05T00:00:00Z' }
    else if (path.endsWith('/agent-chats/status'))
      data = { backend: 'native', available: true }
    else if (path.endsWith('/agent-chats')) data = { threads: [], total: 0 }
    else if (path.endsWith('/agent/history'))
      data = options.empty
        ? []
        : [
            {
              id: 1,
              stock_code: 'sh.600000',
              stock_name: '浦发银行',
              analysis_date: '2026-11-05',
              mode: 'quick',
              final_signal: 'hold',
              final_confidence: 0.72,
              final_reason:
                '趋势与量能仍需交叉验证。先确认数据覆盖，再比较策略回撤与交易成本。',
              created_at: '2026-11-05T04:00:00Z',
              duration_s: 12,
            },
          ]
    else if (path.endsWith('/watchlist') && method === 'GET')
      data = { items: watchlist, total: watchlist.length }
    else if (path.endsWith('/watchlist') && method === 'POST') {
      const stock = stocks.find((item) => item.code === body?.stock_code)!
      watchlist = [
        ...watchlist,
        {
          id: stock.id,
          stock_code: stock.code,
          stock_name: stock.name,
          added_at: '2026-11-05T00:00:00Z',
        },
      ]
      data = watchlist[watchlist.length - 1]
    } else if (path.includes('/watchlist/') && method === 'DELETE') {
      watchlist = watchlist.filter(
        (item) => item.stock_code !== decodeURIComponent(path.split('/').pop()!),
      )
      data = { success: true }
    } else if (path.endsWith('/stocks')) {
      const search = url.searchParams.get('search')?.toLowerCase() || ''
      const market = url.searchParams.get('market')
      data = stocks.filter(
        (stock) =>
          `${stock.name} ${stock.code}`.toLowerCase().includes(search) &&
          (!market || stock.market === market),
      )
      headers = { 'x-total-count': String((data as unknown[]).length) }
    } else if (path.endsWith('/overview'))
      data = {
        stock: stocks[0],
        watchlisted: true,
        recent_analysis: [],
        technical: null,
        quote: {
          ...stocks[0],
          current_price: 10.7,
          high: 10.9,
          low: 10.5,
          volume: 1200000,
          change: 0.1,
          change_percent: 0.94,
        },
      }
    else if (path.includes('/stocks/') && path.endsWith('/kline')) data = bars
    else if (path.includes('/stocks/'))
      data = stocks.find((stock) => path.endsWith(stock.code)) || stocks[0]
    else if (path.endsWith('/data/quality'))
      data = {
        total_stocks: 5200,
        covered_stocks: 5100,
        missing_stocks: 100,
        coverage_pct: 98.1,
        invalid_bars: 0,
        total_bars: 2000000,
        raw_covered_stocks: 5100,
        versioned_bars: 2000000,
        calendar_rows: 5000,
      }
    else if (
      path.endsWith('/data/history/sync') ||
      path.endsWith('/sync/stocks') ||
      path.endsWith('/sync/kline')
    )
      data = { job_id: 'research-sync', message: '已排队' }
    else if (path.includes('/jobs/'))
      data = {
        id: 'research-sync',
        status: 'completed',
        progress: 1,
        message: '已完成',
        result: {
          stocks_synced: 3,
          klines_synced: 30,
          message: '同步完成',
          success: true,
        },
        payload: {},
        updated_at: '2026-11-05T04:30:00',
      }
    else if (path.endsWith('/realtime/indices'))
      data = {
        success: true,
        data: options.empty
          ? []
          : [
              {
                symbol: 'sh.000001',
                name: '上证指数',
                close: 3200,
                prev_close: 3188,
                change: 12,
                change_percent: 0.38,
              },
              {
                symbol: 'sz.399001',
                name: '深证成指',
                close: 10320,
                prev_close: 10340,
                change: -20,
                change_percent: -0.19,
              },
              {
                symbol: 'sz.399006',
                name: '创业板指',
                close: 2100,
                prev_close: 2090,
                change: 10,
                change_percent: 0.48,
              },
            ],
      }
    else if (path.endsWith('/realtime/quotes'))
      data = {
        success: true,
        stale: false,
        data: watchlist.map((stock, index) => ({
          symbol: stock.stock_code,
          open: 10,
          close: 10.7 - index,
          high: 10.9,
          low: 9.5,
          change: index ? -0.1 : 0.1,
          change_percent: index ? -1.1 : 0.94,
          volume: 1200000,
          amount: 12000000,
          prev_close: 10.6,
        })),
      }
    else if (path.includes('/realtime/'))
      data = {
        success: true,
        code: stocks[0].code,
        stale: false,
        data: options.empty ? [] : bars,
      }
    else if (path.endsWith('/strategies')) data = strategies
    else if (path.endsWith('/strategies/signals'))
      data = {
        success: true,
        data: bars.map((bar, index) => ({
          date: bar.date,
          close: bar.close,
          signal: index === 2 ? 1 : index === 27 ? -1 : 0,
        })),
        stats: {
          total_buy_signals: 1,
          total_sell_signals: 1,
          total_trades: 1,
          win_rate: 100,
          avg_holding_days: 25,
          avg_return_per_trade: 5.2,
          profit_ratio: 1.4,
          max_win: 5.2,
          max_loss: 0,
          consecutive_wins: 1,
          consecutive_losses: 0,
        },
      }
    else if (path.endsWith('/strategies/backtest')) data = backtest
    else if (path.endsWith('/strategies/compare'))
      data = {
        success: true,
        total_strategies: 3,
        results: strategies.map((strategy) => ({
          strategy_name: strategy.name,
          metrics,
          equity_curve: values.map((point) => ({
            date: point.date,
            value: point.total_value,
          })),
        })),
      }
    else if (path.endsWith('/backtest/results')) {
      data = options.empty ? [] : [backtest]
      headers = { 'x-total-count': options.empty ? '0' : '1' }
    } else if (/\/backtest\/\d+$/.test(path)) data = backtest
    else if (path.endsWith('/screener/history'))
      data = options.empty
        ? []
        : [
            {
              id: 'screen-review',
              status: 'completed',
              progress: 100,
              created_at: '2026-11-05T04:00:00',
              result: { success: true, total_scanned: 5100, results: [selection] },
            },
          ]
    else if (path.endsWith('/screener/submit')) data = { job_id: 'screen-run' }
    else if (path.endsWith('/screener/screen-run'))
      data = {
        id: 'screen-run',
        status: 'completed',
        progress: 1,
        result: {
          success: true,
          total_scanned: 5100,
          results: options.empty ? [] : [selection],
        },
      }
    else if (path.endsWith('/portfolio-research') && method === 'GET')
      data = { total: options.empty ? 0 : 1, items: options.empty ? [] : [portfolio] }
    else if (path.endsWith('/portfolio-research') && method === 'POST')
      data = { ...portfolio, request: body }
    else if (path.endsWith('/replay')) data = { reproduced: true }
    else if (path.includes('/portfolio-research/')) data = portfolio
    else if (path.endsWith('/dl/models'))
      data = {
        models: [
          {
            id: 'kronos-small',
            name: 'Kronos-small',
            available: true,
            min_context: 60,
            max_context: 512,
            min_horizon: 1,
            max_horizon: 30,
          },
        ],
        remote: { available: true },
      }
    await route.fulfill({ json: data, headers })
  })
  return requests
}
