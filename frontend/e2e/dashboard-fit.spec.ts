import { expect, test, type Page } from '@playwright/test'
import { mockDashboardApi } from './fixtures/dashboard'

async function expectFits(page: Page) {
  const geometry = await page.evaluate(() => {
    const visible = [
      ...document.querySelectorAll<HTMLElement>(
        '.dash-panel, .dash-footer, .dash-hero-actions .ant-btn, .dash-alert-actions, .dash-alert-list, .dash-table-wrap, .dash-history-note, .shell-sidebar',
      ),
    ].filter((el) => el.getClientRects().length)
    return {
      width: innerWidth,
      height: innerHeight,
      scrollWidth: document.documentElement.scrollWidth,
      scrollHeight: document.documentElement.scrollHeight,
      elements: visible.map((el) => {
        const r = el.getBoundingClientRect()
        return {
          name: el.className,
          top: r.top,
          right: r.right,
          bottom: r.bottom,
          scrollHeight: el.scrollHeight,
          clientHeight: el.clientHeight,
        }
      }),
      marketOverlap: [...document.querySelectorAll('.dash-index-cell')].some(
        (el) =>
          el.getBoundingClientRect().bottom >
          document.querySelector('.dash-breadth')!.getBoundingClientRect().top + 1,
      ),
      alertOverlap: (() => {
        const alert = document.querySelector('.dash-alert:last-child')
        if (!alert?.getClientRects().length) return false
        return (
          alert.getBoundingClientRect().bottom >
          document.querySelector('.dash-alert-actions')!.getBoundingClientRect().top + 1
        )
      })(),
    }
  })
  expect(geometry.scrollWidth).toBeLessThanOrEqual(geometry.width)
  expect(geometry.scrollHeight).toBeLessThanOrEqual(geometry.height)
  expect(geometry.marketOverlap, 'index figures must not overlap breadth').toBe(false)
  expect(geometry.alertOverlap, 'alerts must not overlap actions').toBe(false)
  for (const el of geometry.elements) {
    expect(el.top, el.name).toBeGreaterThanOrEqual(0)
    expect(el.right, el.name).toBeLessThanOrEqual(geometry.width + 1)
    expect(el.bottom, el.name).toBeLessThanOrEqual(geometry.height + 1)
    expect(el.scrollHeight, `${el.name} content must fit`).toBeLessThanOrEqual(
      el.clientHeight + 1,
    )
  }
}

test('仪表盘在常见桌面窗口与实时缩放时完整显示全部区块', async ({ page }) => {
  await mockDashboardApi(page)
  await page.goto('/')
  await expect(page.getByText('科创50')).toBeVisible()
  await expect(page.locator('.dash-table tbody tr')).toHaveCount(4)
  await expect(page.locator('.dash-alert')).toHaveCount(3)
  await expect(page.locator('.dash-history-row')).toHaveCount(2)
  for (const [width, height] of [
    [1513, 1039],
    [1568, 1003],
    [1440, 900],
    [1366, 768],
    [1280, 720],
    [1920, 1080],
    [1024, 768],
    [768, 988],
  ]) {
    await page.setViewportSize({ width, height })
    await expect(async () => expectFits(page)).toPass({ timeout: 3000 })
    await expect(page.locator('.dash-chart canvas')).toBeVisible()
    for (const panel of ['market', 'hero', 'chart', 'watchlist', 'alerts', 'history']) {
      await expect(page.locator(`.dash-${panel}`)).toBeVisible()
    }
  }
})

test('走势范围筛选真实日线，股票切换和刷新保持可用', async ({ page }) => {
  await mockDashboardApi(page)
  await page.goto('/')
  const chart = page.locator('.dash-chart-card [role="img"]')
  await expect(chart).toHaveAttribute('aria-label', /近6个月/)
  const range = page.getByRole('group', { name: '走势时间范围' })
  await range.getByRole('button', { name: '1月', exact: true }).click()
  await expect(chart).toHaveAttribute('aria-label', /近1个月/)
  const oneMonth = await chart.getAttribute('aria-label')
  await range.getByRole('button', { name: '1年', exact: true }).click()
  await expect(chart).toHaveAttribute('aria-label', /近12个月/)
  const oneYear = await chart.getAttribute('aria-label')
  const count = (value: string | null) => Number(value?.match(/，(\d+)个交易日/)?.[1])
  expect(count(oneYear)).toBeGreaterThan(count(oneMonth))
  await page.locator('.dash-chart-select .ant-select-selector').click()
  await page.getByTitle('万科A (sz.000002)', { exact: true }).click()
  await expect(chart).toHaveAttribute('aria-label', /^sz\.000002/)
  const refreshed = page.waitForResponse((response) =>
    response.url().includes('/realtime/indices'),
  )
  await page.getByRole('button', { name: '刷新数据', exact: true }).click()
  await refreshed
  await expect(page.getByRole('button', { name: '刷新数据' })).toBeEnabled()
})

test('窄屏通过内容切换访问全部区块，保持一屏可操作', async ({ page }) => {
  await mockDashboardApi(page)
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  await expect(page.getByText('科创50')).toBeVisible()
  const nav = page.getByRole('navigation', { name: '仪表盘内容' })
  for (const [width, height] of [
    [390, 844],
    [390, 667],
    [320, 740],
    [1280, 600],
  ]) {
    await page.setViewportSize({ width, height })
    for (const [label, panel] of [
      ['走势', 'chart'],
      ['自选股', 'watchlist'],
      ['任务告警', 'alerts'],
      ['最近分析', 'history'],
    ]) {
      await nav.getByRole('button', { name: label, exact: true }).click()
      await expect(page.locator(`.dash-${panel}`)).toBeVisible()
      await expect(async () => expectFits(page)).toPass({ timeout: 3000 })
    }
  }
  await page.setViewportSize({ width: 390, height: 844 })
  await page.getByRole('button', { name: '打开菜单' }).click()
  await expect(page.getByRole('dialog', { name: '导航菜单' })).toBeVisible()
})

test('行情失败可重试，空数据与长研究文本不会撑破布局', async ({ page }) => {
  await mockDashboardApi(page)
  let failed = true
  await page.route('**/api/v1/realtime/sh.600000?**', async (route) => {
    if (!failed) return route.fallback()
    await route.fulfill({
      status: 503,
      json: { error: { code: 'provider_unavailable', message: '行情服务不可用' } },
    })
  })
  await page.setViewportSize({ width: 1280, height: 720 })
  await page.goto('/')
  await expect(page.locator('.dash-chart')).toContainText('行情服务不可用')
  failed = false
  await page.locator('.dash-chart').getByRole('button', { name: '重试' }).click()
  await expect(page.locator('.dash-chart canvas')).toBeVisible()
  await expectFits(page)
  await page.route('**/api/v1/agent/history?**', (route) =>
    route.fulfill({
      json: [
        {
          id: 1,
          stock_code: 'sh.600000',
          stock_name: '浦发银行',
          analysis_date: '2026-11-05',
          mode: 'quick',
          final_signal: 'hold',
          final_confidence: 0.6,
          created_at: '2026-11-05T04:00:00Z',
          final_reason:
            '行情数据需要进一步核验，'.repeat(30) + '。补齐数据后重新研究。',
        },
      ],
    }),
  )
  await page.getByRole('button', { name: '刷新数据', exact: true }).click()
  await expect(page.locator('.dash-note')).toContainText('行情数据需要进一步核验')
  await expectFits(page)
  await page.route('**/api/v1/agent/history?**', (route) => route.fulfill({ json: [] }))
  await page.getByRole('button', { name: '刷新数据', exact: true }).click()
  await expect(page.locator('#dash-title')).toHaveText('今天还没有研究结论')
  await expect(page.locator('.dash-history')).toContainText('还没有分析记录')
  await expectFits(page)
})

test('加载中的骨架占位不会撑破一屏布局', async ({ page }) => {
  await mockDashboardApi(page)
  let release!: () => void
  const gate = new Promise<void>((resolve) => {
    release = resolve
  })
  await page.route('**/api/v1/**', async (route) => {
    const path = new URL(route.request().url()).pathname
    if (!path.includes('/auth/')) await gate
    await route.fallback()
  })
  try {
    await page.setViewportSize({ width: 1280, height: 720 })
    await page.goto('/')
    await expect(page.locator('.dash-skeleton').first()).toBeVisible()
    await expectFits(page)
    await page.setViewportSize({ width: 390, height: 667 })
    for (const label of ['走势', '自选股', '任务告警', '最近分析']) {
      await page
        .getByRole('navigation', { name: '仪表盘内容' })
        .getByRole('button', { name: label, exact: true })
        .click()
      await expect(async () => expectFits(page)).toPass({ timeout: 3000 })
    }
  } finally {
    release()
  }
  await expect(page.locator('.dash-history-row')).toHaveCount(2)
})
