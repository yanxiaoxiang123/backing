import { expect, test, type Page } from '@playwright/test'
import { mockStockListApi } from './fixtures/stockList'

async function expectFits(page: Page) {
  const geometry = await page.evaluate(() => {
    const body = document.querySelector('.stock-list-table-area')!
    const footer = document.querySelector('.stock-list-pagination')!
    const table = document.querySelector('.stock-list-table table')
    return {
      width: innerWidth,
      height: innerHeight,
      scrollWidth: document.documentElement.scrollWidth,
      scrollHeight: document.documentElement.scrollHeight,
      tableRight: table?.getBoundingClientRect().right ?? 0,
      tableBottom: table?.getBoundingClientRect().bottom ?? 0,
      footerTop: footer.getBoundingClientRect().top,
      rows: document.querySelectorAll('.ant-table-row').length,
      bodyHeight: body.clientHeight,
      bodyScroll: body.scrollHeight,
      panels: [
        ...document.querySelectorAll<HTMLElement>(
          '.stock-list-page > *, .shell-sidebar',
        ),
      ]
        .filter((el) => el.getClientRects().length)
        .map((el) => ({
          name: el.className,
          bottom: el.getBoundingClientRect().bottom,
          scroll: el.scrollHeight,
          client: el.clientHeight,
        })),
    }
  })
  expect(geometry.scrollWidth).toBeLessThanOrEqual(geometry.width)
  expect(geometry.scrollHeight).toBeLessThanOrEqual(geometry.height)
  expect(geometry.tableRight).toBeLessThanOrEqual(geometry.width)
  expect(
    geometry.tableBottom,
    'last row must stay above pagination',
  ).toBeLessThanOrEqual(geometry.footerTop + 1)
  expect(geometry.bodyScroll, 'table must fit its available space').toBeLessThanOrEqual(
    geometry.bodyHeight + 1,
  )
  for (const panel of geometry.panels) {
    expect(panel.bottom, panel.name).toBeLessThanOrEqual(geometry.height + 1)
    expect(panel.scroll, panel.name).toBeLessThanOrEqual(panel.client + 1)
  }
  return geometry.rows
}

test('股票管理按实际视口请求行数，表格与分页始终完整显示', async ({ page }) => {
  const { listRequests } = await mockStockListApi(page)
  await page.setViewportSize({ width: 1568, height: 1003 })
  await page.goto('/stocks')
  await expect(page.locator('.ant-table-row')).toHaveCount(11)
  const counts: number[] = []
  for (const [width, height] of [
    [1568, 1003],
    [1440, 900],
    [1366, 768],
    [1280, 720],
    [1920, 1080],
    [1024, 768],
    [768, 988],
    [390, 844],
    [390, 667],
    [320, 740],
    [1280, 600],
  ]) {
    await page.setViewportSize({ width, height })
    await expect(async () => {
      const count = await expectFits(page)
      expect(listRequests.some((request) => request.limit === count)).toBe(true)
    }).toPass({ timeout: 4000 })
    counts.push(await page.locator('.ant-table-row').count())
  }
  expect(new Set(counts).size).toBeGreaterThan(2)
})

test('翻页经过防抖仍保持当前页，缩小窗口保留当前标的并能恢复手动行数', async ({
  page,
}) => {
  await mockStockListApi(page)
  await page.setViewportSize({ width: 1568, height: 1003 })
  await page.goto('/stocks')
  await expect(page.locator('.ant-table-row')).toHaveCount(11)
  await page.locator('.ant-pagination-item-2').click()
  await expect(page).toHaveURL(/page=2/)
  await expect(page.locator('.stock-code-cell > strong').first()).toHaveText(
    'sz.000157',
  )
  await page.getByPlaceholder('搜索代码或名称...').focus()
  await page.getByPlaceholder('搜索代码或名称...').blur()
  await page.setViewportSize({ width: 1280, height: 720 })
  await expect(page.locator('.stock-list-table')).toContainText('中联重科')
  await expect(async () => expectFits(page)).toPass({ timeout: 3000 })
  await page.locator('.stock-page-size .ant-select-selector').click()
  await page.getByTitle('5 条 / 页', { exact: true }).click()
  await expect(page.locator('.ant-table-row')).toHaveCount(5)
  await expect(page).toHaveURL(/page_size=5/)
  await page.reload()
  await expect(page.locator('.ant-table-row')).toHaveCount(5)
  await expectFits(page)
})

test('搜索快捷键、市场过滤、本页排序和进入研究正常工作', async ({ page }) => {
  await mockStockListApi(page)
  await page.goto('/stocks')
  await expect(page.locator('.ant-table-row').first()).toBeVisible()
  await page.keyboard.press('Control+k')
  await expect(page.getByLabel('搜索股票代码或名称')).toBeFocused()
  await page.getByLabel('搜索股票代码或名称').fill('招商')
  await expect(page).toHaveURL(/q=/)
  await expect(page.locator('.ant-table-row')).toHaveCount(1)
  await expect(page.locator('.stock-list-table')).toContainText('招商银行')
  await page.getByLabel('搜索股票代码或名称').fill('')
  await page.locator('.stock-list-market .ant-select-selector').click()
  await page.getByTitle('上海', { exact: true }).click()
  await expect(page).toHaveURL(/market=sh/)
  await expect(page.locator('.ant-table-row')).toHaveCount(4)
  await page.locator('.stock-sort-direction').click()
  await expect(page.locator('.stock-code-cell > strong').first()).toHaveText(
    'sh.600000',
  )
  await page.locator('.stock-sort-direction').click()
  await expect(page.locator('.stock-code-cell > strong').first()).toHaveText(
    'sh.601169',
  )
  await page.getByRole('button', { name: '打开 北京银行 操作菜单' }).press('Enter')
  await expect(page.getByRole('menuitem', { name: /策略验证/ })).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(page).toHaveURL(/\/stocks\?/)
  await page.getByRole('button', { name: '进入研究' }).first().click()
  await expect(page).toHaveURL(/\/stocks\/sh\.601169$/)
})

test('选择股票不会误进详情，同步所选 K 线与本页原始价格使用实际代码', async ({
  page,
}) => {
  const { submissions, requests } = await mockStockListApi(page)
  await page.goto('/stocks')
  await page.getByRole('checkbox', { name: '选择 平安银行', exact: true }).check()
  await expect(page).toHaveURL(/\/stocks$/)
  await page.getByRole('button', { name: /同步所选 K 线/ }).click()
  const dialog = page.getByRole('dialog', { name: '同步K线数据' })
  await expect(dialog.getByLabel('股票代码（可选）')).toHaveValue('sz.000001')
  await dialog.getByRole('button', { name: '开始同步' }).click()
  await expect(dialog).not.toBeVisible()
  expect(
    submissions.find((request) => request.path.includes('sync-kline'))?.body,
  ).toEqual(['sz.000001'])
  const codes = await page.locator('.stock-code-cell > strong').allTextContents()
  await page.getByRole('button', { name: '补齐本页原始价格' }).click()
  await expect(page.getByText('补数完成，已核对交易日历覆盖')).toBeVisible()
  expect(
    requests.find((request) => request.path.endsWith('/data/history/sync'))?.body
      ?.codes,
  ).toEqual(codes)
  await expect(async () => expectFits(page)).toPass({ timeout: 3000 })
  await page.getByRole('button', { name: '同步股票列表', exact: true }).click()
  await expect
    .poll(() =>
      submissions.some((request) => request.path.endsWith('/stocks/sync/submit')),
    )
    .toBe(true)
})

test('窄屏覆盖详情可刷新和补数，空列表、错误与加载状态保持可恢复', async ({ page }) => {
  await mockStockListApi(page)
  await page.setViewportSize({ width: 390, height: 667 })
  await page.goto('/stocks')
  await page.getByRole('button', { name: '详情与补数' }).click()
  const dialog = page.getByRole('dialog', { name: '历史数据覆盖' })
  await expect(dialog).toContainText('版本化行情记录')
  await dialog.getByRole('button', { name: '刷新数据质量' }).click()
  await expect(dialog.getByRole('button', { name: '刷新数据质量' })).toBeEnabled()
  await dialog.getByRole('button', { name: 'Close', exact: true }).click()
  await page.getByLabel('搜索股票代码或名称').fill('没有匹配的股票')
  await expect(page.locator('.ant-table-empty')).toBeVisible()
  await expectFits(page)
  let fail = true
  await page.route('**/api/v1/stocks?**', (route) =>
    fail
      ? route.fulfill({ status: 503, json: { error: { message: '股票列表暂不可用' } } })
      : route.fallback(),
  )
  await page.reload()
  await expect(page.getByRole('button', { name: /重试/ })).toBeVisible()
  await expectFits(page)
  fail = false
  await page.getByRole('button', { name: /重试/ }).click()
  await expect(page.locator('.ant-table-empty')).toBeVisible()
})

test('加载占位在缩小窗口时仍为一屏，完成后按当前容量展示', async ({ page }) => {
  await mockStockListApi(page)
  let release!: () => void
  const gate = new Promise<void>((resolve) => {
    release = resolve
  })
  await page.route('**/api/v1/stocks?**', async (route) => {
    await gate
    await route.fallback()
  })
  try {
    await page.goto('/stocks')
    await expect(page.locator('.async-boundary')).toBeVisible()
    await expectFits(page)
    await page.setViewportSize({ width: 390, height: 667 })
    await expect(async () => expectFits(page)).toPass({ timeout: 3000 })
  } finally {
    release()
  }
  await expect(page.locator('.ant-table-row')).toHaveCount(2)
  await expectFits(page)
})
