import { expect, test, type Page } from '@playwright/test'
import { backtest, mockResearchApi, strategies } from './fixtures/research'

async function setup(page: Page) {
  await mockResearchApi(page)
  await page.addInitScript(() => {
    for (const [key, value] of Object.entries({
      backing_strategies_selectedStrategy: 'ma_cross',
      backing_strategies_stockCode: 'sh.600000',
    })) {
      if (sessionStorage.getItem(key) === null)
        sessionStorage.setItem(key, JSON.stringify(value))
    }
  })
  const submitted: Record<string, unknown>[] = []
  await page.route('**/api/v1/strategies/backtest', async (route) => {
    const request = route.request().postDataJSON() as Record<string, unknown>
    submitted.push(request)
    await route.fulfill({
      json: {
        ...backtest,
        ...request,
        execution_metadata: {
          corporate_action_mode: request.corporate_action_mode,
          dividend_tax_rate: request.dividend_tax_rate,
          data_provenance: { adjustment: request.price_source },
        },
      },
    })
  })
  return submitted
}

async function selectStock(page: Page, name: string) {
  await page.locator('#strategy-stock').fill(name)
  await page
    .locator('.ant-select-item-option')
    .filter({ hasText: name })
    .first()
    .click()
}

async function navigate(page: Page, href: string) {
  await page.locator(`.shell-sidebar a[href="${href}"]`).click()
}

test('an incoming stock link allows another stock, submits it, and can be cleared', async ({
  page,
}) => {
  const submitted = await setup(page)
  await page.goto('/strategies?stock=sh.600000&keep=1')
  await selectStock(page, '万科')
  await expect(page).toHaveURL(/stock=sz\.000002/)
  await expect(page).toHaveURL(/keep=1/)
  await page.getByRole('button', { name: '执行回测', exact: true }).click()
  await expect(page.locator('.strategy-saved-context')).toContainText('sz.000002')
  expect(submitted[0].stock_code).toBe('sz.000002')
  const select = page
    .locator('.ant-select')
    .filter({ has: page.locator('#strategy-stock') })
  await select.hover()
  await select.locator('.ant-select-clear').click()
  await expect(page).not.toHaveURL(/stock=/)
  await expect(
    page.getByRole('button', { name: '执行回测', exact: true }),
  ).toBeDisabled()
})

test('edited parameters survive strategy changes, navigation and reload', async ({
  page,
}) => {
  await setup(page)
  await page.goto('/strategies')
  const short = page.locator('#strategy-param-short_window')
  await short.fill('8')
  await short.blur()
  const catalog = page.locator('.strategy-catalog-disclosure')
  if (!(await catalog.getAttribute('open'))) await catalog.locator('summary').click()
  await page.getByRole('button', { name: /^动量策略/ }).click()
  await expect(page.locator('#strategy-param-lookback')).toBeVisible()
  await catalog.locator('summary').click()
  await page.getByRole('button', { name: /^均线交叉/ }).click()
  await expect(short).toHaveValue('8')
  await navigate(page, '/history')
  await expect(
    page.getByRole('heading', { name: '回测历史', exact: true }),
  ).toBeVisible()
  await navigate(page, '/strategies')
  await expect(short).toHaveValue('8')
  await page.reload()
  await expect(short).toHaveValue('8')
})

test('a completed backtest restores results and viewing position without rerunning', async ({
  page,
}) => {
  const submitted = await setup(page)
  await page.goto('/strategies?stock=sh.600000')
  await page.locator('#strategy-param-short_window').fill('8')
  await page.getByRole('button', { name: '执行回测', exact: true }).click()
  await expect(page.getByRole('tab', { name: '绩效指标' })).toHaveAttribute(
    'aria-selected',
    'true',
  )
  await expect(page.locator('.strategy-saved-context')).toContainText(
    '绩效与交易记录对应这次已保存运行',
  )
  await page.getByRole('tab', { name: '交易记录' }).click()
  await navigate(page, '/history')
  await expect(
    page.getByRole('heading', { name: '回测历史', exact: true }),
  ).toBeVisible()
  await navigate(page, '/strategies')
  await expect(page.locator('.strategy-saved-context')).toContainText('#41')
  await expect(page.getByRole('tab', { name: '交易记录' })).toHaveAttribute(
    'aria-selected',
    'true',
  )
  await page.reload()
  await expect(page.getByRole('tab', { name: '交易记录' })).toHaveAttribute(
    'aria-selected',
    'true',
  )
  expect(submitted).toHaveLength(1)
  await page.locator('.strategy-execution-options summary').click()
  await page
    .locator('.ant-select')
    .filter({ has: page.locator('#research-corporate-actions') })
    .locator('.ant-select-selector')
    .click()
  await page.locator('#research-corporate-actions').press('ArrowDown')
  await page.locator('#research-corporate-actions').press('Enter')
  await expect(page.locator('.strategy-saved-context')).toContainText('当前配置已调整')
  await selectStock(page, '万科')
  await page.getByRole('button', { name: '恢复本次配置' }).click()
  await expect(page).toHaveURL(/stock=sh\.600000/)
  await expect(page.locator('#strategy-param-short_window')).toHaveValue('8')
  await expect(page.locator('.strategy-saved-context')).toContainText(
    '绩效与交易记录对应这次已保存运行',
  )
  expect(submitted).toHaveLength(1)
  await expect(
    page.locator('.strategy-saved-context').getByRole('link', { name: '查看历史' }),
  ).toHaveAttribute('href', '/history?result=41')
})

test('changing stock removes the previous candles even when new data fails', async ({
  page,
}) => {
  await setup(page)
  await page.goto('/strategies')
  await page.getByRole('button', { name: '执行回测', exact: true }).click()
  await expect(page.getByRole('tab', { name: '绩效指标' })).toHaveAttribute(
    'aria-selected',
    'true',
  )
  await page.getByRole('tab', { name: '行情与信号' }).click()
  await expect(page.locator('.strategy-chart-preview canvas')).toHaveCount(1)
  let release!: () => void
  const gate = new Promise<void>((resolve) => {
    release = resolve
  })
  await page.route('**/api/v1/stocks/sz.000002/kline*', async (route) => {
    await gate
    await route.fulfill({ status: 503, json: { detail: 'unavailable' } })
  })
  try {
    await selectStock(page, '万科')
    await expect(page.locator('.strategy-chart-preview canvas')).toHaveCount(0)
  } finally {
    release()
  }
  await expect(page.locator('.strategy-chart-preview canvas')).toHaveCount(0)
})

test('malformed persisted form values fall back to usable defaults', async ({
  page,
}) => {
  await setup(page)
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.addInitScript(() => {
    sessionStorage.setItem('backing_strategies_dateRange', 'null')
    sessionStorage.setItem('backing_strategies_initialCapital', '{"bad":true}')
    sessionStorage.setItem('backing_strategies_priceSource', '"unknown"')
    sessionStorage.setItem('backing_strategies_savedRun', '{"version":1,"result":null}')
  })
  await page.goto('/strategies')
  await expect(page.locator('#strategy-dates')).toHaveValue(/^\d{4}-\d{2}-\d{2}$/)
  await expect(page.locator('#strategy-capital')).toHaveValue('100,000')
  await expect(page.locator('.strategy-saved-context')).toHaveCount(0)
  await expect(
    page.getByRole('button', { name: '执行回测', exact: true }),
  ).toBeEnabled()
  expect(errors).toEqual([])
})

test('a changed catalog refetched on reconnect preserves edited parameters', async ({
  page,
  context,
}) => {
  await setup(page)
  await page.goto('/strategies')
  await page.locator('#strategy-param-short_window').fill('8')
  await page.locator('#strategy-param-short_window').blur()
  await page.route('**/api/v1/strategies', (route) =>
    route.fulfill({
      json: strategies.map((strategy) => ({
        ...strategy,
        description: `${strategy.description} updated`,
      })),
    }),
  )
  await page.clock.setFixedTime(new Date(Date.now() + 6 * 60_000))
  await context.setOffline(true)
  const refreshed = page.waitForResponse(
    (response) => new URL(response.url()).pathname === '/api/v1/strategies',
  )
  await context.setOffline(false)
  await refreshed
  await expect(page.locator('#strategy-param-short_window')).toHaveValue('8')
})
