# Backing 公开落地页 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增一个公开、可索引、零主包影响的 Backing 落地页 `/welcome/`，并把未登录访客与登录后的 `next` 跳转串起来。

**Architecture:** 落地页是 `frontend/public/welcome/` 下的纯静态 HTML/CSS/JS，由 Vite 原样复制到 `dist/welcome/`，不进入 React 主包。未登录重定向、`next` 参数和登录回跳放在现有 `App.tsx` / `Login.tsx` 中，配一个可单测的 `safeNextPath` 工具。截图和 OG 图由开发期 Playwright 脚本生成。

**Tech Stack:** 静态 HTML/CSS/ES2020、Vite 5、React 18、React Router 6、Vitest、Playwright。

**Commit policy:** 本计划不自动 commit。每个任务末尾是检查点，必须停下来向用户汇报；只有用户明确要求时才提交。

---

## 文件结构

**新增**

- `frontend/public/welcome/index.html` — 落地页全文案、meta、JSON-LD、导航、各 section、footer。
- `frontend/public/welcome/landing.css` — 落地页全部样式、响应式、动效、法律页样式。
- `frontend/public/welcome/landing.js` — `next` 传播、移动端菜单、标签逐字、滚动揭示、导航高亮。
- `frontend/public/welcome/assets/dashboard.png` — 真实 Dashboard 截图。
- `frontend/public/welcome/assets/strategies.png` — 真实策略回测截图。
- `frontend/public/welcome/assets/og-image.png` — 1200×630 OG 图。
- `frontend/public/legal/privacy.html` — 隐私说明。
- `frontend/public/legal/terms.html` — 使用条款。
- `frontend/public/favicon.svg` — 品牌 favicon。
- `frontend/public/robots.txt` — 只放行 `/welcome/`。
- `frontend/scripts/capture-landing.mjs` — 截图和 OG 图生成脚本。
- `frontend/scripts/og-template.html` — OG 图模板。
- `frontend/src/utils/nextPath.ts` — `safeNextPath`。
- `frontend/src/utils/nextPath.test.ts` — 单测。
- `frontend/e2e/landing.spec.ts` — 落地页 e2e。
- `frontend/e2e/auth-redirect.spec.ts` — 未登录跳转和登录回跳 e2e。

**修改**

- `frontend/src/pages/Login.tsx` — 读取 `next`，登录后回原路径，增加“了解 Backing”链接。
- `frontend/src/App.tsx` — 未登录整页跳转 `/welcome/?next=...`；处理 `/welcome` 无斜杠。
- `frontend/index.html` — app shell 加 `noindex`，favicon 改为 `/favicon.svg`。
- `frontend/eslint.config.js` — 为 `public/**/*.js` 增加浏览器 globals，为 `scripts/**/*.mjs` 补充 Node globals。

**不修改**

- `frontend/src/styles/*`
- `frontend/vite.config.ts`（除非 `/welcome/` 无法被静态服务，见 Task 10 的兜底）
- 后端、`TradingAgents-astock/`
- 不新增 npm 依赖

---

## Task 1: `safeNextPath` 工具与单测

**Files:**
- Create: `frontend/src/utils/nextPath.test.ts`
- Create: `frontend/src/utils/nextPath.ts`

- [ ] **Step 1: 写失败测试**

创建 `frontend/src/utils/nextPath.test.ts`：

```ts
import { describe, expect, it } from 'vitest'
import { safeNextPath } from './nextPath'

describe('safeNextPath', () => {
  it('accepts same-origin absolute paths', () => {
    expect(safeNextPath('/')).toBe('/')
    expect(safeNextPath('/stocks/600519')).toBe('/stocks/600519')
    expect(safeNextPath('/stocks?code=600519')).toBe('/stocks?code=600519')
  })

  it('rejects protocol-relative and external URLs', () => {
    expect(safeNextPath('//evil.com')).toBeNull()
    expect(safeNextPath('https://evil.com')).toBeNull()
    expect(safeNextPath('/\\evil.com')).toBeNull()
    expect(safeNextPath('javascript:alert(1)')).toBeNull()
  })

  it('rejects empty values', () => {
    expect(safeNextPath(null)).toBeNull()
    expect(safeNextPath(undefined)).toBeNull()
    expect(safeNextPath('')).toBeNull()
  })
})
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd frontend
npx vitest run src/utils/nextPath.test.ts
```

Expected: FAIL，报错 `Cannot find module './nextPath'` 或同等错误。

- [ ] **Step 3: 写最小实现**

创建 `frontend/src/utils/nextPath.ts`：

```ts
/**
 * 只允许站内绝对路径作为登录后的回跳目标。
 * 拒绝协议相对地址（//evil.com）、反斜杠变体（/\evil.com）和外部 URL。
 */
export function safeNextPath(value: string | null | undefined): string | null {
  if (!value) return null
  if (!value.startsWith('/')) return null
  if (value.startsWith('//')) return null
  if (value.startsWith('/\\')) return null
  return value
}
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
npx vitest run src/utils/nextPath.test.ts
```

Expected: PASS，3 个测试全部通过。

- [ ] **Step 5: 检查点**

不要 commit。向用户汇报：`safeNextPath` 已实现，3 个测试通过。等待下一步指令。

---

## Task 2: 生成 Dashboard、策略回测和 OG 图

**Files:**
- Create: `frontend/scripts/og-template.html`
- Create: `frontend/scripts/capture-landing.mjs`
- Create: `frontend/public/welcome/assets/dashboard.png`
- Create: `frontend/public/welcome/assets/strategies.png`
- Create: `frontend/public/welcome/assets/og-image.png`

- [ ] **Step 1: 创建 OG 图模板**

创建 `frontend/scripts/og-template.html`：

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <style>
      * {
        box-sizing: border-box;
      }
      html,
      body {
        margin: 0;
        width: 1200px;
        height: 630px;
      }
      body {
        background: #f3f0ee;
        color: #141413;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC',
          'Microsoft YaHei', sans-serif;
      }
      .card {
        position: relative;
        width: 100%;
        height: 100%;
        padding: 64px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        overflow: hidden;
      }
      .brand {
        display: flex;
        align-items: center;
        gap: 12px;
        font-size: 24px;
        font-weight: 600;
      }
      h1 {
        max-width: 960px;
        margin: 0;
        font-size: 48px;
        line-height: 1;
        font-weight: 600;
      }
      p {
        max-width: 640px;
        margin: 24px 0 0;
        font-size: 20px;
        line-height: 28px;
        color: #696969;
      }
      .tag {
        position: absolute;
        right: 64px;
        top: 64px;
        font-size: 16px;
        font-weight: 600;
        color: #9a3a0a;
      }
      .chart {
        position: absolute;
        right: -40px;
        bottom: -30px;
        width: 560px;
        height: 300px;
        opacity: 0.9;
      }
    </style>
  </head>
  <body>
    <div class="card">
      <div>
        <div class="brand">
          <svg width="32" height="32" viewBox="0 0 20 20" aria-hidden="true">
            <rect x="3" y="9" width="3" height="8" rx="1" fill="#141413"></rect>
            <rect x="8.5" y="5" width="3" height="12" rx="1" fill="#141413"></rect>
            <rect x="14" y="2" width="3" height="15" rx="1" fill="#cf4500"></rect>
          </svg>
          Backing
        </div>
        <h1>从 K 线到模拟成交，<br />把 A 股研究跑成一条可复现的链路</h1>
        <p>回测、参数优化、AI 分析与模拟盘，都在一个工作台里。</p>
      </div>
      <div class="tag">A 股研究台</div>
      <svg class="chart" viewBox="0 0 560 300" aria-hidden="true">
        <path
          d="M0 240 L80 210 L150 225 L230 160 L310 180 L390 110 L470 130 L560 60"
          fill="none"
          stroke="#cf4500"
          stroke-width="3"
          stroke-linecap="round"
          stroke-linejoin="round"
        ></path>
        <path
          d="M0 260 L80 240 L150 250 L230 210 L310 220 L390 180 L470 190 L560 150"
          fill="none"
          stroke="#141413"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
          opacity="0.25"
        ></path>
      </svg>
    </div>
  </body>
</html>
```

- [ ] **Step 2: 创建截图脚本**

创建 `frontend/scripts/capture-landing.mjs`：

```js
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
  await mkdir(ASSETS, { recursive: true })
  const server = await ensureServer()
  const browser = await chromium.launch()
  try {
    const page = await browser.newPage({
      viewport: { width: 1440, height: 900 },
      deviceScaleFactor: 1,
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
    await page.getByRole('heading', { name: '市场概览' }).waitFor()
    await page.waitForTimeout(600)
    await page.screenshot({
      path: resolve(ASSETS, 'dashboard.png'),
      clip: { x: 0, y: 80, width: 1440, height: 820 },
    })

    await page.goto(`${BASE}/strategies`, { waitUntil: 'domcontentloaded' })
    await page.getByRole('button', { name: '执行回测' }).click()
    await page.waitForSelector('text=回测已保存')
    await page.getByRole('tab', { name: '绩效指标' }).click()
    await page.getByText('总收益率').waitFor()
    await page.waitForTimeout(400)
    await page.screenshot({
      path: resolve(ASSETS, 'strategies.png'),
      clip: { x: 0, y: 80, width: 1440, height: 820 },
    })

    const ogPage = await browser.newPage({
      viewport: { width: 1200, height: 630 },
      deviceScaleFactor: 1,
    })
    const ogHtml = await readFile(OG_TEMPLATE, 'utf8')
    await ogPage.setContent(ogHtml, { waitUntil: 'load' })
    await ogPage.screenshot({ path: resolve(ASSETS, 'og-image.png') })
  } finally {
    await browser.close()
    if (server) server.kill()
  }
}

main().catch((error) => {
  console.error(error)
  process.exitCode = 1
})
```

- [ ] **Step 3: 生成图片**

```bash
cd frontend
node scripts/capture-landing.mjs
```

Expected: 脚本启动或复用 `http://127.0.0.1:5174`，生成三张图片，无报错。

- [ ] **Step 4: 检查文件与大小**

```bash
ls -lh public/welcome/assets
```

Expected: 存在 `dashboard.png`、`strategies.png`、`og-image.png`。

如果 `dashboard.png` 或 `strategies.png` 超过 300KB，执行下面的降级：

```bash
ls -l public/welcome/assets/*.png
```

把 `page.screenshot` 改为：

```js
await page.screenshot({
  path: resolve(ASSETS, 'dashboard.png'),
  type: 'jpeg',
  quality: 90,
})
```

并把文件名改为 `.jpg`，同时在 Task 3 的 HTML 里使用 `.jpg`。只有超过 300KB 才这样做。

- [ ] **Step 5: 检查点**

不要 commit。向用户汇报截图和 OG 图已生成，附上文件大小；等待下一步指令。

---

## Task 3: 写失败 e2e 测试（落地页）

**Files:**
- Create: `frontend/e2e/landing.spec.ts`

- [ ] **Step 1: 写测试**

创建 `frontend/e2e/landing.spec.ts`：

```ts
import { expect, test } from '@playwright/test'

test.describe('landing page', () => {
  test.beforeEach(async ({ page }) => {
    await page.route('**/api/v1/auth/me', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ authenticated: false }),
      }),
    )
  })

  test('renders the full landing page without JS', async ({ browser }) => {
    const context = await browser.newContext({ javaScriptEnabled: false })
    const page = await context.newPage()
    await page.goto('/welcome/')
    await expect(page.getByRole('heading', { level: 1 })).toContainText(
      '从 K 线到模拟成交',
    )
    await expect(
      page.getByRole('link', { name: '登录研究工作台' }).first(),
    ).toHaveAttribute('href', '/login')
    await expect(page.locator('.faq-item')).toHaveCount(9)
    await expect(page.getByRole('link', { name: '隐私' })).toHaveAttribute(
      'href',
      '/legal/privacy.html',
    )
    await expect(page.getByRole('link', { name: '条款' })).toHaveAttribute(
      'href',
      '/legal/terms.html',
    )
    await context.close()
  })

  test('propagates next into login links', async ({ page }) => {
    await page.goto('/welcome/?next=%2Fstocks%2F600519')
    await expect(
      page.getByRole('link', { name: '登录研究工作台' }).first(),
    ).toHaveAttribute('href', '/login?next=%2Fstocks%2F600519')
  })

  test('opens and closes the mobile menu with Escape', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 })
    await page.goto('/welcome/')
    const toggle = page.getByRole('button', { name: '打开菜单' })
    await toggle.click()
    const menu = page.locator('#mobile-menu')
    await expect(menu).toBeVisible()
    await expect(page.getByRole('button', { name: '关闭菜单' })).toBeFocused()
    await page.keyboard.press('Escape')
    await expect(menu).toBeHidden()
    await expect(toggle).toBeFocused()
  })

  test('has no horizontal scroll at 375, 768 and 1440', async ({ page }) => {
    for (const width of [375, 768, 1440]) {
      await page.setViewportSize({ width, height: 900 })
      await page.goto('/welcome/')
      const overflow = await page.evaluate(
        () =>
          document.documentElement.scrollWidth >
          document.documentElement.clientWidth,
      )
      expect(overflow).toBe(false)
    }
  })

  test('shows the tagline with reduced motion', async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await page.goto('/welcome/')
    const firstWord = page.locator('.tagline-word').first()
    await expect(firstWord).toBeVisible()
    const opacity = await firstWord.evaluate((element) => getComputedStyle(element).opacity)
    expect(opacity).toBe('1')
  })
})
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd frontend
npx playwright test e2e/landing.spec.ts
```

Expected: FAIL。`/welcome/` 还不存在，页面会落回 SPA 登录页或返回空壳，H1、FAQ、链接都找不到。

- [ ] **Step 3: 检查点**

不要 commit。向用户汇报测试已写好并按预期失败，接下来实现静态页。

---

## Task 4: 落地页 HTML

**Files:**
- Create: `frontend/public/welcome/index.html`

- [ ] **Step 1: 创建完整 HTML**

创建 `frontend/public/welcome/index.html`：

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Backing｜A 股研究、回测与模拟交易工作台</title>
    <meta
      name="description"
      content="同步 A 股行情与日线，跑 13 个内置策略的回测和参数优化，用 DeepSeek 做多阶段分析，在模拟盘验证。仅供研究，不构成投资建议。"
    />
    <meta name="robots" content="index,follow" />
    <meta name="theme-color" content="#f3f0ee" />
    <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
    <meta property="og:type" content="website" />
    <meta property="og:site_name" content="Backing" />
    <meta property="og:locale" content="zh_CN" />
    <meta
      property="og:title"
      content="Backing｜A 股研究、回测与模拟交易工作台"
    />
    <meta
      property="og:description"
      content="同步 A 股行情与日线，跑 13 个内置策略的回测和参数优化，用 DeepSeek 做多阶段分析，在模拟盘验证。仅供研究，不构成投资建议。"
    />
    <meta property="og:image" content="/welcome/assets/og-image.png" />
    <meta name="twitter:card" content="summary_large_image" />
    <meta
      name="twitter:title"
      content="Backing｜A 股研究、回测与模拟交易工作台"
    />
    <meta
      name="twitter:description"
      content="同步 A 股行情与日线，跑 13 个内置策略的回测和参数优化，用 DeepSeek 做多阶段分析，在模拟盘验证。仅供研究，不构成投资建议。"
    />
    <meta name="twitter:image" content="/welcome/assets/og-image.png" />
    <script>
      document.documentElement.classList.add('js')
    </script>
    <link rel="stylesheet" href="/welcome/landing.css" />
    <script src="/welcome/landing.js" defer></script>
    <script type="application/ld+json">
      {
        "@context": "https://schema.org",
        "@graph": [
          {
            "@type": "SoftwareApplication",
            "name": "Backing",
            "description": "A 股研究、回测、AI 分析与模拟交易工作台。",
            "applicationCategory": "FinanceApplication",
            "operatingSystem": "Web",
            "inLanguage": "zh-CN"
          },
          {
            "@type": "FAQPage",
            "mainEntity": [
              {
                "@type": "Question",
                "name": "这是实盘交易系统吗？",
                "acceptedAnswer": {
                  "@type": "Answer",
                  "text": "不是。系统没有券商接口，所有下单和成交都发生在模拟盘。"
                }
              },
              {
                "@type": "Question",
                "name": "需要自己准备数据源吗？",
                "acceptedAnswer": {
                  "@type": "Answer",
                  "text": "需要配置 baostock 或 mootdx；两者都不可达时，实时行情会明确返回空或 503，不会用旧数据冒充实时。"
                }
              },
              {
                "@type": "Question",
                "name": "支持哪些策略？可以写自己的吗？",
                "acceptedAnswer": {
                  "@type": "Answer",
                  "text": "内置 13 个策略，覆盖趋势、反转和突破；自定义策略继承 Strategy 并注册即可出现在策略列表里。"
                }
              },
              {
                "@type": "Question",
                "name": "AI 分析会编造数据吗？",
                "acceptedAnswer": {
                  "@type": "Answer",
                  "text": "行情、财务和新闻事实都通过工具网关获取，返回带 source_id、as_of 和 vendor；模型只负责组织结论。"
                }
              },
              {
                "@type": "Question",
                "name": "回测会有未来函数吗？",
                "acceptedAnswer": {
                  "@type": "Answer",
                  "text": "统一执行器按交易日推进，指标只使用当日及之前的数据；评估用例覆盖了前视偏差检查。"
                }
              },
              {
                "@type": "Question",
                "name": "怎么登录？API Key 存在哪里？",
                "acceptedAnswer": {
                  "@type": "Answer",
                  "text": "用 API Key 换取 8 小时的 HttpOnly 会话 Cookie；Key 不写入 localStorage，也不进入浏览器 bundle。"
                }
              },
              {
                "@type": "Question",
                "name": "数据存在哪里？重启会丢吗？",
                "acceptedAnswer": {
                  "@type": "Answer",
                  "text": "默认 SQLite，可切 MySQL；回测结果、交易明细和任务状态都落库，重启后可以恢复。"
                }
              },
              {
                "@type": "Question",
                "name": "手机上能用吗？",
                "acceptedAnswer": {
                  "@type": "Answer",
                  "text": "页面是响应式布局，移动端有独立的全屏导航；图表和表格在窄屏下会隐藏次要列。"
                }
              },
              {
                "@type": "Question",
                "name": "这些内容构成投资建议吗？",
                "acceptedAnswer": {
                  "@type": "Answer",
                  "text": "不构成。系统只用于研究和模拟，不提供任何收益承诺。"
                }
              }
            ]
          }
        ]
      }
    </script>
  </head>
  <body>
    <a class="skip-link" href="#main">跳到主内容</a>

    <header class="site-header">
      <nav class="nav-pill" aria-label="主导航">
        <a class="wordmark" href="/welcome/" aria-label="Backing 首页">
          <svg
            class="wordmark-mark"
            width="20"
            height="20"
            viewBox="0 0 20 20"
            aria-hidden="true"
          >
            <rect x="3" y="9" width="3" height="8" rx="1" fill="currentColor"></rect>
            <rect x="8.5" y="5" width="3" height="12" rx="1" fill="currentColor"></rect>
            <rect x="14" y="2" width="3" height="15" rx="1" fill="var(--lp-accent)"></rect>
          </svg>
          <span>Backing</span>
        </a>
        <div class="nav-links">
          <a href="#features">功能</a>
          <a href="#how-it-works">工作原理</a>
          <a href="#boundary">边界</a>
          <a href="#faq">常见问题</a>
          <a class="nav-login" href="/login">登录</a>
        </div>
        <button
          class="nav-toggle"
          type="button"
          aria-label="打开菜单"
          aria-expanded="false"
          aria-controls="mobile-menu"
        >
          <span></span>
          <span></span>
        </button>
      </nav>
    </header>

    <div id="mobile-menu" class="mobile-menu" hidden>
        <button class="mobile-close" type="button" aria-label="关闭菜单">
          <span aria-hidden="true">×</span>
        </button>
        <nav aria-label="移动端导航">
          <a href="#features">功能</a>
          <a href="#how-it-works">工作原理</a>
          <a href="#boundary">边界</a>
          <a href="#faq">常见问题</a>
          <a class="nav-login" href="/login">登录</a>
        </nav>
    </div>

    <main id="main">
      <section class="hero">
        <div class="container">
          <p class="eyebrow">A 股研究 · 回测 · 模拟交易</p>
          <h1 id="hero-title">
            从 K 线到模拟成交，<br class="hero-break" />把 A 股研究跑成<br class="hero-break" />一条可复现的链路
          </h1>
          <p class="hero-sub">
            同步行情与日线，跑 13 个内置策略的回测和参数优化，用 DeepSeek
            做多阶段分析，最后在模拟盘验证。所有交易都是模拟盘，不接券商。
          </p>
          <div class="hero-actions">
            <a class="button button-primary login-link" href="/login">登录研究工作台</a>
            <a class="text-link" href="#how-it-works">
              看看工作流 <span aria-hidden="true">↓</span>
            </a>
          </div>
          <p class="risk-reversal">无需绑定券商账户。所有成交都在模拟盘。</p>
          <p class="proof-line">
            数据源 baostock / mootdx · 13 个内置策略 · 统一回测引擎 · 模拟盘 T+1
          </p>
          <figure class="hero-visual">
            <div class="browser-frame">
              <div class="browser-bar" aria-hidden="true">
                <span></span><span></span><span></span>
              </div>
              <img
                src="/welcome/assets/dashboard.png"
                alt="Backing 仪表盘界面，展示指数卡片、自选股表格和当日走势图"
                width="1440"
                height="820"
                loading="eager"
                fetchpriority="high"
                decoding="async"
              />
            </div>
            <figcaption>Backing 仪表盘 · 真实界面，示例数据</figcaption>
          </figure>
        </div>
      </section>

      <section class="tagline" aria-label="Backing 的研究主张">
        <div class="container">
          <p class="tagline-line" data-tagline>先回测，再相信。</p>
          <p class="tagline-line" data-tagline>每一个策略假设，</p>
          <p class="tagline-line" data-tagline>都值得放进<span class="tagline-break" aria-hidden="true"></span>数据里跑一遍。</p>
        </div>
      </section>

      <section id="features" class="section" aria-labelledby="features-title">
        <div class="container" data-reveal>
          <header class="section-heading">
            <p class="eyebrow">能力</p>
            <h2 id="features-title">把研究流程里的重复动作收进一个系统</h2>
          </header>
          <div class="feature-grid">
            <article class="feature-card">
              <svg
                class="feature-icon"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="1.5"
                stroke-linecap="round"
                stroke-linejoin="round"
                aria-hidden="true"
              >
                <ellipse cx="12" cy="5.5" rx="7" ry="3"></ellipse>
                <path d="M5 5.5v6c0 1.66 3.13 3 7 3s7-1.34 7-3v-6"></path>
                <path d="M5 11.5v6c0 1.66 3.13 3 7 3s7-1.34 7-3v-6"></path>
              </svg>
              <h3>数据到回测，一条链路</h3>
              <p>
                股票列表、日线、实时行情和技术指标都在同一个库里，回测直接读数据库，不用在脚本之间搬
                CSV。
              </p>
            </article>
            <article class="feature-card">
              <svg
                class="feature-icon"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="1.5"
                stroke-linecap="round"
                stroke-linejoin="round"
                aria-hidden="true"
              >
                <path d="M4 19V5"></path>
                <path d="M4 19h16"></path>
                <path d="M7 15l4-5 3 3 5-7"></path>
              </svg>
              <h3>13 个内置策略，参数可以搜</h3>
              <p>
                趋势、反转、突破三类策略；网格搜索参数组合，结果落库，直接对比净值、回撤和逐笔交易。
              </p>
            </article>
            <article class="feature-card">
              <svg
                class="feature-icon"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="1.5"
                stroke-linecap="round"
                stroke-linejoin="round"
                aria-hidden="true"
              >
                <rect x="5" y="8" width="14" height="10" rx="3"></rect>
                <path d="M12 5v3"></path>
                <circle cx="9" cy="13" r="1"></circle>
                <circle cx="15" cy="13" r="1"></circle>
                <path d="M9 16h6"></path>
              </svg>
              <h3>AI 分析，结论有出处</h3>
              <p>
                技术面、消息面、风险、策略、决策五个阶段；事实来自工具网关的
                <code>source_id</code> / <code>as_of</code>，不让模型编造行情。
              </p>
            </article>
            <article class="feature-card">
              <svg
                class="feature-icon"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="1.5"
                stroke-linecap="round"
                stroke-linejoin="round"
                aria-hidden="true"
              >
                <path d="M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6l7-3z"></path>
                <path d="M9 12l2 2 4-4"></path>
              </svg>
              <h3>模拟盘按 A 股规则成交</h3>
              <p>
                没有审批就不下单；T+1、涨跌停、手续费和滑点都按规则模拟。
              </p>
            </article>
          </div>
        </div>
      </section>

      <section
        id="how-it-works"
        class="section section-alt"
        aria-labelledby="how-title"
      >
        <div class="container" data-reveal>
          <header class="section-heading">
            <p class="eyebrow">工作流</p>
            <h2 id="how-title">从数据到模拟盘，三步</h2>
          </header>
          <ol class="steps">
            <li class="step">
              <span class="step-index">01</span>
              <h3>同步数据</h3>
              <p>
                拉取股票列表和日线，实时行情按需获取；数据源不可达时明确返回空或
                503，不假装有数据。
              </p>
            </li>
            <li class="step">
              <span class="step-index">02</span>
              <h3>选策略，跑回测</h3>
              <p>
                调参数或交给优化器做网格搜索；看净值曲线、最大回撤和逐笔交易。
              </p>
            </li>
            <li class="step">
              <span class="step-index">03</span>
              <h3>用 AI 写报告，再进模拟盘</h3>
              <p>
                生成多阶段研究报告，把结论放进模拟盘跟踪；审批通过后才成交。
              </p>
            </li>
          </ol>
        </div>
      </section>

      <section id="screens" class="section" aria-labelledby="screens-title">
        <div class="container" data-reveal>
          <header class="section-heading">
            <p class="eyebrow">真实界面</p>
            <h2 id="screens-title">真实界面，示例数据</h2>
            <p class="section-sub">
              截图来自真实前端，数据为演示用示例，不是实时行情。
            </p>
          </header>
          <div class="screens-grid">
            <figure class="screen-card">
              <div class="browser-frame">
                <div class="browser-bar" aria-hidden="true">
                  <span></span><span></span><span></span>
                </div>
                <img
                  src="/welcome/assets/dashboard.png"
                  alt="Backing 仪表盘界面，展示指数卡片、自选股表格和当日走势图"
                  width="1440"
                  height="820"
                  loading="lazy"
                  decoding="async"
                />
              </div>
              <figcaption>
                仪表盘：指数、自选股和当日走势 · 真实界面，示例数据
              </figcaption>
            </figure>
            <figure class="screen-card">
              <div class="browser-frame">
                <div class="browser-bar" aria-hidden="true">
                  <span></span><span></span><span></span>
                </div>
                <img
                  src="/welcome/assets/strategies.png"
                  alt="Backing 策略回测界面，展示净值曲线、回撤指标和逐笔交易表"
                  width="1440"
                  height="820"
                  loading="lazy"
                  decoding="async"
                />
              </div>
              <figcaption>
                策略回测：净值曲线、回撤和逐笔交易 · 真实界面，示例数据
              </figcaption>
            </figure>
          </div>
        </div>
      </section>

      <section
        id="boundary"
        class="section section-alt"
        aria-labelledby="boundary-title"
      >
        <div class="container" data-reveal>
          <header class="section-heading">
            <p class="eyebrow">边界</p>
            <h2 id="boundary-title">先说清楚边界</h2>
            <p class="section-sub">
              这是一个研究工具，不是荐股服务，也不是实盘交易终端。
            </p>
          </header>
          <div class="boundary-grid">
            <article class="boundary-card">
              <h3>不接实盘</h3>
              <p>没有券商接口，所有成交都在模拟盘。</p>
            </article>
            <article class="boundary-card">
              <h3>不承诺收益</h3>
              <p>回测是历史数据上的推演，不代表未来表现。</p>
            </article>
            <article class="boundary-card">
              <h3>不替你做决定</h3>
              <p>AI 输出是研究材料，不是投资建议。</p>
            </article>
          </div>
        </div>
      </section>

      <section id="faq" class="section" aria-labelledby="faq-title">
        <div class="container" data-reveal>
          <header class="section-heading">
            <p class="eyebrow">常见问题</p>
            <h2 id="faq-title">你可能想先问清楚的事</h2>
          </header>
          <div class="faq-list">
            <details class="faq-item">
              <summary>这是实盘交易系统吗？</summary>
              <p>不是。系统没有券商接口，所有下单和成交都发生在模拟盘。</p>
            </details>
            <details class="faq-item">
              <summary>需要自己准备数据源吗？</summary>
              <p>
                需要配置 baostock 或 mootdx；两者都不可达时，实时行情会明确返回空或
                503，不会用旧数据冒充实时。
              </p>
            </details>
            <details class="faq-item">
              <summary>支持哪些策略？可以写自己的吗？</summary>
              <p>
                内置 13 个策略，覆盖趋势、反转和突破；自定义策略继承
                <code>Strategy</code> 并注册即可出现在策略列表里。
              </p>
            </details>
            <details class="faq-item">
              <summary>AI 分析会编造数据吗？</summary>
              <p>
                行情、财务和新闻事实都通过工具网关获取，返回带
                <code>source_id</code>、<code>as_of</code> 和
                <code>vendor</code>；模型只负责组织结论。
              </p>
            </details>
            <details class="faq-item">
              <summary>回测会有未来函数吗？</summary>
              <p>
                统一执行器按交易日推进，指标只使用当日及之前的数据；评估用例覆盖了前视偏差检查。
              </p>
            </details>
            <details class="faq-item">
              <summary>怎么登录？API Key 存在哪里？</summary>
              <p>
                用 API Key 换取 8 小时的 HttpOnly 会话 Cookie；Key 不写入
                localStorage，也不进入浏览器 bundle。
              </p>
            </details>
            <details class="faq-item">
              <summary>数据存在哪里？重启会丢吗？</summary>
              <p>
                默认 SQLite，可切 MySQL；回测结果、交易明细和任务状态都落库，重启后可以恢复。
              </p>
            </details>
            <details class="faq-item">
              <summary>手机上能用吗？</summary>
              <p>
                页面是响应式布局，移动端有独立的全屏导航；图表和表格在窄屏下会隐藏次要列。
              </p>
            </details>
            <details class="faq-item">
              <summary>这些内容构成投资建议吗？</summary>
              <p>不构成。系统只用于研究和模拟，不提供任何收益承诺。</p>
            </details>
          </div>
        </div>
      </section>

      <section class="final-cta" aria-labelledby="final-cta-title">
        <div class="container">
          <h2 id="final-cta-title">把下一个策略假设放进数据里</h2>
          <p>
            登录 Backing，从同步数据开始，跑一遍回测，再决定要不要相信它。
          </p>
          <a class="button button-primary login-link" href="/login">登录研究工作台</a>
          <p class="risk-reversal">无需绑定券商账户。所有成交都在模拟盘。</p>
        </div>
      </section>
    </main>

    <footer class="site-footer">
      <div class="container">
        <div class="footer-main">
          <div class="footer-brand">
            <a class="wordmark" href="/welcome/" aria-label="Backing 首页">
              <svg
                class="wordmark-mark"
                width="20"
                height="20"
                viewBox="0 0 20 20"
                aria-hidden="true"
              >
                <rect
                  x="3"
                  y="9"
                  width="3"
                  height="8"
                  rx="1"
                  fill="currentColor"
                ></rect>
                <rect
                  x="8.5"
                  y="5"
                  width="3"
                  height="12"
                  rx="1"
                  fill="currentColor"
                ></rect>
                <rect
                  x="14"
                  y="2"
                  width="3"
                  height="15"
                  rx="1"
                  fill="var(--lp-accent)"
                ></rect>
              </svg>
              <span>Backing</span>
            </a>
            <p>A 股研究、回测、AI 分析与模拟交易工作台。</p>
          </div>
          <nav class="footer-links" aria-label="页脚导航">
            <a href="#features">功能</a>
            <a href="#how-it-works">工作原理</a>
            <a href="#boundary">边界</a>
            <a href="#faq">常见问题</a>
            <a class="login-link" href="/login">登录</a>
          </nav>
          <nav class="footer-legal" aria-label="法律信息">
            <a href="/legal/privacy.html">隐私</a>
            <a href="/legal/terms.html">条款</a>
          </nav>
        </div>
        <div class="footer-bottom">
          <p>仅供研究使用，不构成投资建议。所有交易均为模拟盘。</p>
          <p>© 2026 Backing</p>
        </div>
      </div>
    </footer>
  </body>
</html>
```

- [ ] **Step 2: 验证关键文案在 HTML 源码中**

```bash
cd frontend
grep -c "从 K 线到模拟成交" public/welcome/index.html
grep -c "faq-item" public/welcome/index.html
grep -c "FAQPage" public/welcome/index.html
```

Expected: 第一个输出至少 `1`，第二个至少 `10`（9 个条目 + 1 个 CSS 类名引用不算，实际以文件为准），第三个 `1`。

- [ ] **Step 3: 检查点**

不要 commit。向用户汇报 HTML 已创建，等待 CSS。

---

## Task 5: 落地页 CSS

**Files:**
- Create: `frontend/public/welcome/landing.css`

- [ ] **Step 1: 创建完整 CSS**

创建 `frontend/public/welcome/landing.css`：

```css
/*
 * Backing landing page.
 * Brand values mirror src/styles/tokens.css; keep both in sync when the brand changes.
 * Type sizes, spacing, radii and motion follow the landing-page-design skill.
 */
:root {
  --lp-canvas: #f3f0ee;
  --lp-surface: #fcfbfa;
  --lp-ink: #141413;
  --lp-ink-soft: #262627;
  --lp-muted: #696969;
  --lp-tertiary: #77716b;
  --lp-accent: #cf4500;
  --lp-clay: #9a3a0a;
  --lp-border: rgba(20, 20, 19, 0.12);
  --lp-border-soft: rgba(20, 20, 19, 0.08);
  --lp-ease: cubic-bezier(0.22, 1, 0.36, 1);
  --lp-container: 1120px;
  --lp-nav-width: 760px;
  --lp-shadow: 0 24px 48px rgba(20, 20, 19, 0.08);
}

*,
*::before,
*::after {
  box-sizing: border-box;
}

html {
  scroll-behavior: smooth;
  scrollbar-width: thin;
  scrollbar-color: rgba(20, 20, 19, 0.22) transparent;
}

[id] {
  scroll-margin-top: 96px;
}

body {
  margin: 0;
  background: var(--lp-canvas);
  color: var(--lp-ink);
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC',
    'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
  font-size: 16px;
  line-height: 24px;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

img {
  display: block;
  max-width: 100%;
  height: auto;
}

a {
  color: inherit;
  text-decoration: none;
}

button {
  font: inherit;
}

code {
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', monospace;
  font-size: 14px;
  line-height: 20px;
}

:focus-visible {
  outline: 2px solid var(--lp-ink);
  outline-offset: 3px;
}

.skip-link {
  position: fixed;
  top: 16px;
  left: 16px;
  z-index: 300;
  padding: 12px 16px;
  border-radius: 9999px;
  background: var(--lp-ink);
  color: var(--lp-canvas);
  font-size: 14px;
  line-height: 20px;
  font-weight: 600;
  transform: translateY(-200%);
  transition: transform 300ms var(--lp-ease);
}

.skip-link:focus {
  transform: translateY(0);
}

.container {
  width: min(100% - 32px, var(--lp-container));
  margin-inline: auto;
}

@media (min-width: 768px) {
  .container {
    width: min(100% - 48px, var(--lp-container));
  }
}

@media (min-width: 1024px) {
  .container {
    width: min(100% - 64px, var(--lp-container));
  }
}

/* Header */
.site-header {
  position: fixed;
  top: 24px;
  left: 50%;
  z-index: 100;
  width: min(calc(100% - 48px), var(--lp-nav-width));
  transform: translateX(-50%);
}

@media (max-width: 767px) {
  .site-header {
    top: 16px;
    width: calc(100% - 32px);
  }
}

.nav-pill {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  min-height: 56px;
  padding: 8px 16px;
  border: 1px solid var(--lp-border-soft);
  border-radius: 9999px;
  background: rgba(252, 251, 250, 0.72);
  box-shadow: 0 8px 28px rgba(20, 20, 19, 0.06);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
}

.wordmark {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 20px;
  line-height: 28px;
  font-weight: 600;
  white-space: nowrap;
  transition: opacity 300ms var(--lp-ease);
}

.wordmark:hover {
  opacity: 0.72;
}

.wordmark-mark {
  flex: none;
}

.nav-links {
  display: none;
  align-items: center;
  gap: 4px;
  margin-left: auto;
}

@media (min-width: 900px) {
  .nav-links {
    display: flex;
  }
}

.nav-links a {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 8px 12px;
  border-radius: 9999px;
  font-size: 14px;
  line-height: 20px;
  font-weight: 600;
  color: var(--lp-muted);
  transition: color 300ms var(--lp-ease), background-color 300ms var(--lp-ease);
}

.nav-links a:hover {
  color: var(--lp-ink);
  background: rgba(20, 20, 19, 0.04);
}

.nav-links a[aria-current='true'] {
  color: var(--lp-ink);
}

.nav-links a[aria-current='true']::after {
  content: '';
  width: 4px;
  height: 4px;
  margin-top: 4px;
  border-radius: 9999px;
  background: var(--lp-accent);
}

.nav-login {
  color: var(--lp-ink) !important;
}

.nav-toggle {
  display: inline-flex;
  flex-direction: column;
  justify-content: center;
  gap: 4px;
  width: 40px;
  height: 40px;
  padding: 0;
  border: 0;
  border-radius: 9999px;
  background: transparent;
  color: var(--lp-ink);
  cursor: pointer;
  transition: background-color 300ms var(--lp-ease);
}

.nav-toggle:hover {
  background: rgba(20, 20, 19, 0.04);
}

.nav-toggle span {
  display: block;
  width: 18px;
  height: 2px;
  margin-inline: auto;
  background: currentColor;
  transition: transform 500ms var(--lp-ease), opacity 300ms var(--lp-ease);
}

.nav-toggle[aria-expanded='true'] span:first-child {
  transform: translateY(4px) rotate(45deg);
}

.nav-toggle[aria-expanded='true'] span:last-child {
  transform: translateY(-4px) rotate(-45deg);
}

@media (min-width: 900px) {
  .nav-toggle {
    display: none;
  }
}

/* Mobile menu */
.mobile-menu {
  position: fixed;
  inset: 0;
  z-index: 200;
  display: flex;
  flex-direction: column;
  padding: 24px;
  background: rgba(243, 240, 238, 0.97);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
}

.mobile-menu[hidden] {
  display: none;
}

.mobile-close {
  align-self: flex-end;
  width: 48px;
  height: 48px;
  border: 0;
  border-radius: 9999px;
  background: rgba(20, 20, 19, 0.06);
  color: var(--lp-ink);
  font-size: 24px;
  line-height: 1;
  cursor: pointer;
  transition: background-color 300ms var(--lp-ease),
    transform 300ms var(--lp-ease);
}

.mobile-close:hover {
  background: rgba(20, 20, 19, 0.12);
}

.mobile-close:active {
  transform: scale(0.98);
}

.mobile-menu nav {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 48px;
}

.mobile-menu nav a {
  padding: 12px 0;
  font-size: 24px;
  line-height: 32px;
  font-weight: 600;
  opacity: 0;
  transform: translateY(24px);
  transition: opacity 400ms var(--lp-ease), transform 500ms var(--lp-ease),
    color 300ms var(--lp-ease);
}

.mobile-menu nav a:hover {
  color: var(--lp-clay);
}

.mobile-menu.is-open nav a {
  opacity: 1;
  transform: translateY(0);
}

.mobile-menu nav a:nth-child(1) {
  transition-delay: 60ms;
}

.mobile-menu nav a:nth-child(2) {
  transition-delay: 120ms;
}

.mobile-menu nav a:nth-child(3) {
  transition-delay: 180ms;
}

.mobile-menu nav a:nth-child(4) {
  transition-delay: 240ms;
}

.mobile-menu nav a:nth-child(5) {
  transition-delay: 300ms;
}

/* Hero */
.hero {
  padding: 96px 0 64px;
}

@media (min-width: 768px) {
  .hero {
    padding: 96px 0 96px;
  }
}

.eyebrow {
  margin: 0;
  font-size: 12px;
  line-height: 16px;
  font-weight: 600;
  color: var(--lp-clay);
}

.hero h1 {
  max-width: 680px;
  margin: 16px 0 0;
  font-size: 30px;
  line-height: 36px;
  font-weight: 600;
  text-wrap: balance;
  background: linear-gradient(90deg, #141413, #6f6a64);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}

@supports not (background-clip: text) {
  .hero h1 {
    background: none;
    color: var(--lp-ink);
  }
}

@media (min-width: 768px) {
  .hero h1 {
    font-size: 48px;
    line-height: 1;
  }
}

@media (max-width: 359px) {
  .hero h1 {
    font-size: 24px;
    line-height: 32px;
  }
}

.hero-sub {
  max-width: 680px;
  margin: 24px 0 0;
  font-size: 16px;
  line-height: 24px;
  color: var(--lp-muted);
  text-wrap: pretty;
}

.hero-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 16px;
  margin-top: 32px;
}

.button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 40px;
  padding: 8px 12px;
  border: 0;
  border-radius: 9999px;
  font-size: 16px;
  line-height: 24px;
  font-weight: 600;
  cursor: pointer;
  transition: transform 300ms var(--lp-ease),
    background-color 300ms var(--lp-ease), color 300ms var(--lp-ease);
}

.button-primary {
  background: var(--lp-ink);
  color: var(--lp-canvas);
}

.button-primary:hover {
  background: var(--lp-ink-soft);
  transform: translateY(-1px);
}

.button-primary:active {
  transform: scale(0.98);
}

.text-link {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 40px;
  padding: 8px 0;
  border-bottom: 1px solid var(--lp-border);
  font-size: 16px;
  line-height: 24px;
  font-weight: 600;
  transition: border-color 300ms var(--lp-ease);
}

.text-link:hover {
  border-color: var(--lp-ink);
}

.risk-reversal {
  margin: 16px 0 0;
  font-size: 14px;
  line-height: 20px;
  color: var(--lp-tertiary);
}

.proof-line {
  margin: 8px 0 0;
  font-size: 14px;
  line-height: 20px;
  color: var(--lp-muted);
}

.hero-visual {
  margin: 48px 0 0;
}

.browser-frame {
  padding: 8px;
  border: 1px solid var(--lp-border);
  border-radius: 16px;
  background: var(--lp-surface);
  box-shadow: var(--lp-shadow);
}

.browser-bar {
  display: flex;
  gap: 4px;
  padding: 4px 4px 12px;
}

.browser-bar span {
  width: 8px;
  height: 8px;
  border-radius: 9999px;
  background: var(--lp-border);
}

.browser-frame img {
  width: 100%;
  border-radius: 8px;
}

.hero-visual figcaption,
.screen-card figcaption {
  margin-top: 12px;
  font-size: 14px;
  line-height: 20px;
  color: var(--lp-tertiary);
  text-align: center;
}

/* Tagline */
.tagline {
  padding: 64px 0;
}

@media (min-width: 768px) {
  .tagline {
    padding: 96px 0;
  }
}

.tagline-line {
  max-width: 680px;
  margin: 0 auto;
  font-size: 36px;
  line-height: 40px;
  font-weight: 600;
  text-align: center;
  text-wrap: balance;
}

.tagline-line + .tagline-line {
  margin-top: 16px;
}

@media (min-width: 768px) {
  .tagline-line {
    font-size: 48px;
    line-height: 1;
  }
}

.tagline-word {
  opacity: 1;
  transition: opacity 400ms var(--lp-ease);
}

html.js .tagline-word {
  opacity: 0.3;
}

html.js .tagline-word.is-lit {
  opacity: 1;
}

.tagline-break {
  display: none;
}

@media (max-width: 767px) {
  br.tagline-break {
    display: inline;
  }
}

/* Sections */
.section {
  padding: 64px 0;
}

@media (min-width: 768px) {
  .section {
    padding: 96px 0;
  }
}

.section-alt {
  background: var(--lp-surface);
}

.section-heading {
  max-width: 680px;
  margin-bottom: 40px;
}

.section-heading h2 {
  margin: 12px 0 0;
  font-size: 30px;
  line-height: 36px;
  font-weight: 600;
  text-wrap: balance;
}

@media (min-width: 768px) {
  .section-heading h2 {
    font-size: 36px;
    line-height: 40px;
  }
}

.section-sub {
  margin: 16px 0 0;
  font-size: 16px;
  line-height: 24px;
  color: var(--lp-muted);
  text-wrap: pretty;
}

/* Features */
.feature-grid {
  display: grid;
  gap: 16px;
}

@media (min-width: 768px) {
  .feature-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 24px;
  }
}

.feature-card {
  padding: 24px;
  border: 1px solid var(--lp-border-soft);
  border-radius: 16px;
  background: var(--lp-surface);
}

@media (min-width: 768px) {
  .feature-card {
    padding: 32px;
  }
}

.feature-icon {
  width: 24px;
  height: 24px;
  margin-bottom: 24px;
  color: var(--lp-ink);
}

.feature-card h3,
.boundary-card h3,
.step h3 {
  margin: 0 0 12px;
  font-size: 20px;
  line-height: 28px;
  font-weight: 600;
  text-wrap: balance;
}

.feature-card p,
.boundary-card p,
.step p {
  margin: 0;
  font-size: 16px;
  line-height: 24px;
  color: var(--lp-muted);
  text-wrap: pretty;
}

/* Steps */
.steps {
  display: grid;
  gap: 24px;
  margin: 0;
  padding: 0;
  list-style: none;
}

@media (min-width: 1024px) {
  .steps {
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 32px;
  }
}

.step::before {
  content: '';
  display: block;
  width: 24px;
  height: 2px;
  margin-bottom: 24px;
  background: var(--lp-accent);
}

.step-index {
  display: block;
  margin-bottom: 16px;
  font-size: 12px;
  line-height: 16px;
  font-weight: 600;
  color: var(--lp-clay);
}

/* Screens */
.screens-grid {
  display: grid;
  gap: 32px;
}

@media (min-width: 1024px) {
  .screens-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 24px;
  }
}

.screen-card {
  margin: 0;
}

/* Boundary */
.boundary-grid {
  display: grid;
  gap: 16px;
}

@media (min-width: 1024px) {
  .boundary-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 24px;
  }
}

.boundary-card {
  padding: 24px;
  border: 1px solid var(--lp-border-soft);
  border-radius: 16px;
  background: var(--lp-canvas);
}

/* FAQ */
.faq-list {
  max-width: 840px;
  border-top: 1px solid var(--lp-border);
}

.faq-item {
  border-bottom: 1px solid var(--lp-border);
}

.faq-item summary {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  padding: 24px 0;
  cursor: pointer;
  list-style: none;
  font-size: 18px;
  line-height: 28px;
  font-weight: 600;
  text-wrap: balance;
  transition: color 300ms var(--lp-ease);
}

.faq-item summary:hover {
  color: var(--lp-clay);
}

.faq-item summary::-webkit-details-marker {
  display: none;
}

.faq-item summary::after {
  content: '+';
  flex: none;
  font-size: 20px;
  line-height: 28px;
  color: var(--lp-clay);
  transition: transform 300ms var(--lp-ease);
}

.faq-item[open] summary::after {
  content: '−';
}

.faq-item p {
  max-width: 680px;
  margin: 0 0 24px;
  font-size: 16px;
  line-height: 24px;
  color: var(--lp-muted);
  text-wrap: pretty;
}

/* Final CTA */
.final-cta {
  padding: 64px 0;
  background: var(--lp-ink);
  color: var(--lp-canvas);
  text-align: center;
}

@media (min-width: 768px) {
  .final-cta {
    padding: 80px 0;
  }
}

.final-cta h2 {
  max-width: 680px;
  margin: 0 auto;
  font-size: 30px;
  line-height: 36px;
  font-weight: 600;
  text-wrap: balance;
}

@media (min-width: 768px) {
  .final-cta h2 {
    font-size: 36px;
    line-height: 40px;
  }
}

.final-cta p {
  max-width: 680px;
  margin: 16px auto 32px;
  font-size: 16px;
  line-height: 24px;
  color: rgba(243, 240, 238, 0.72);
  text-wrap: pretty;
}

.final-cta .button-primary {
  background: var(--lp-canvas);
  color: var(--lp-ink);
}

.final-cta .button-primary:hover {
  background: #ffffff;
}

.final-cta .risk-reversal {
  color: rgba(243, 240, 238, 0.64);
}

/* Footer */
.site-footer {
  padding: 64px 0 32px;
}

.footer-main {
  display: grid;
  gap: 32px;
}

@media (min-width: 768px) {
  .footer-main {
    grid-template-columns: 2fr 1fr 1fr;
    gap: 48px;
  }
}

.footer-brand p {
  max-width: 320px;
  margin: 12px 0 0;
  font-size: 14px;
  line-height: 20px;
  color: var(--lp-muted);
  text-wrap: pretty;
}

.footer-links,
.footer-legal {
  display: flex;
  flex-direction: column;
  gap: 12px;
  font-size: 14px;
  line-height: 20px;
  color: var(--lp-muted);
}

.footer-links a,
.footer-legal a {
  transition: color 300ms var(--lp-ease);
}

.footer-links a:hover,
.footer-legal a:hover {
  color: var(--lp-ink);
  text-decoration: underline;
}

.footer-bottom {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 12px;
  margin-top: 48px;
  padding-top: 24px;
  border-top: 1px solid var(--lp-border);
  font-size: 12px;
  line-height: 16px;
  color: var(--lp-tertiary);
}

.footer-bottom p {
  margin: 0;
}

/* Reveal */
html.js [data-reveal] {
  opacity: 0;
  transform: translateY(32px);
  transition: opacity 700ms var(--lp-ease), transform 700ms var(--lp-ease);
}

html.js [data-reveal].is-revealed {
  opacity: 1;
  transform: translateY(0);
}

/* Legal pages */
.legal-page {
  min-height: 100vh;
}

.legal-header {
  padding: 32px 0 0;
}

.legal-main {
  max-width: 720px;
  padding: 96px 0 64px;
}

.legal-main h1 {
  margin: 0 0 24px;
  font-size: 36px;
  line-height: 40px;
  font-weight: 600;
  text-wrap: balance;
}

.legal-main h2 {
  margin: 32px 0 12px;
  font-size: 20px;
  line-height: 28px;
  font-weight: 600;
}

.legal-main p,
.legal-main li {
  font-size: 16px;
  line-height: 24px;
  color: var(--lp-muted);
  text-wrap: pretty;
}

.legal-main ul {
  padding-left: 24px;
}

.legal-back {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin-top: 40px;
  padding-bottom: 4px;
  border-bottom: 1px solid var(--lp-border);
  font-size: 14px;
  line-height: 20px;
  font-weight: 600;
  color: var(--lp-ink);
  transition: color 300ms var(--lp-ease);
}

.legal-back:hover {
  color: var(--lp-clay);
}

/* Reduced motion */
@media (prefers-reduced-motion: reduce) {
  html {
    scroll-behavior: auto;
  }

  html.js .tagline-word,
  html.js [data-reveal],
  .mobile-menu nav a {
    opacity: 1;
    transform: none;
    transition: none;
  }

  .button,
  .text-link,
  .nav-toggle span,
  .faq-item summary::after,
  .skip-link {
    transition: none;
  }
}
```

- [ ] **Step 2: 验证字号和间距没有非法值**

```bash
cd frontend
grep -nE "font-size: (11|13|17|19|22|26|28|34)px" public/welcome/landing.css
grep -nE "padding: (10|14|18|20|28|36|44|56|72)px" public/welcome/landing.css
```

Expected: 两条命令都没有输出。允许的字体大小只有 12、14、16、18、20、24、30、36、48；允许的间距只有 0、2、4、8、12、16、24、32、40、48、64、80、96。

- [ ] **Step 3: 检查点**

不要 commit。向用户汇报 CSS 已创建，等待 JS。

---

## Task 6: 落地页 JS 与 e2e 通过

**Files:**
- Create: `frontend/public/welcome/landing.js`

- [ ] **Step 1: 创建完整 JS**

创建 `frontend/public/welcome/landing.js`：

```js
(() => {
  const doc = document
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches

  const safeNextPath = (value) => {
    if (!value) return null
    if (!value.startsWith('/')) return null
    if (value.startsWith('//')) return null
    if (value.startsWith('/\\')) return null
    return value
  }

  const params = new URLSearchParams(window.location.search)
  const next = safeNextPath(params.get('next'))
  if (next) {
    doc.querySelectorAll('a[href="/login"]').forEach((link) => {
      link.setAttribute('href', `/login?next=${encodeURIComponent(next)}`)
    })
  }

  const toggle = doc.querySelector('.nav-toggle')
  const menu = doc.getElementById('mobile-menu')
  const closeButton = doc.querySelector('.mobile-close')
  const menuLinks = menu ? Array.from(menu.querySelectorAll('a')) : []
  let lastFocused = null
  let closeTimer = 0

  const focusables = () => [closeButton, ...menuLinks].filter(Boolean)

  const onKeyDown = (event) => {
    if (event.key === 'Escape') {
      closeMenu()
      return
    }
    if (event.key !== 'Tab' || !menu) return
    const items = focusables()
    if (items.length === 0) return
    const first = items[0]
    const last = items[items.length - 1]
    if (event.shiftKey && doc.activeElement === first) {
      event.preventDefault()
      last.focus()
    } else if (!event.shiftKey && doc.activeElement === last) {
      event.preventDefault()
      first.focus()
    }
  }

  const openMenu = () => {
    if (!menu || !toggle) return
    window.clearTimeout(closeTimer)
    lastFocused = doc.activeElement
    menu.hidden = false
    requestAnimationFrame(() => menu.classList.add('is-open'))
    toggle.setAttribute('aria-expanded', 'true')
    doc.body.style.overflow = 'hidden'
    closeButton?.focus()
    doc.addEventListener('keydown', onKeyDown)
  }

  const closeMenu = () => {
    if (!menu || !toggle) return
    menu.classList.remove('is-open')
    toggle.setAttribute('aria-expanded', 'false')
    doc.body.style.overflow = ''
    doc.removeEventListener('keydown', onKeyDown)
    closeTimer = window.setTimeout(
      () => {
        menu.hidden = true
      },
      reduceMotion ? 0 : 300,
    )
    const restore = lastFocused instanceof HTMLElement ? lastFocused : toggle
    restore.focus()
  }

  toggle?.addEventListener('click', openMenu)
  closeButton?.addEventListener('click', closeMenu)
  menuLinks.forEach((link) => link.addEventListener('click', closeMenu))

  const taglineLines = Array.from(doc.querySelectorAll('[data-tagline]'))
  taglineLines.forEach((line) => {
    const segments = []
    let buffer = ''
    line.childNodes.forEach((node) => {
      // 3 = text node, 1 = element node
      if (node.nodeType === 3) {
        buffer += node.textContent || ''
      } else if (
        node.nodeType === 1 &&
        node.classList &&
        node.classList.contains('tagline-break')
      ) {
        segments.push(buffer)
        buffer = ''
      }
    })
    segments.push(buffer)
    line.textContent = ''
    segments.forEach((segment, index) => {
      if (index > 0) {
        const br = doc.createElement('br')
        br.className = 'tagline-break'
        line.appendChild(br)
      }
      Array.from(segment).forEach((char) => {
        const span = doc.createElement('span')
        span.className = 'tagline-word'
        span.textContent = char === ' ' ? '\u00A0' : char
        line.appendChild(span)
      })
    })
  })

  const taglineWords = Array.from(doc.querySelectorAll('.tagline-word'))
  if (reduceMotion || !('IntersectionObserver' in window)) {
    taglineWords.forEach((word) => word.classList.add('is-lit'))
  } else {
    const taglineObserver = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add('is-lit')
            taglineObserver.unobserve(entry.target)
          }
        })
      },
      { rootMargin: '0px 0px -20% 0px', threshold: 0 },
    )
    taglineWords.forEach((word) => taglineObserver.observe(word))
  }

  const revealTargets = Array.from(doc.querySelectorAll('[data-reveal]'))
  if (reduceMotion || !('IntersectionObserver' in window)) {
    revealTargets.forEach((target) => target.classList.add('is-revealed'))
  } else {
    const revealObserver = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add('is-revealed')
            revealObserver.unobserve(entry.target)
          }
        })
      },
      { threshold: 0.12 },
    )
    revealTargets.forEach((target) => revealObserver.observe(target))
  }

  const navLinks = Array.from(doc.querySelectorAll('.nav-links a[href^="#"]'))
  const sections = navLinks
    .map((link) => doc.querySelector(link.getAttribute('href')))
    .filter(Boolean)
  if (sections.length && 'IntersectionObserver' in window) {
    const navObserver = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return
          navLinks.forEach((link) => link.removeAttribute('aria-current'))
          const active = navLinks.find(
            (link) => link.getAttribute('href') === `#${entry.target.id}`,
          )
          active?.setAttribute('aria-current', 'true')
        })
      },
      { rootMargin: '-40% 0px -50% 0px', threshold: 0 },
    )
    sections.forEach((section) => navObserver.observe(section))
  }
})()
```

- [ ] **Step 2: 更新 ESLint 配置**

`frontend/eslint.config.js` 末尾的 `prettier` 之前加：

```js
  {
    files: ['public/**/*.js'],
    languageOptions: {
      globals: {
        document: 'readonly',
        window: 'readonly',
        IntersectionObserver: 'readonly',
        URLSearchParams: 'readonly',
        HTMLElement: 'readonly',
        requestAnimationFrame: 'readonly'
      }
    }
  },
```

把现有的 `scripts/**/*.mjs` globals 从：

```js
      globals: {
        URL: 'readonly',
        console: 'readonly',
        process: 'readonly'
      }
```

改成：

```js
      globals: {
        URL: 'readonly',
        console: 'readonly',
        process: 'readonly',
        fetch: 'readonly',
        setTimeout: 'readonly',
        sessionStorage: 'readonly'
      }
```

- [ ] **Step 3: 运行落地页 e2e**

```bash
cd frontend
npx playwright test e2e/landing.spec.ts
```

Expected: PASS，5 个测试全部通过。

如果 `/welcome/` 返回的是 SPA 登录页，先执行 Task 10 的兜底插件，再重跑。

- [ ] **Step 4: 检查点**

不要 commit。向用户汇报落地页 e2e 通过，等待法律页和 SEO 文件。

---

## Task 7: 法律页、favicon、robots 和 app shell noindex

**Files:**
- Create: `frontend/public/legal/privacy.html`
- Create: `frontend/public/legal/terms.html`
- Create: `frontend/public/favicon.svg`
- Create: `frontend/public/robots.txt`
- Modify: `frontend/index.html`

- [ ] **Step 1: 创建 favicon**

创建 `frontend/public/favicon.svg`：

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
  <rect width="32" height="32" rx="8" fill="#f3f0ee" />
  <rect x="6" y="15" width="4" height="11" rx="1" fill="#141413" />
  <rect x="14" y="9" width="4" height="17" rx="1" fill="#141413" />
  <rect x="22" y="5" width="4" height="21" rx="1" fill="#cf4500" />
</svg>
```

- [ ] **Step 2: 创建 robots**

创建 `frontend/public/robots.txt`：

```txt
User-agent: *
Allow: /welcome/
Disallow: /
```

- [ ] **Step 3: 创建隐私页**

创建 `frontend/public/legal/privacy.html`：

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>隐私说明｜Backing</title>
    <meta name="robots" content="noindex,follow" />
    <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
    <link rel="stylesheet" href="/welcome/landing.css" />
  </head>
  <body class="legal-page">
    <header class="legal-header">
      <div class="container">
        <a class="wordmark" href="/welcome/" aria-label="Backing 首页">
          <svg
            class="wordmark-mark"
            width="20"
            height="20"
            viewBox="0 0 20 20"
            aria-hidden="true"
          >
            <rect x="3" y="9" width="3" height="8" rx="1" fill="currentColor"></rect>
            <rect x="8.5" y="5" width="3" height="12" rx="1" fill="currentColor"></rect>
            <rect x="14" y="2" width="3" height="15" rx="1" fill="var(--lp-accent)"></rect>
          </svg>
          <span>Backing</span>
        </a>
      </div>
    </header>
    <main class="container legal-main">
      <h1>隐私说明</h1>
      <p>本页说明 Backing 的公开介绍页和登录后系统分别处理哪些数据。</p>

      <h2>公开介绍页</h2>
      <p>介绍页不加载统计脚本，不设置 Cookie，不收集访客个人信息。</p>

      <h2>登录后的系统</h2>
      <ul>
        <li>使用 API Key 换取 8 小时的 HttpOnly 会话 Cookie。</li>
        <li>状态变更请求使用 CSRF Cookie 做双提交校验。</li>
        <li>API Key 不写入 localStorage，也不进入浏览器 bundle。</li>
        <li>数据存储在部署者配置的 SQLite 或 MySQL 中。</li>
      </ul>

      <h2>第三方服务</h2>
      <p>
        系统可能调用 baostock、mootdx 和 DeepSeek 获取行情、K 线或分析结果；具体请求由部署者配置。
      </p>

      <h2>联系</h2>
      <p>如对数据处理有疑问，请联系部署该系统的管理员。</p>

      <a class="legal-back" href="/welcome/">← 返回 Backing 介绍页</a>
    </main>
  </body>
</html>
```

- [ ] **Step 4: 创建条款页**

创建 `frontend/public/legal/terms.html`：

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>使用条款｜Backing</title>
    <meta name="robots" content="noindex,follow" />
    <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
    <link rel="stylesheet" href="/welcome/landing.css" />
  </head>
  <body class="legal-page">
    <header class="legal-header">
      <div class="container">
        <a class="wordmark" href="/welcome/" aria-label="Backing 首页">
          <svg
            class="wordmark-mark"
            width="20"
            height="20"
            viewBox="0 0 20 20"
            aria-hidden="true"
          >
            <rect x="3" y="9" width="3" height="8" rx="1" fill="currentColor"></rect>
            <rect x="8.5" y="5" width="3" height="12" rx="1" fill="currentColor"></rect>
            <rect x="14" y="2" width="3" height="15" rx="1" fill="var(--lp-accent)"></rect>
          </svg>
          <span>Backing</span>
        </a>
      </div>
    </header>
    <main class="container legal-main">
      <h1>使用条款</h1>
      <p>使用 Backing 即表示你理解并同意以下边界。</p>

      <h2>研究与模拟</h2>
      <p>
        Backing 只用于 A 股研究、回测、AI 分析和模拟交易，不接券商，不执行实盘交易。
      </p>

      <h2>不构成投资建议</h2>
      <p>系统输出、回测结果和 AI 分析都不构成投资建议，也不承诺任何收益。</p>

      <h2>数据与可用性</h2>
      <p>
        行情和数据可能延迟、缺失或不可用；系统按现状提供，不提供明示或暗示的担保。
      </p>

      <h2>账户与密钥</h2>
      <p>你负责保管 API Key 和部署环境的安全。不要在不信任的设备上登录。</p>

      <h2>使用限制</h2>
      <p>不要用本系统从事违法活动、传播虚假信息或干扰第三方服务。</p>

      <a class="legal-back" href="/welcome/">← 返回 Backing 介绍页</a>
    </main>
  </body>
</html>
```

- [ ] **Step 5: 修改 app shell**

编辑 `frontend/index.html`，把：

```html
<link rel="icon" type="image/svg+xml" href="/vite.svg" />
```

改成：

```html
<meta name="robots" content="noindex,nofollow" />
<link rel="icon" type="image/svg+xml" href="/favicon.svg" />
```

- [ ] **Step 6: 验证静态文件和 noindex**

```bash
cd frontend
grep -c "noindex,nofollow" index.html
ls public/legal/privacy.html public/legal/terms.html public/favicon.svg public/robots.txt
```

Expected: `index.html` 命中 1 次；四个文件都存在。

- [ ] **Step 7: 检查点**

不要 commit。向用户汇报法律页和 SEO 文件已创建，等待登录跳转。

---

## Task 8: 写失败 e2e 测试（未登录跳转和登录回跳）

**Files:**
- Create: `frontend/e2e/auth-redirect.spec.ts`

- [ ] **Step 1: 写测试**

创建 `frontend/e2e/auth-redirect.spec.ts`：

```ts
import { expect, test } from '@playwright/test'

test.describe('auth redirect and login next', () => {
  test.beforeEach(async ({ page }) => {
    await page.route('**/api/v1/auth/me', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ authenticated: false }),
      }),
    )
    await page.route('**/api/v1/stocks**', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ items: [], total: 0, nextCursor: null }),
      }),
    )
  })

  test('unauthenticated app route redirects to welcome with next', async ({
    page,
  }) => {
    await page.goto('/stocks')
    await expect(page).toHaveURL(/\/welcome\/\?next=%2Fstocks$/)
  })

  test('login returns to the next path and links back to welcome', async ({
    page,
  }) => {
    await page.route('**/api/v1/auth/session', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true }),
      }),
    )
    await page.goto('/login?next=%2Fstocks')
    await expect(
      page.getByRole('link', { name: '了解 Backing' }),
    ).toHaveAttribute('href', '/welcome/')
    await page.getByPlaceholder('API Key').fill('test-key')
    await page.getByRole('button', { name: /登\s*录/ }).click()
    await expect(page).toHaveURL(/\/stocks$/)
  })
})
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd frontend
npx playwright test e2e/auth-redirect.spec.ts
```

Expected: FAIL。未登录仍跳到 `/login`，登录页没有“了解 Backing”链接，`next` 不生效。

- [ ] **Step 3: 检查点**

不要 commit。向用户汇报测试已写好并按预期失败，接下来改 `App.tsx` 和 `Login.tsx`。

---

## Task 9: Login 和 App 的 next 跳转

**Files:**
- Modify: `frontend/src/pages/Login.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: 修改 Login.tsx**

把 `frontend/src/pages/Login.tsx` 改成：

```tsx
import { useState } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { Button, Form, Input, Typography, Alert } from 'antd'
import { LockOutlined } from '@ant-design/icons'
import { loginWithApiKey } from '../services/api'
import { safeNextPath } from '../utils/nextPath'

const { Title, Paragraph } = Typography

interface LoginFormValues {
  apiKey: string
}

/**
 * 登录页：提交一次 API key 换取短期 HttpOnly session cookie。
 *
 * API key 只在本次请求中出现（内存态），随后即被丢弃——不写入
 * localStorage、不进入 bundle、不随后续请求发送。
 */
export default function Login() {
  const navigate = useNavigate()
  const location = useLocation()
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const params = new URLSearchParams(location.search)
  const nextFromQuery = safeNextPath(params.get('next'))
  const nextFromState = safeNextPath(
    (location.state as { from?: string } | null)?.from ?? null,
  )
  const from = nextFromQuery || nextFromState || '/'

  const onFinish = async (values: LoginFormValues) => {
    setSubmitting(true)
    setError(null)
    try {
      await loginWithApiKey(values.apiKey.trim())
      navigate(from, { replace: true })
    } catch {
      setError('登录失败：API Key 无效或服务不可用，请检查后重试')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <Title level={3} className="login-title">
          量化系统
        </Title>
        <Paragraph type="secondary" className="login-subtitle">
          请输入 API Key 登录（密钥仅本次提交，会话由 HttpOnly Cookie 维持）
        </Paragraph>
        {error && (
          <Alert type="error" showIcon message={error} style={{ marginBottom: 16 }} />
        )}
        <Form<LoginFormValues>
          layout="vertical"
          onFinish={onFinish}
          requiredMark={false}
        >
          <Form.Item
            name="apiKey"
            rules={[{ required: true, message: '请输入 API Key' }]}
          >
            <Input.Password
              prefix={<LockOutlined />}
              placeholder="API Key"
              autoFocus
              autoComplete="current-password"
            />
          </Form.Item>
          <Button type="primary" htmlType="submit" block loading={submitting}>
            登录
          </Button>
        </Form>
        <Link
          to="/welcome/"
          style={{
            display: 'inline-block',
            marginTop: 16,
            fontSize: 13,
            color: 'var(--color-text-secondary)',
          }}
        >
          了解 Backing
        </Link>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: 修改 App.tsx**

在 `frontend/src/App.tsx` 中，`App` 组件之前加两个小工具组件：

```tsx
function RedirectTo({ to }: { to: string }) {
  useEffect(() => {
    window.location.replace(to)
  }, [to])

  return (
    <div className="route-loading" role="status" aria-live="polite">
      正在加载…
    </div>
  )
}
```

把未认证分支改成：

```tsx
  if (authState === 'unauthenticated') {
    const isLogin = location.pathname === '/login'
    const isWelcome = location.pathname === '/welcome/'

    if (!isLogin && !isWelcome) {
      const next = `${location.pathname}${location.search}`
      return <RedirectTo to={`/welcome/?next=${encodeURIComponent(next)}`} />
    }

    return (
      <Suspense fallback={<div className="route-loading">加载登录页…</div>}>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </Suspense>
    )
  }
```

在 `if (authState === 'unknown')` 之后、`if (authState === 'unauthenticated')` 之前加：

```tsx
  if (location.pathname === '/welcome') {
    return <RedirectTo to={`/welcome/${location.search}`} />
  }
```

注意：这个 `/welcome` 无斜杠的处理必须放在未认证分支之前，否则未认证用户会先被送去 `/welcome/?next=%2Fwelcome`，形成错误跳转。

同时，已登录分支的 `/login` 路由不能直接 `Navigate to="/"`，否则登录成功后的 auth 状态切换会抢先覆盖 `Login` 里的 `navigate(from)`。在 `RedirectTo` 之后加：

```tsx
function LoginRedirect() {
  const location = useLocation()
  const params = new URLSearchParams(location.search)
  const next =
    safeNextPath(params.get('next')) ||
    safeNextPath((location.state as { from?: string } | null)?.from ?? null) ||
    '/'
  return <Navigate to={next} replace />
}
```

并在 `App.tsx` 顶部加 `import { safeNextPath } from './utils/nextPath'`，把已登录分支的：

```tsx
<Route path="/login" element={<Navigate to="/" replace />} />
```

改成：

```tsx
<Route path="/login" element={<LoginRedirect />} />
```

- [ ] **Step 3: 运行类型检查和 auth e2e**

```bash
cd frontend
npm run typecheck
npx playwright test e2e/auth-redirect.spec.ts
```

Expected: typecheck PASS；2 个 e2e 测试 PASS。

- [ ] **Step 4: 检查点**

不要 commit。向用户汇报未登录跳转和登录回跳已通过，等待完整验收。

---

## Task 10: 完整验收与兜底

**Files:**
- Read: `frontend/public/welcome/index.html`
- Read: `frontend/public/welcome/landing.css`
- Read: `frontend/public/welcome/landing.js`
- Read: `frontend/src/App.tsx`
- Read: `frontend/src/pages/Login.tsx`

- [ ] **Step 1: 启动 dev server 并验证静态页**

```bash
cd frontend
npm run dev -- --host 127.0.0.1
```

另开一个终端：

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:5174/welcome/
curl -s http://127.0.0.1:5174/welcome/ | grep -c "从 K 线到模拟成交"
curl -s http://127.0.0.1:5174/ | grep -c "noindex,nofollow"
```

Expected: 状态码 `200`；源码命中 `1`；app shell 命中 `1`。

如果 `/welcome/` 返回的是 SPA 登录页，执行下面的兜底：

在 `frontend/vite.config.ts` 的 `plugins` 数组里加：

```ts
    {
      name: 'welcome-directory-index',
      configureServer(server) {
        server.middlewares.use((req, _res, next) => {
          if (req.url === '/welcome' || req.url === '/welcome/') {
            req.url = '/welcome/index.html'
          }
          next()
        })
      },
      configurePreviewServer(server) {
        server.middlewares.use((req, _res, next) => {
          if (req.url === '/welcome' || req.url === '/welcome/') {
            req.url = '/welcome/index.html'
          }
          next()
        })
      },
    },
```

然后重启 dev server，重跑上面的 curl 和全部 e2e。

- [ ] **Step 2: 跑完整测试**

```bash
cd frontend
npx prettier --write src/utils/nextPath.ts src/utils/nextPath.test.ts src/pages/Login.tsx src/App.tsx e2e/landing.spec.ts e2e/auth-redirect.spec.ts
npm run typecheck
npm run lint
npm run format:check
npm run build
npm test
npm run test:e2e
```

Expected: 全部 PASS。`npm run build` 末尾的 `check:bundle` 不能报 chunk 预算超限。

- [ ] **Step 3: 验证构建产物**

```bash
ls -lh dist/welcome/index.html dist/welcome/landing.css dist/welcome/landing.js
ls -lh dist/welcome/assets
grep -c "从 K 线到模拟成交" dist/welcome/index.html
grep -c "noindex,nofollow" dist/index.html
```

Expected: 静态文件都在；HTML 文案命中；`dist/index.html` 有 noindex。

- [ ] **Step 4: 手工验收**

启动 `npm run dev`，在浏览器检查：

1. `/welcome/` 在 375、768、1024、1440 四个宽度无横向滚动。
2. Tab 键走完导航、CTA、FAQ、footer；focus ring 可见。
3. 手机宽度打开菜单，Escape 关闭，焦点回到汉堡按钮。
4. 开启系统 reduced motion，标签文字直接可见，没有位移动画。
5. 关闭 JavaScript，文案、FAQ、法律链接仍然可见。
6. 未登录访问 `/stocks/600519`，落到 `/welcome/?next=%2Fstocks%2F600519`；点击登录并登录后回到 `/stocks/600519`。
7. `/legal/privacy.html`、`/legal/terms.html` 可打开，返回链接正常。
8. 页面没有背景渐变（Hero 文字渐变除外）、没有单边卡片边框、没有斜体、没有超粗字。

- [ ] **Step 5: 最终检查点**

不要 commit。向用户汇报：所有测试和手工验收结果，附上未通过项（如果有）和修复建议。等待用户决定是否提交。

---

## 自检

**Spec coverage**

- 5.1 导航：Task 4/5/6。
- 5.2 Hero：Task 4/5。
- 5.3 标签揭示：Task 4/5/6。
- 5.4 能力：Task 4/5。
- 5.5 工作流：Task 4/5。
- 5.6 真实界面：Task 2/4/5。
- 5.7 边界：Task 4/5。
- 5.8 FAQ：Task 4/5。
- 5.9 最终 CTA：Task 4/5。
- 5.10 Footer：Task 4/5。
- 6 视觉系统：Task 5。
- 7.1 静态路径：Task 4。
- 7.2 文件变更：全部任务。
- 7.3 路由与登录跳转：Task 1/8/9。
- 7.4 SEO：Task 4/7/10。
- 7.5 截图与 OG：Task 2。
- 7.6 构建与服务：Task 10。
- 8 内容真实性与合规：Task 4/7。
- 9 测试与验收：Task 1/3/6/8/9/10。
- 10 风险与缓解：Task 10 兜底。
- 11 上线前补充：不在本轮实现，Task 10 只做本地验证。
- 12 不做清单：文件结构 and commit policy。

**Placeholder scan**

- 无 `TBD`、`TODO`、`implement later`。
- 唯一条件分支是 `/welcome/` 的 Vite 兜底，带完整代码和明确触发条件。
- 截图大于 300KB 的降级路径带完整代码和明确触发条件。

**Type / 名称一致性**

- `safeNextPath` 在 `nextPath.ts`、`Login.tsx`、`landing.js` 中同名同语义。
- `next` 参数统一用 `encodeURIComponent` 编码，`URLSearchParams` 解码。
- `RedirectTo` 的 prop 是 `to`，在 App 中一致使用。
- HTML 的 `data-tagline`、`data-reveal`、`.nav-toggle`、`.mobile-menu`、`.tagline-word`、`.faq-item` 与 CSS/JS/e2e 选择器一致。
- 截图脚本的 `RealtimeIndex` 使用 `symbol/close`，`DashboardSummary.indices` 使用 `code/value`，与前端类型一致。
