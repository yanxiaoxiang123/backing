import { expect, test, type Page, type Route } from '@playwright/test'

async function json(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  })
}

async function mockApi(page: Page) {
  let authenticated = false
  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url())
    const path = url.pathname

    if (path.endsWith('/auth/me')) return json(route, { authenticated })
    if (path.endsWith('/auth/session')) {
      authenticated = true
      return json(route, { authenticated: true })
    }
    if (path.endsWith('/watchlist')) {
      return json(route, {
        items: [
          {
            id: 1,
            stock_code: 'sh.600000',
            stock_name: '浦发银行',
            added_at: '2026-08-27T01:00:00Z',
          },
        ],
        total: 1,
      })
    }
    if (path.endsWith('/realtime/indices')) {
      return json(route, {
        success: true,
        data: [
          {
            symbol: 'sh.000001',
            name: '上证指数',
            close: 3200,
            change: 12,
            change_percent: 0.38,
            prev_close: 3188,
          },
        ],
      })
    }
    if (path.includes('/realtime/quotes')) {
      return json(route, {
        success: true,
        data: [
          {
            symbol: 'SH600000',
            open: 10,
            high: 10.3,
            low: 9.9,
            close: 10.2,
            volume: 1_200_000,
            amount: 12_000_000,
            change: 0.2,
            change_percent: 2,
            prev_close: 10,
          },
        ],
      })
    }
    if (path.includes('/realtime/sh.600000')) {
      return json(route, {
        success: true,
        code: 'SH600000',
        data: [
          {
            date: '2026-08-26',
            open: 10,
            high: 10.3,
            low: 9.9,
            close: 10.2,
            volume: 1_200_000,
            amount: 12_000_000,
            symbol: 'SH600000',
          },
        ],
      })
    }
    if (path.endsWith('/dashboard'))
      return json(route, { recent_activity: [], alerts: [] })
    if (path.endsWith('/stocks/sh.600000/overview')) {
      return json(route, {
        stock: {
          id: 1,
          code: 'SH600000',
          name: '浦发银行',
          market: 'sh',
          created_at: '2026-08-27T00:00:00Z',
        },
        quote: {
          id: 1,
          code: 'SH600000',
          name: '浦发银行',
          current_price: 10.2,
          high: 10.3,
          low: 9.9,
          volume: 1_200_000,
          change: 0.2,
          change_percent: 2,
        },
        watchlisted: true,
        technical: null,
        recent_analysis: [],
      })
    }
    if (path.endsWith('/agent-chats/status')) {
      return json(route, { backend: 'fake', available: false, reason: 'e2e' })
    }
    if (path.endsWith('/agent-chats')) return json(route, { threads: [], total: 0 })
    if (path.endsWith('/stocks')) {
      return json(route, [
        {
          id: 1,
          code: 'SH600000',
          name: '浦发银行',
          market: 'sh',
          created_at: '2026-08-27T00:00:00Z',
        },
      ])
    }
    return json(route, {})
  })
}

async function login(page: Page) {
  await page.goto('/login')
  await page.getByPlaceholder('API Key').fill('e2e-key')
  await page.getByRole('button', { name: /登\s*录/ }).click()
  await expect(page).toHaveURL(/\/$/)
}

test.describe('研究终端桌面主流程', () => {
  test.beforeEach(async ({ page }) => {
    await mockApi(page)
  })

  test('登录后从仪表盘进入个股并切换 K 线周期', async ({ page }) => {
    await login(page)
    await expect(page.getByRole('heading', { name: '市场概览' })).toBeVisible()
    await expect(page.locator('tbody tr').first()).toContainText('浦发银行')
    await page.locator('tbody tr').first().click()
    await expect(page).toHaveURL(/\/stocks\/sh\.600000$/)
    await expect(page.getByRole('heading', { name: 'K 线与成交量' })).toBeVisible()
    await page.getByRole('button', { name: '周K' }).click()
    await expect(page.getByRole('button', { name: '周K' })).toHaveClass(/active/)
  })

  test('报告中心可进入工作台并保留股票研究预填', async ({ page }) => {
    await login(page)
    await page.goto('/agent')
    await expect(page.getByRole('heading', { name: '分析报告' })).toBeVisible()
    await page.goto('/workspace?stock=sh600000')
    await expect(page.getByLabel('聊天输入')).toHaveValue(/分析一下 sh\.600000/)
  })
})
