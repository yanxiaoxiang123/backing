import { expect, test } from '@playwright/test'

const stamp = '2026-10-30T15:00:00+08:00'
const envelope = (data: unknown[], extra = {}) => ({
  status: 'ok',
  data,
  provider: 'tencent',
  market_at: stamp,
  fetched_at: Date.now() / 1000,
  served_at: Date.now() / 1000,
  cache_age_ms: 0,
  stale: false,
  ...extra,
})
const snapshot = {
  indices: envelope([
    { symbol: 'sh.000001', name: '上证指数', close: 3599.02, change_percent: -1.44 },
    { symbol: 'sz.399001', name: '深证成指', close: 10833.78, change_percent: -2.73 },
    { symbol: 'sz.399006', name: '创业板指', close: 2413.63, change_percent: -4.13 },
  ]),
  quotes: envelope([
    {
      symbol: 'sh.600519',
      close: 1423.5,
      change: 12.5,
      change_percent: 0.89,
      volume: 25834,
      amount: 3678000000,
      prev_close: 1411,
      open: 1412.5,
      high: 1428.8,
      low: 1408.2,
      market_at: stamp,
    },
    {
      symbol: 'sz.300750',
      close: 259.3,
      change: -2.1,
      change_percent: -0.8,
      volume: 98000,
      amount: 2541140000,
      prev_close: 261.4,
      market_at: stamp,
    },
    {
      symbol: 'sh.600036',
      close: 38.42,
      change: 0.32,
      change_percent: 0.84,
      volume: 56000,
      amount: 215152000,
      prev_close: 38.1,
      market_at: stamp,
    },
  ]),
}
const series = (code: string) => ({
  ...envelope(
    Array.from({ length: 12 }, (_, i) => ({
      time: `2026-10-30T09:${String(30 + i).padStart(2, '0')}:00+08:00`,
      price: (code === 'sz.300750' ? 258 : 1420) + i * 0.2,
      volume: 120 + i * 13,
    })),
  ),
  code,
  trade_date: '2026-10-30',
  volume_unit: 'lots',
  volume_kind: 'interval',
})

test.beforeEach(async ({ page }) => {
  await page.route('**/api/v1/public/market', (route) =>
    route.fulfill({ json: snapshot }),
  )
  await page.route('**/api/v1/public/market/intraday?*', (route) => {
    const code = new URL(route.request().url()).searchParams.get('code') || 'sh.600519'
    return route.fulfill({ json: series(code) })
  })
})

test('chart hover enlarges the inspected point and displays day quote details', async ({
  page,
}) => {
  await page.goto('/welcome/')
  const chart = page.locator('[data-price-chart] svg')
  await expect(chart).toBeVisible()
  const box = (await chart.boundingBox())!
  await page.mouse.move(box.x + box.width * 0.35, box.y + 80)
  const tip = page.getByRole('tooltip')
  await expect(tip).toBeVisible()
  await expect(tip).toContainText('当日开盘')
  await expect(tip).toContainText('1,412.50')
  await expect(tip).toContainText('当日收盘')
  await expect(tip).toContainText('1,423.50')
  await expect(tip).toContainText('分钟成交量')
  await expect(page.locator('.chart-marker')).toHaveAttribute('r', '8')
  await chart.focus()
  await page.keyboard.press('Home')
  await expect(tip).toContainText('09:30')
  await page.keyboard.press('Escape')
  await expect(tip).toBeHidden()
})

test('intraday quote uses latest price wording before the close', async ({ page }) => {
  await page.route('**/api/v1/public/market', (route) =>
    route.fulfill({
      json: {
        ...snapshot,
        quotes: envelope([
          { ...snapshot.quotes.data[0], market_at: '2026-10-30T10:00:00+08:00' },
        ]),
      },
    }),
  )
  await page.goto('/welcome/')
  const chart = page.locator('[data-price-chart] svg')
  await chart.focus()
  await expect(page.getByRole('tooltip')).toContainText('当日最新价')
  await expect(page.getByRole('tooltip')).not.toContainText('当日收盘')
})

test('chart does not combine daily quote values from a different date', async ({
  page,
}) => {
  await page.route('**/api/v1/public/market', (route) =>
    route.fulfill({
      json: {
        ...snapshot,
        quotes: envelope([
          { ...snapshot.quotes.data[0], market_at: '2026-10-29T15:00:00+08:00' },
        ]),
      },
    }),
  )
  await page.goto('/welcome/')
  const chart = page.locator('[data-price-chart] svg')
  await chart.focus()
  await page.keyboard.press('Home')
  const tip = page.getByRole('tooltip')
  await expect(tip).toContainText('日行情日期不同')
  await expect(tip).not.toContainText('1,412.50')
})

test('renders real quote fields, chart and accessible table; changes selected stock', async ({
  page,
}) => {
  await page.goto('/welcome/')
  const board = page.locator('[data-market-board]')
  await expect(board.locator('[data-price]')).toHaveText('1,423.50')
  await expect(board.locator('[data-indices]')).toContainText('上证指数')
  await expect(board.locator('[data-quote-time]')).toContainText('2026/10/30')
  await expect(board.locator('[data-price-chart] svg')).toHaveCount(1)
  await board.getByRole('button', { name: '宁德时代', exact: true }).click()
  await expect(board.locator('[data-price]')).toHaveText('259.30')
  await expect(board.locator('[data-selected-name]')).toHaveText('宁德时代')
  await board.getByText('查看分时数据表', { exact: true }).click()
  await expect(board.locator('tbody tr')).toHaveCount(12)
  await expect(board.locator('tbody tr').first()).toContainText('258.00')
})

test('reports unavailable quotes without inventing prices and allows retry', async ({
  page,
}) => {
  let fail = true
  await page.route('**/api/v1/public/market', (route) =>
    route.fulfill({
      json: fail
        ? {
            indices: envelope([]),
            quotes: envelope([], {
              status: 'unavailable',
              reason: 'provider_unavailable',
            }),
          }
        : snapshot,
    }),
  )
  await page.goto('/welcome/')
  await expect(page.locator('[data-market-message]')).toContainText('暂不可用')
  await expect(page.locator('[data-price]')).toHaveText('—')
  fail = false
  await page.getByRole('button', { name: '重新获取行情' }).click()
  await expect(page.locator('[data-price]')).toHaveText('1,423.50')
})

test('keeps stale data explicit and never calls strategy mutation APIs', async ({
  page,
}) => {
  const mutations: string[] = []
  page.on('request', (request) => {
    if (request.method() === 'POST') mutations.push(request.url())
  })
  await page.route('**/api/v1/public/market', (route) =>
    route.fulfill({
      json: {
        ...snapshot,
        quotes: envelope(snapshot.quotes.data, { stale: true, cache_age_ms: 400000 }),
      },
    }),
  )
  await page.goto('/welcome/')
  await expect(page.locator('[data-market-message]')).toContainText('报价')
  const result = page.locator('[data-scene="result"]')
  await result.scrollIntoViewIfNeeded()
  await expect(result).toContainText('演示案例')
  expect(mutations).toEqual([])
})

test('does not let a late old-symbol response overwrite the selection', async ({
  page,
}) => {
  await page.route('**/api/v1/public/market/intraday?*', async (route) => {
    const code = new URL(route.request().url()).searchParams.get('code') || ''
    if (code === 'sh.600519') await new Promise((resolve) => setTimeout(resolve, 800))
    await route.fulfill({ json: series(code) }).catch(() => {})
  })
  await page.goto('/welcome/')
  await page.getByRole('button', { name: '宁德时代', exact: true }).click()
  await expect(page.locator('[data-chart-heading]')).toContainText('宁德时代')
  await expect(page.locator('[data-price-chart]')).toHaveAttribute(
    'data-code',
    'sz.300750',
  )
})

test('desktop scrolling activates each read-only stage', async ({ page }) => {
  await page.goto('/welcome/')
  for (const key of ['market', 'strategy', 'result']) {
    await page.locator(`[data-scene-trigger="${key}"]`).scrollIntoViewIfNeeded()
    await expect(page.locator('.cinema-stage')).toHaveAttribute(
      'data-active-scene',
      key,
    )
    await expect(page.locator(`[data-scene="${key}"]`)).toBeVisible()
  }
})

test('stops polling while the market board is offscreen', async ({ page }) => {
  let requests = 0
  await page.route('**/api/v1/public/market', (route) => {
    requests += 1
    return route.fulfill({ json: snapshot })
  })
  await page.clock.install()
  await page.goto('/welcome/')
  await expect(page.locator('[data-price]')).toHaveText('1,423.50')
  await page.locator('#faq').scrollIntoViewIfNeeded()
  await page.clock.runFor(1000)
  const before = requests
  await page.clock.runFor(90000)
  expect(requests).toBe(before)
})

test('missing turnover fields remain missing rather than zero', async ({ page }) => {
  await page.route('**/api/v1/public/market', (route) =>
    route.fulfill({
      json: {
        ...snapshot,
        quotes: envelope([{ ...snapshot.quotes.data[0], amount: null, volume: null }]),
      },
    }),
  )
  await page.goto('/welcome/')
  await expect(page.locator('[data-volume]')).toHaveText('未提供')
  await expect(page.locator('[data-amount]')).toHaveText('未提供')
})

test('preserves minute gaps and leaves unknown volumes unpainted', async ({ page }) => {
  await page.route('**/api/v1/public/market/intraday?*', (route) =>
    route.fulfill({
      json: {
        ...series('sh.600519'),
        data: [
          { time: '2026-10-30T09:30:00+08:00', price: 1420, volume: 10 },
          { time: '2026-10-30T09:31:00+08:00', price: 1421, volume: null },
          { time: '2026-10-30T09:35:00+08:00', price: 1422, volume: 20 },
        ],
      },
    }),
  )
  await page.goto('/welcome/')
  const line = page.locator('.price-line')
  await expect(line).toHaveCount(1)
  expect((await line.getAttribute('d'))?.match(/M/g)).toHaveLength(2)
  await expect(page.locator('.volume-bar')).toHaveCount(2)
})

test('old quotes do not advertise refreshing live status or a pointless retry', async ({
  page,
}) => {
  await page.route('**/api/v1/public/market', (route) =>
    route.fulfill({
      json: { ...snapshot, quotes: envelope(snapshot.quotes.data, { stale: true }) },
    }),
  )
  await page.goto('/welcome/')
  await expect(page.locator('[data-price]')).toHaveText('1,423.50')
  await expect(page.locator('[data-market-retry]')).toBeHidden()
  await expect(page.locator('[data-market-message]')).toContainText('报价时间')
})

test('marks cached indices after a refresh connection failure', async ({ page }) => {
  let calls = 0
  await page.route('**/api/v1/public/market', (route) => {
    calls += 1
    return calls === 1 ? route.fulfill({ json: snapshot }) : route.abort()
  })
  await page.clock.install()
  await page.goto('/welcome/')
  await expect(page.locator('[data-price]')).toHaveText('1,423.50')
  await page.clock.runFor(31000)
  await expect(page.locator('[data-index-source]')).toContainText('缓存')
})

test('mobile and reduced motion keep all story stages readable', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto('/welcome/')
  for (const key of ['market', 'strategy', 'result']) {
    const stage = page.locator(`[data-scene="${key}"]`)
    await stage.scrollIntoViewIfNeeded()
    await expect(stage).toBeVisible()
  }
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth > innerWidth),
  ).toBe(false)
  await expect(page.locator('main img')).toHaveCount(1)
})
