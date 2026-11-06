import { expect, test } from '@playwright/test'
import { mockResearchApi } from './fixtures/research'

const pages = [
  ['/', '仪表盘'],
  ['/stocks', '股票管理'],
  ['/stocks/sh.600000', '浦发银行'],
  ['/watchlist', '自选股'],
  ['/screener', 'AI 量化选股'],
  ['/strategies?stock=sh.600000', '策略研究'],
  ['/portfolio', '组合研究'],
  ['/history', '回测历史'],
] as const

test('all research and strategy screens share the shell and fit desktop and mobile', async ({
  page,
}) => {
  test.setTimeout(60000)
  await mockResearchApi(page)
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  for (const [path, title] of pages) {
    await page.setViewportSize({ width: 1592, height: 988 })
    await page.goto(path)
    await expect(page.locator('main h1')).toHaveText(title)
    await expect(page.locator('.shell--research')).toBeVisible()
    await expect
      .poll(async () => (await page.locator('.shell-sidebar').boundingBox())?.width)
      .toBe(250)
    for (const width of [1592, 768, 390]) {
      await page.setViewportSize({ width, height: 988 })
      await expect
        .poll(() =>
          page.evaluate(() => document.documentElement.scrollWidth > innerWidth),
        )
        .toBe(false)
    }
    await expect(page.getByRole('button', { name: '打开菜单' })).toBeVisible()
  }
  expect(errors).toEqual([])
})

test('stock search still updates the URL, rows navigate, and the sync dialog opens', async ({
  page,
}) => {
  await mockResearchApi(page)
  await page.goto('/stocks')
  await page.getByPlaceholder('搜索代码或名称...').fill('招商')
  await expect(page).toHaveURL(/q=/)
  await expect(page.locator('tbody tr.ant-table-row')).toHaveCount(1)
  await expect(page.locator('tbody tr.ant-table-row')).toContainText('招商银行')
  await page.getByRole('button', { name: /同步K线数据/ }).click()
  await expect(page.getByRole('dialog', { name: '同步K线数据' })).toBeVisible()
  await page.getByRole('button', { name: 'Close', exact: true }).click()
  await page.getByRole('link', { name: '查看 招商银行 sh.600036 K线' }).press('Enter')
  await expect(page).toHaveURL(/\/stocks\/sh\.600036$/)
  await page.getByRole('button', { name: '周K', exact: true }).click()
  await expect(page.getByRole('button', { name: '周K', exact: true })).toHaveAttribute(
    'aria-pressed',
    'true',
  )
})

test('watchlist additions and confirmed removals remain available', async ({
  page,
}) => {
  await mockResearchApi(page)
  await page.goto('/watchlist')
  await page.getByLabel('股票代码').fill('招商')
  await page.getByTitle('sh.600036 - 招商银行', { exact: true }).click()
  await page.getByRole('button', { name: /添加$/, exact: false }).click()
  await expect(page.getByRole('heading', { name: '我的自选股 (3)' })).toBeVisible()
  await page
    .getByRole('button', { name: '打开 招商银行 操作菜单', exact: true })
    .press('Enter')
  await page.getByRole('menuitem', { name: /移除自选/ }).click()
  await expect(page.getByRole('dialog', { name: '移除自选股？' })).toBeVisible()
  await page
    .getByRole('dialog', { name: '移除自选股？' })
    .getByRole('button', { name: '移 除' })
    .click()
  await expect(page.getByRole('heading', { name: '我的自选股 (2)' })).toBeVisible()
  await expect(page).toHaveURL(/\/watchlist$/)
})

test('strategy selection, parameters, signals, backtest tabs and execution assumptions work', async ({
  page,
}) => {
  const requests = await mockResearchApi(page)
  await page.goto('/strategies?stock=sh.600000')
  await page.getByRole('button', { name: /均线交叉/ }).click()
  await expect(page.locator('.strategy-catalog-disclosure')).not.toHaveAttribute('open')
  await page.locator('#strategy-param-short_window').fill('7')
  await page.getByRole('button', { name: /生成信号/ }).click()
  await expect(page.getByText('信号历史表现', { exact: true })).toBeVisible()
  expect(
    requests.find((request) => request.path.endsWith('/strategies/signals'))?.body,
  ).toMatchObject({
    stock_code: 'sh.600000',
    strategy_name: 'ma_cross',
    parameters: { short_window: 7, long_window: 20 },
    price_source: 'raw',
    corporate_action_mode: 'verified',
  })
  await page.getByRole('button', { name: /执行回测/ }).click()
  await page.getByRole('tab', { name: '绩效指标', exact: true }).click()
  await expect(page.getByRole('link', { name: '#41 · 查看历史' })).toBeVisible()
  await page.getByRole('tab', { name: '交易记录', exact: true }).click()
  await expect(
    page.getByRole('cell', { name: '2026-10-03', exact: true }),
  ).toBeVisible()
  await page.locator('.strategy-execution-options > summary').click()
  await page.getByLabel('历史行情口径').press('ArrowDown')
  await page.getByTitle('旧行情 · 复权口径未知', { exact: true }).click()
  await expect(page.getByLabel('收益计算')).toBeDisabled()
  await expect(page.locator('.strategy-execution-options > summary')).toContainText(
    '仅价格收益',
  )
  await page.locator('.strategy-catalog-disclosure > summary').click()
  await page.getByLabel('搜索策略').fill('动量')
  await page.getByRole('button', { name: /动量策略/ }).click()
  await expect(page.locator('.strategy-catalog-disclosure > summary')).toContainText(
    '当前策略：动量策略',
  )
})

test('portfolio keeps its saved snapshot, replay, export and form submission', async ({
  page,
}) => {
  const requests = await mockResearchApi(page)
  await page.goto('/portfolio')
  await expect(
    page.getByRole('heading', { name: '银行股配置研究', exact: true }),
  ).toBeVisible()
  await page.getByRole('button', { name: '重放核验', exact: true }).click()
  await expect(page.getByText('快照重放一致', { exact: true })).toBeVisible()
  const download = page.waitForEvent('download')
  await page.getByRole('button', { name: '导出实验', exact: true }).click()
  expect((await download).suggestedFilename()).toBe('portfolio-portfolio-review.json')
  await page.getByLabel('股票 1', { exact: true }).fill('浦发')
  await page.getByTitle('sh.600000 - 浦发银行', { exact: true }).click()
  await page.getByLabel('股票 2', { exact: true }).fill('招商')
  await page.getByTitle('sh.600036 - 招商银行', { exact: true }).click()
  await page.getByRole('button', { name: '运行组合回测', exact: true }).click()
  await expect
    .poll(
      () =>
        requests.find(
          (request) =>
            request.path.endsWith('/portfolio-research') && request.method === 'POST',
        )?.body,
    )
    .toMatchObject({
      weights: { 'sh.600000': 0.5, 'sh.600036': 0.5 },
      initial_capital: 100000,
    })
  await page.getByText('成交明细 · 2 笔', { exact: true }).click()
  await expect(
    page.getByRole('cell', { name: '2026-10-03', exact: true }),
  ).toBeVisible()
})

test('history details and empty scan results remain honest and usable', async ({
  page,
}) => {
  await mockResearchApi(page)
  await page.goto('/history')
  await page.getByRole('button', { name: /查看/ }).click()
  const detail = page.getByRole('dialog', { name: /回测详情/ })
  await expect(detail).toBeVisible()
  await expect(detail.getByText('资金曲线', { exact: true })).toBeVisible()
  await expect(
    detail.getByRole('cell', { name: '2026-10-03', exact: true }),
  ).toBeVisible()
  await page.setViewportSize({ width: 390, height: 844 })
  await expect
    .poll(() => page.evaluate(() => document.documentElement.scrollWidth > innerWidth))
    .toBe(false)
})

test('empty lists and a completed scan with no hits keep their empty state', async ({
  page,
}) => {
  await mockResearchApi(page, { empty: true })
  await page.goto('/watchlist')
  await expect(page.getByText('暂无自选股，请在上方搜索添加')).toBeVisible()
  await page.goto('/portfolio')
  await expect(page.getByText('尚未保存组合实验', { exact: true })).toBeVisible()
  await page.goto('/screener')
  await page.getByRole('button', { name: /开始 AI 选股/ }).click()
  await expect(page.getByText('全市场扫描完成', { exact: true })).toBeVisible()
  await expect(page.getByText(/本轮没有股票同时满足筛选条件/)).toBeVisible()
  await expect(
    page.getByRole('button', { name: '开始 AI 选股', exact: true }),
  ).toHaveCount(0)
  await page.getByRole('button', { name: '重新选股', exact: true }).click()
  await expect(
    page.getByRole('button', { name: '开始 AI 选股', exact: true }),
  ).toBeEnabled()
})
