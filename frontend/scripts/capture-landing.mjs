import { chromium } from '@playwright/test'
import { spawn } from 'node:child_process'
import { mkdir, readFile } from 'node:fs/promises'
import { resolve } from 'node:path'

const BASE = process.env.LANDING_BASE_URL || 'http://127.0.0.1:5174'
const ASSETS = resolve('public/welcome/assets')
const OG_TEMPLATE = resolve('scripts/og-template.html')

const json = (route, body) =>
  route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(body),
  })

const bars = Array.from({ length: 365 }, (_, index) => {
  const date = new Date(Date.UTC(2024, 0, 2 + index))
  const close =
    1600 + Math.sin(index / 12) * 40 + index * 0.8 + Math.sin(index / 3) * 6
  const value = Number(close.toFixed(2))
  return {
    date: date.toISOString().slice(0, 10),
    open: Number((value - 3).toFixed(2)),
    high: Number((value + 8).toFixed(2)),
    low: Number((value - 9).toFixed(2)),
    close: value,
    volume: 1200000 + index * 1000,
    amount: 1900000000,
    symbol: '600519',
  }
})

const trendDates = bars.slice(-30).map((bar) => bar.date)
const trendValues = bars.slice(-30).map((bar) => bar.close)

const watchlistItems = [
  {
    id: 1,
    stock_code: '600519',
    stock_name: '贵州茅台',
    added_at: '2024-01-02T00:00:00Z',
  },
  {
    id: 2,
    stock_code: '000001',
    stock_name: '平安银行',
    added_at: '2024-01-03T00:00:00Z',
  },
  {
    id: 3,
    stock_code: '300750',
    stock_name: '宁德时代',
    added_at: '2024-01-04T00:00:00Z',
  },
]

const quotes = watchlistItems.map((item, index) => {
  const close = [1888.4, 11.28, 186.72][index]
  const change = [12.6, -0.08, 3.42][index]
  return {
    symbol: item.stock_code,
    open: Number((close - change).toFixed(2)),
    high: Number((close + 6.2).toFixed(2)),
    low: Number((close - 7.4).toFixed(2)),
    close,
    volume: [32100, 1280000, 186000][index],
    amount: [5420000000, 1440000000, 3480000000][index],
    change,
    change_percent: Number(((change / (close - change)) * 100).toFixed(2)),
    prev_close: Number((close - change).toFixed(2)),
  }
})

const realtimeIndices = [
  {
    symbol: '000001',
    name: '上证指数',
    close: 3072.18,
    change: 12.44,
    change_percent: 0.41,
    prev_close: 3059.74,
  },
  {
    symbol: '399001',
    name: '深证成指',
    close: 9684.32,
    change: -21.36,
    change_percent: -0.22,
    prev_close: 9705.68,
  },
  {
    symbol: '399006',
    name: '创业板指',
    close: 1908.75,
    change: 6.82,
    change_percent: 0.36,
    prev_close: 1901.93,
  },
]

const summary = {
  as_of: '2024-12-31T15:00:00Z',
  market_stats: { up: 2864, down: 1921, flat: 168, total: 4953 },
  indices: realtimeIndices.map((index) => ({
    code: index.symbol,
    name: index.name,
    value: index.close,
    change: index.change,
    change_percent: index.change_percent,
  })),
  trend: { name: '上证指数', dates: trendDates, values: trendValues },
  watchlist: watchlistItems.map((item, index) => ({
    id: item.id,
    code: item.stock_code,
    name: item.stock_name,
    current_price: quotes[index].close,
    high: quotes[index].high,
    low: quotes[index].low,
    volume: quotes[index].volume,
    change: quotes[index].change,
    change_percent: quotes[index].change_percent,
  })),
  research_queue: [
    {
      code: '600519',
      name: '贵州茅台',
      reason: '均线多头排列，量能温和放大',
      change_percent: 0.75,
    },
    {
      code: '300750',
      name: '宁德时代',
      reason: '突破 20 日新高，关注回踩确认',
      change_percent: 1.86,
    },
  ],
  recent_activity: [
    {
      id: 'a1',
      title: 'ma_cross 回测完成',
      kind: 'backtest',
      created_at: '2024-12-31T14:20:00Z',
    },
    {
      id: 'a2',
      title: '贵州茅台 AI 分析报告',
      kind: 'analysis',
      created_at: '2024-12-31T11:05:00Z',
    },
  ],
  alerts: [
    {
      id: 1,
      title: '自选股 600519 触及 20 日新高',
      severity: 'info',
      created_at: '2024-12-31T10:15:00Z',
    },
  ],
}

const strategies = [
  [
    'ma_cross',
    '均线交叉：短期均线上穿长期均线买入，下穿卖出',
    {
      short_period: {
        type: 'slider',
        default: 5,
        min: 1,
        max: 30,
        step: 1,
        description: '短期均线天数',
      },
      long_period: {
        type: 'slider',
        default: 20,
        min: 10,
        max: 120,
        step: 1,
        description: '长期均线天数',
      },
    },
  ],
  [
    'momentum',
    '动量：按过去一段时间的涨幅排序',
    {
      lookback: {
        type: 'slider',
        default: 20,
        min: 5,
        max: 60,
        step: 1,
        description: '回看天数',
      },
    },
  ],
  ['macd_cross', 'MACD 金叉买入，死叉卖出', {}],
  ['mean_reversion', '均值回归：偏离均线过远时反向交易', {}],
  ['rsi_reversal', 'RSI 超买超卖反转', {}],
  ['macd_divergence', 'MACD 背离反转', {}],
  ['breakout', '价格突破前高买入', {}],
  ['dual_thrust', 'Dual Thrust 区间突破', {}],
  ['turtle_trading', '海龟交易法则', {}],
  ['bollinger_breakout', '布林带突破', {}],
  ['donchian_channel', '唐奇安通道突破', {}],
  ['aberration', 'Aberration 通道策略', {}],
  ['keltner_channel', '肯特纳通道突破', {}],
].map(([name, description, parameters]) => ({ name, description, parameters }))

const portfolioValues = Array.from({ length: 240 }, (_, index) => {
  const date = new Date(Date.UTC(2024, 0, 2 + index)).toISOString().slice(0, 10)
  const progress = index / 239
  const total = 100000 + progress * 12340 + Math.sin(index / 8) * 900 * (1 - progress)
  const positionValue = total * 0.62
  return {
    date,
    total_value: Number(total.toFixed(2)),
    cash: Number((total - positionValue).toFixed(2)),
    position_value: Number(positionValue.toFixed(2)),
    position: 100,
  }
})

const backtest = {
  success: true,
  result_id: 1287,
  strategy_name: 'ma_cross',
  stock_code: '600519',
  start_date: '2024-01-02',
  end_date: '2024-12-31',
  initial_capital: 100000,
  final_capital: 112340.75,
  trades: [
    { date: '2024-02-06', action: 'buy', price: 1642.3, quantity: 60, amount: 98538 },
    { date: '2024-03-19', action: 'sell', price: 1718.5, quantity: 60, amount: 103110 },
    { date: '2024-05-08', action: 'buy', price: 1665.2, quantity: 62, amount: 103242.4 },
    { date: '2024-06-21', action: 'sell', price: 1742.8, quantity: 62, amount: 108053.6 },
    { date: '2024-08-14', action: 'buy', price: 1698.6, quantity: 64, amount: 108710.4 },
    { date: '2024-10-11', action: 'sell', price: 1786.4, quantity: 64, amount: 114329.6 },
    { date: '2024-11-05', action: 'buy', price: 1742.2, quantity: 65, amount: 113243 },
    { date: '2024-12-24', action: 'sell', price: 1788.9, quantity: 65, amount: 116278.5 },
  ],
  metrics: {
    sharpe_ratio: 1.2345,
    total_return: 12.34,
    annual_return: 11.87,
    max_drawdown: -8.76,
    win_rate: 62.5,
    profit_factor: 1.68,
    total_trades: 8,
  },
  portfolio_values: portfolioValues,
  parameters: { short_period: 5, long_period: 20 },
}

const stockList = {
  items: [
    {
      id: 1,
      code: '600519',
      name: '贵州茅台',
      market: 'SH',
      list_date: '2001-08-27',
      created_at: '2024-01-01T00:00:00Z',
    },
    {
      id: 2,
      code: '000001',
      name: '平安银行',
      market: 'SZ',
      list_date: '1991-04-03',
      created_at: '2024-01-01T00:00:00Z',
    },
  ],
  total: 2,
  nextCursor: null,
}

async function ensureServer() {
  try {
    const response = await fetch(BASE)
    if (response.ok) return null
  } catch {
    // start below
  }
  const server = spawn('npm', ['run', 'dev', '--', '--host', '127.0.0.1'], {
    stdio: 'inherit',
    shell: true,
  })
  for (let attempt = 0; attempt < 90; attempt += 1) {
    await new Promise((resolveDelay) => setTimeout(resolveDelay, 1000))
    try {
      const response = await fetch(BASE)
      if (response.ok) return server
    } catch {
      // keep waiting
    }
  }
  server.kill()
  throw new Error(`Vite dev server did not start at ${BASE}`)
}

async function main() {
  console.log('capture: start')
  await mkdir(ASSETS, { recursive: true })
  const server = await ensureServer()
  console.log('capture: server ready')
  const browser = await chromium.launch()
  try {
    const page = await browser.newPage({
      viewport: { width: 1440, height: 900 },
      deviceScaleFactor: 1,
    })
    page.setDefaultTimeout(20000)
    page.on('pageerror', (error) => {
      console.error('pageerror:', error)
    })
    page.on('requestfailed', (request) => {
      console.error('requestfailed:', request.url(), request.failure()?.errorText)
    })
    await page.addInitScript(() => {
      sessionStorage.setItem(
        'backing_strategies_selectedStrategy',
        JSON.stringify('ma_cross'),
      )
      sessionStorage.setItem('backing_strategies_stockCode', JSON.stringify('600519'))
      sessionStorage.setItem(
        'backing_strategies_dateRange',
        JSON.stringify(['2024-01-02', '2024-12-31']),
      )
      sessionStorage.setItem('backing_strategies_initialCapital', JSON.stringify(100000))
    })
    await page.route('**/api/v1/**', async (route) => {
      const url = new URL(route.request().url())
      const path = url.pathname
      const method = route.request().method()

      if (path === '/api/v1/auth/me') return json(route, { authenticated: true })
      if (path === '/api/v1/watchlist')
        return json(route, {
          items: watchlistItems,
          total: watchlistItems.length,
        })
      if (path === '/api/v1/realtime/indices')
        return json(route, {
          success: true,
          status: 'ok',
          data: realtimeIndices,
        })
      if (path === '/api/v1/realtime/quotes')
        return json(route, { success: true, status: 'ok', data: quotes })
      if (path.startsWith('/api/v1/realtime/'))
        return json(route, {
          success: true,
          status: 'ok',
          code: '600519',
          data: bars,
        })
      if (path === '/api/v1/dashboard') return json(route, summary)
      if (path === '/api/v1/strategies' && method === 'GET')
        return json(route, strategies)
      if (path === '/api/v1/strategies/backtest' && method === 'POST')
        return json(route, backtest)
      if (path === '/api/v1/stocks') return json(route, stockList)
      return json(route, { success: true, data: [] })
    })

    await page.goto(`${BASE}/`, { waitUntil: 'domcontentloaded' })
    console.log('capture: dashboard loaded')
    await page.getByRole('heading', { name: '市场概览' }).waitFor()
    await page.waitForTimeout(600)
    console.log('capture: dashboard ready')
    await page.screenshot({
      path: resolve(ASSETS, 'dashboard.png'),
      clip: { x: 0, y: 80, width: 1440, height: 820 },
    })
    console.log('capture: dashboard screenshot saved')

    await page.goto(`${BASE}/strategies`, { waitUntil: 'domcontentloaded' })
    console.log('capture: strategies loaded')
    const responsePromise = page
      .waitForResponse(
        (response) =>
          response.url().includes('/api/v1/strategies/backtest') &&
          response.request().method() === 'POST',
        { timeout: 15000 },
      )
      .catch((error) => {
        console.error('capture: no backtest response', error.message)
        return null
      })
    await page.getByRole('button', { name: '执行回测' }).click()
    const backtestResponse = await responsePromise
    console.log('capture: backtest response', backtestResponse?.status() ?? 'none')
    await page.waitForSelector('text=回测已保存')
    console.log('capture: backtest finished')
    await page.getByRole('tab', { name: '绩效指标' }).click()
    await page.getByText('总收益率').waitFor()
    await page.waitForTimeout(400)
    await page.screenshot({
      path: resolve(ASSETS, 'strategies.png'),
      clip: { x: 0, y: 80, width: 1440, height: 820 },
    })
    console.log('capture: strategies screenshot saved')

    const ogPage = await browser.newPage({
      viewport: { width: 1200, height: 630 },
      deviceScaleFactor: 1,
    })
    const ogHtml = await readFile(OG_TEMPLATE, 'utf8')
    await ogPage.setContent(ogHtml, { waitUntil: 'load' })
    await ogPage.screenshot({ path: resolve(ASSETS, 'og-image.png') })
    console.log('capture: og image saved')
  } finally {
    await browser.close()
    if (server) server.kill()
  }
}

main().catch((error) => {
  console.error(error)
  process.exitCode = 1
})
