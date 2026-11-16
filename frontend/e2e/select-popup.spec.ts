import { expect, test } from '@playwright/test'
import { mockDashboardApi } from './fixtures/dashboard'
import { mockStockListApi } from './fixtures/stockList'

test('反复缩放和切换走势股票后，下拉选项仍可见且可点击', async ({ page }) => {
  await mockDashboardApi(page)
  await page.goto('/')
  const chart = page.locator('.dash-chart-card div[role="img"]')
  await expect(chart.locator('canvas')).toBeVisible()

  // Reopen while the previous leave motion can still be active.
  for (let index = 0; index < 18; index += 1) {
    await page.setViewportSize(
      index % 2 ? { width: 1440, height: 900 } : { width: 1280, height: 720 },
    )
    await page.locator('.dash-chart-select .ant-select-selector').click()
    const code = index % 2 ? 'sh.600000' : 'sz.000002'
    const option = page.getByTitle(
      index % 2 ? '浦发银行 (sh.600000)' : '万科A (sz.000002)',
      { exact: true },
    )
    await expect(option).toBeInViewport({ timeout: 2500 })
    await option.click({ timeout: 2500 })
    await expect(chart).toHaveAttribute(
      'aria-label',
      new RegExp(`^${code.replace('.', '\\.')}`),
    )
  }
})

test('反复搜索清空和切换市场后，下拉选项仍可见且过滤正确', async ({ page }) => {
  await mockStockListApi(page)
  await page.goto('/stocks')
  await expect(page.locator('.ant-table-row').first()).toBeVisible()

  for (let index = 0; index < 18; index += 1) {
    await page.getByLabel('搜索股票代码或名称').fill('招商')
    await expect(page).toHaveURL(/q=/)
    await page.getByLabel('搜索股票代码或名称').fill('')
    await expect(page).not.toHaveURL(/q=/)
    await page.locator('.stock-list-market .ant-select-selector').click()
    const market = index % 2 ? '深圳' : '上海'
    const option = page.getByTitle(market, { exact: true })
    await expect(option).toBeInViewport({ timeout: 2500 })
    await option.click({ timeout: 2500 })
    await expect(page).toHaveURL(index % 2 ? /market=sz/ : /market=sh/)
  }
})
