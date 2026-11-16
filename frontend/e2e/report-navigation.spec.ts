import { expect, test, type Page } from '@playwright/test'
import { mockDashboardApi } from './fixtures/dashboard'

async function setup(page: Page) {
  await mockDashboardApi(page)
  const requested: number[] = []
  await page.route(/\/api\/v1\/agent\/\d+(?:\?.*)?$/, async (route) => {
    const id = Number(new URL(route.request().url()).pathname.split('/').pop())
    requested.push(id)
    await route.fulfill({
      json: {
        success: true,
        stock_code: id === 1 ? 'sh.600000' : 'sz.000002',
        stock_name: id === 1 ? '浦发银行' : '万科A',
        mode: 'quick',
        final_signal: 'hold',
        final_confidence: 0.55,
        final_reason: `报告 ${id} 的独立研究结论`,
        duration_s: 12,
        opinions: [],
        stages: [],
        news_items: [],
      },
    })
  })
  return requested
}

test('dashboard opens the selected saved report directly and restores it on refresh', async ({
  page,
}) => {
  await setup(page)
  await page.goto('/')
  await page.getByRole('button', { name: '打开分析报告', exact: true }).click()
  await expect(page).toHaveURL(/\/agent\?report=1$/)
  await expect(page.getByRole('dialog')).toContainText('报告 1 的独立研究结论')
  await page.reload()
  await expect(page.getByRole('dialog')).toContainText('报告 1 的独立研究结论')
  await page
    .getByRole('dialog')
    .getByRole('button', { name: 'Close', exact: true })
    .click()
  await expect(page).toHaveURL(/\/agent$/)
  await page.locator('.shell-sidebar .shell-nav-item[href="/"]').click()
  await page.locator('.dash-history-row').filter({ hasText: '万科A' }).click()
  await expect(page).toHaveURL(/report=2/)
  await expect(page.getByRole('dialog')).toContainText('报告 2 的独立研究结论')
})

test('closing a report preserves other parameters and browser history selects the right record', async ({
  page,
}) => {
  await setup(page)
  await page.goto('/agent?keep=1&report=1')
  await expect(page.getByRole('dialog')).toContainText('报告 1 的独立研究结论')
  await page
    .getByRole('dialog')
    .getByRole('button', { name: 'Close', exact: true })
    .click()
  await expect(page).toHaveURL(/\/agent\?keep=1$/)
  await page
    .getByRole('row')
    .filter({ hasText: '万科A' })
    .getByRole('button', { name: /查看/ })
    .click()
  await expect(page.getByRole('dialog')).toContainText('报告 2 的独立研究结论')
  await page.goBack()
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await page.goForward()
  await expect(page.getByRole('dialog')).toContainText('报告 2 的独立研究结论')
})

test('invalid report IDs do not fetch details and a failed deep link can retry', async ({
  page,
}) => {
  const requested = await setup(page)
  await page.goto('/agent?report=-1')
  await expect(
    page.getByRole('heading', { name: '分析报告', exact: true }),
  ).toBeVisible()
  await expect(page.getByRole('dialog')).toHaveCount(0)
  expect(requested).toEqual([])
  let fail = true
  await page.route('**/api/v1/agent/9', async (route) => {
    if (fail) return route.fulfill({ status: 404, json: { detail: 'missing report' } })
    return route.fallback()
  })
  await page.goto('/agent?report=9')
  await expect(page.getByRole('dialog')).toContainText('获取详情失败')
  fail = false
  await page
    .getByRole('dialog')
    .getByRole('button', { name: /重\s*试/ })
    .click()
  await expect(page.getByRole('dialog')).toContainText('报告 9 的独立研究结论')
})

test('a late response for the previous report cannot replace the selected report', async ({
  page,
}) => {
  await setup(page)
  let release!: () => void
  const gate = new Promise<void>((resolve) => {
    release = resolve
  })
  await page.route('**/api/v1/agent/1', async (route) => {
    await gate
    await route.fallback()
  })
  await page.goto('/agent?report=1')
  await expect(page.getByRole('dialog')).toContainText('加载分析详情')
  await page.evaluate(() => {
    window.history.pushState({}, '', '/agent?report=2')
    window.dispatchEvent(new PopStateEvent('popstate'))
  })
  try {
    await expect(page.getByRole('dialog')).toContainText('报告 2 的独立研究结论')
  } finally {
    release()
  }
  await expect(page.getByRole('dialog')).not.toContainText('报告 1 的独立研究结论')
  await expect(page).toHaveURL(/report=2/)
})
