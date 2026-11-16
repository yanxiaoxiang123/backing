import { expect, test, type Page } from '@playwright/test'
import { historyRecords, mockHistoryApi } from './fixtures/history'

async function chartState(page: Page, action?: 'zoom' | 'hide') {
  return page.evaluate(async (action) => {
    const source = performance
      .getEntriesByType('resource')
      .find((resource) => /echartsCustom.*\.(js|ts)/.test(resource.name))!.name
    const { default: core } = await import(source)
    const chart = core.getInstanceByDom(
      document.querySelector('.history-equity-panel > div[role="img"]'),
    )
    if (action === 'zoom')
      chart.dispatchAction({ type: 'dataZoom', start: 25, end: 70 })
    if (action === 'hide')
      chart.dispatchAction({ type: 'legendUnSelect', name: '组合价值' })
    const option = chart.getOption()
    return {
      zoom: option.dataZoom.map(({ start, end }: { start: number; end: number }) => ({
        start,
        end,
      })),
      values: option.series[0].data,
    }
  }, action)
}

test('history restores URL filters, pagination and detail across reload and back navigation', async ({
  page,
}) => {
  const requests = await mockHistoryApi(page)
  await page.goto('/history?stock=sh.600000&page=2&page_size=10&sort=return&result=43')
  const detail = page.getByRole('dialog', { name: /回测详情/ })
  await expect(detail).toContainText('#43')
  await expect(detail.getByText('0.00%', { exact: true }).first()).toHaveClass(
    /price-flat/,
  )
  expect(
    requests.some(
      (request) =>
        request.includes('skip=10') && request.includes('stock_code=sh.600000'),
    ),
  ).toBeTruthy()
  await page.reload()
  await expect(page.getByRole('dialog', { name: /回测详情/ })).toContainText('#43')
  await page.getByRole('button', { name: '关闭', exact: true }).click()
  await expect(page).toHaveURL(/page=2/)
  await expect(page.getByLabel('筛选股票代码')).toHaveValue('sh.600000')
  await page.getByLabel('筛选策略').fill('momentum')
  await expect(page).toHaveURL(/strategy=momentum/)
  await expect(page).toHaveURL(/page=1/)
  await expect(page.locator('.ant-table-tbody tr[data-row-key]')).toHaveCount(5)
  await page.getByRole('button', { name: /查看/ }).first().click()
  await page.getByRole('button', { name: '下一条' }).click()
  await expect(page.getByRole('dialog', { name: /回测详情/ })).toContainText(
    '本页第 2 / 5 条',
  )
  await page.goBack()
  await expect(page.getByRole('dialog', { name: /回测详情/ })).not.toBeVisible()
  await expect(page.getByLabel('筛选策略')).toHaveValue('momentum')
})

test('background refresh preserves readable rows without fading the list', async ({
  page,
}) => {
  await mockHistoryApi(page)
  await page.goto('/history')
  const rows = page.locator('.ant-table-tbody tr[data-row-key]')
  await expect(rows).toHaveCount(20)
  let release!: () => void
  const gate = new Promise<void>((resolve) => {
    release = resolve
  })
  await page.route('**/api/v1/backtest/results*', async (route) => {
    await gate
    await route.fulfill({
      json: historyRecords.slice(0, 20),
      headers: { 'x-total-count': '26' },
    })
  })
  await page.getByRole('button', { name: '刷新记录' }).click()
  await expect(page.getByRole('status').filter({ hasText: '更新中' })).toBeVisible()
  await expect(rows).toHaveCount(20)
  await expect(page.locator('.ant-spin-spinning')).toHaveCount(0)
  release()
  await expect(page.getByRole('button', { name: '刷新记录' })).toBeVisible()
})

test('initial load uses a skeleton and refresh errors preserve the last readable results', async ({
  page,
}) => {
  await mockHistoryApi(page)
  let release!: () => void
  const gate = new Promise<void>((resolve) => {
    release = resolve
  })
  let fail = false
  await page.route('**/api/v1/backtest/results*', async (route) => {
    await gate
    return fail
      ? route.fulfill({ status: 503, json: { detail: '暂时不可用' } })
      : route.fulfill({
          json: historyRecords.slice(0, 20),
          headers: { 'x-total-count': '26' },
        })
  })
  await page.goto('/history')
  await expect(page.getByLabel('正在加载历史记录')).toBeVisible()
  release()
  await expect(page.locator('.ant-table-tbody tr[data-row-key]')).toHaveCount(20)
  fail = true
  await page.getByRole('button', { name: '刷新记录' }).click()
  await expect(page.getByText('更新失败，以下保留上次记录')).toBeVisible()
  await expect(page.locator('.ant-table-tbody tr[data-row-key]')).toHaveCount(20)
  await expect(page.locator('.ant-spin-spinning')).toHaveCount(0)
})

test('detail shows missing metrics as dashes and can recover a failed detail request', async ({
  page,
}) => {
  await mockHistoryApi(page)
  let failed = true
  await page.route('**/api/v1/backtest/41', (route) =>
    failed
      ? route.fulfill({ status: 404, json: { detail: '记录不存在' } })
      : route.fulfill({
          json: { ...historyRecords[0], sharpe_ratio: null, max_drawdown: null },
        }),
  )
  await page.goto('/history?result=41')
  await expect(page.getByText('加载详情失败，记录可能已被删除')).toBeVisible({
    timeout: 15000,
  })
  failed = false
  await page.getByRole('button', { name: /重\s*试/ }).click()
  const metrics = page.locator('.backtest-detail-metrics')
  await expect(metrics).toContainText('+5.20%')
  await expect(metrics.locator('.metric-card__value').nth(2)).toHaveText('—')
  await expect(metrics.locator('.metric-card__value').nth(3)).toHaveText('—')
  await expect(page.getByRole('dialog').getByText('短期窗口')).toBeVisible()
})

test('history chart resets its range and remains stable after pointer release', async ({
  page,
}) => {
  await mockHistoryApi(page)
  await page.goto('/history?result=41')
  await page.locator('.history-equity-panel canvas').waitFor()
  const original = await chartState(page)
  await chartState(page, 'zoom')
  expect((await chartState(page)).zoom[0].start).toBeGreaterThan(0)
  await page.getByRole('button', { name: /重置视图/ }).click()
  expect((await chartState(page)).zoom).toEqual(original.zoom)
  expect((await chartState(page)).values).toEqual(original.values)
  await chartState(page, 'zoom')
  const canvas = page.locator('.history-equity-panel canvas')
  const box = (await canvas.boundingBox())!
  await page.mouse.move(box.x + box.width * 0.5, box.y + box.height - 15)
  await page.mouse.down()
  await page.mouse.move(box.x + box.width * 0.7, box.y + box.height - 15, { steps: 8 })
  await page.mouse.up()
  const released = await chartState(page)
  expect(released.zoom[0].start).toBeGreaterThan(25)
  await page.waitForTimeout(240)
  expect(await chartState(page)).toEqual(released)
})

test('returning from another screen restores the history list position', async ({
  page,
}) => {
  await mockHistoryApi(page)
  await page.goto('/history')
  await expect(page.locator('.ant-table-tbody tr[data-row-key]')).toHaveCount(20)
  await page.evaluate(() => window.scrollTo(0, 520))
  await expect.poll(() => page.evaluate(() => scrollY)).toBe(520)
  await page.getByRole('link', { name: '股票管理', exact: true }).click()
  await expect(page).toHaveURL(/\/stocks$/)
  await page.goBack()
  await expect(
    page.getByRole('heading', { name: '回测历史', exact: true }),
  ).toBeVisible()
  await expect.poll(() => page.evaluate(() => scrollY)).toBe(520)
})

test('shared chart reset preserves legend choices and links price and volume axes', async ({
  page,
}) => {
  await mockHistoryApi(page)
  await page.goto('/stocks/sh.600000')
  const chart = page.locator('.stock-chart-panel div[role="img"]')
  await expect(chart.locator('canvas')).toBeVisible()
  const state = (change = false) =>
    chart.evaluate(async (node, change) => {
      const source = performance
        .getEntriesByType('resource')
        .find((resource) => /echartsCustom.*\.(js|ts)/.test(resource.name))!.name
      const { default: core } = await import(source)
      const instance = core.getInstanceByDom(node)
      if (change) {
        instance.dispatchAction({ type: 'dataZoom', start: 30, end: 80 })
        instance.dispatchAction({ type: 'legendUnSelect', name: '成交量' })
      }
      const option = instance.getOption()
      return {
        zoom: option.dataZoom.map(({ start, end }: { start: number; end: number }) => ({
          start,
          end,
        })),
        selected: option.legend[0].selected,
        link: option.axisPointer[0].link,
      }
    }, change)
  const original = await state()
  await state(true)
  await page.getByRole('button', { name: '重置视图', exact: true }).click()
  const reset = await state()
  expect(reset.zoom).toEqual(original.zoom)
  expect(reset.selected['成交量']).toBe(false)
  expect(reset.link).toEqual([{ xAxisIndex: 'all' }])
})

test('mobile uses compact records, visible actions and full-width details without document overflow', async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await mockHistoryApi(page)
  await page.goto('/history?page_size=10')
  await expect(page.locator('.history-mobile-list li')).toHaveCount(10)
  const first = page.locator('.history-mobile-list li').first()
  await expect(first.getByRole('button', { name: /查看/ })).toBeVisible()
  await expect(first).toContainText('+5.20%')
  await first.getByRole('button', { name: /查看/ }).click()
  await expect(page.getByRole('dialog')).toBeVisible()
  const box = (await page.getByRole('dialog').boundingBox())!
  expect(box.width).toBeCloseTo(390, 1)
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(390)
  await page.getByRole('button', { name: '下一条' }).click()
  await expect(
    page
      .locator('.backtest-detail-metrics')
      .getByText('-2.80%', { exact: true })
      .first(),
  ).toHaveClass(/price-down/)
})
