import { expect, test, type Page } from '@playwright/test'

async function mockWorkspace(page: Page, available = true) {
  const thread = {
    thread_id: 'research-bank',
    title: '浦发银行趋势研究',
    status: 'active',
    last_run_id: null,
    archived: false,
    created_at: '2026-11-05T09:00:00+08:00',
    updated_at: '2026-11-05T09:42:00+08:00',
  }
  await page.route('**/api/v1/**', async (route) => {
    const path = new URL(route.request().url()).pathname
    if (path.endsWith('/events')) {
      return route.fulfill({
        contentType: 'text/event-stream',
        body: ': connected\n\n',
      })
    }
    let body: unknown = {}
    if (path.endsWith('/auth/me')) body = { authenticated: true }
    else if (path.endsWith('/agent-chats/status'))
      body = { backend: 'native', available, reason: null }
    else if (path.endsWith('/agent-chats')) body = { threads: [thread], total: 1 }
    else if (path.includes('/agent-chats/'))
      body = {
        thread,
        turns: [
          {
            id: 1,
            thread_id: thread.thread_id,
            content: '研究浦发银行的趋势和风险',
            status: 'completed',
            final_reply: '先核对趋势与成交量，再验证策略。尚未执行回测。',
            error: null,
            end_reason: 'completed',
            created_at: thread.updated_at,
          },
        ],
        has_more: false,
      }
    else if (path.endsWith('/paper/alerts')) body = { alerts: [] }
    else if (path.endsWith('/jobs/metrics'))
      body = { started_at: thread.created_at, counters: [], durations: [] }
    else if (path.endsWith('/kline')) body = []
    await route.fulfill({ json: body })
  })
}

async function expectChatFitsViewport(page: Page) {
  const geometry = await page.evaluate(() => ({
    width: innerWidth,
    scrollWidth: document.documentElement.scrollWidth,
    inputBottom: document.querySelector('.chat-input')!.getBoundingClientRect().bottom,
    height: innerHeight,
  }))
  expect(geometry.scrollWidth).toBeLessThanOrEqual(geometry.width)
  expect(geometry.inputBottom).toBeLessThanOrEqual(geometry.height)
}

test('桌面示例只填草稿，会话与研究侧栏可折叠并保留偏好', async ({ page }) => {
  await mockWorkspace(page)
  const submitted: string[] = []
  page.on('request', (request) => {
    if (request.method() === 'POST' && request.url().endsWith('/turns'))
      submitted.push(request.url())
  })
  await page.goto('/workspace')
  await expect(
    page.getByRole('heading', { level: 1, name: 'Agent 工作台' }),
  ).toBeVisible()
  await page.getByRole('button', { name: /验证一个策略/ }).click()
  await expect(page.getByLabel('聊天输入')).toHaveValue(/5 日与 20 日均线交叉/)
  await expect(page.getByLabel('聊天输入')).toBeFocused()
  expect(submitted).toEqual([])
  await page.getByRole('button', { name: '收起会话列表' }).click()
  await page.getByRole('button', { name: '收起研究区' }).click()
  await page.reload()
  await expect(page.getByRole('button', { name: '展开会话列表' })).toBeVisible()
  await expect(page.getByRole('button', { name: '展开研究区' })).toBeVisible()
  await expectChatFitsViewport(page)
})

test('手机全宽聊天，会话与研究使用可关闭且恢复焦点的抽屉', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await mockWorkspace(page)
  await page.goto('/workspace')
  await expect(page.getByRole('button', { name: '打开会话列表' })).toBeVisible()
  await expect(page.locator('.agent-workspace-chat-sidebar')).toBeHidden()
  await expectChatFitsViewport(page)
  await page.getByRole('button', { name: '打开会话列表' }).click()
  const history = page.getByRole('dialog')
  await history.getByRole('button', { name: /^浦发银行趋势研究/ }).click()
  await expect(history).toBeHidden()
  await expect(
    page.getByText('先核对趋势与成交量，再验证策略。尚未执行回测。'),
  ).toBeVisible()
  await page.reload()
  await expect(
    page.getByText('先核对趋势与成交量，再验证策略。尚未执行回测。'),
  ).toBeVisible()
  await page.getByRole('button', { name: '打开研究面板' }).click()
  const research = page.getByRole('dialog')
  await research.getByRole('tab', { name: '证据', exact: true }).click()
  await expect(research.getByText('暂无证据条目')).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(research).toBeHidden()
  await expect(page.getByRole('button', { name: '打开研究面板' })).toBeFocused()
  await expectChatFitsViewport(page)
})

test('平板研究抽屉保留页签，服务不可用时保留会话阅读', async ({ page }) => {
  await page.setViewportSize({ width: 768, height: 1024 })
  await mockWorkspace(page, false)
  await page.goto('/workspace')
  await expect(page.getByText('Agent 聊天暂不可用')).toBeVisible()
  await expect(page.getByLabel('聊天输入')).toBeDisabled()
  await page.getByRole('button', { name: /^浦发银行趋势研究/ }).click()
  await expect(
    page.getByText('先核对趋势与成交量，再验证策略。尚未执行回测。'),
  ).toBeVisible()
  await page.getByRole('button', { name: '打开研究面板' }).click()
  await page.getByRole('tab', { name: '回测', exact: true }).click()
  await expect(page.getByText('尚无回测结果')).toBeVisible()
  await page.getByRole('button', { name: '关闭研究面板' }).click()
  await page.getByRole('button', { name: '打开研究面板' }).click()
  await expect(page.getByRole('tab', { name: '回测', exact: true })).toHaveAttribute(
    'aria-selected',
    'true',
  )
})

test('AI 标题完成后最近会话与当前标题自动同步，刷新后保留', async ({ page }) => {
  await mockWorkspace(page)
  let named = false
  const thread = () => ({
    thread_id: 'research-bank',
    title: named ? '银行股估值与风险比较' : null,
    title_pending: !named,
    status: 'idle',
    last_run_id: null,
    archived: false,
    created_at: '2026-11-05T09:00:00+08:00',
    updated_at: '2026-11-05T09:42:00+08:00',
  })
  await page.route('**/api/v1/agent-chats**', async (route) => {
    const path = new URL(route.request().url()).pathname
    if (path.endsWith('/agent-chats')) {
      return route.fulfill({ json: { threads: [thread()], total: 1 } })
    }
    if (path.endsWith('/agent-chats/research-bank')) {
      return route.fulfill({ json: { thread: thread(), turns: [], has_more: false } })
    }
    return route.fallback()
  })
  await page.goto('/workspace?thread_id=research-bank')
  await expect(page.locator('.chat-sidebar-title')).toHaveText('正在生成标题…')
  named = true
  await expect(page.locator('.chat-sidebar-title')).toHaveText('银行股估值与风险比较')
  await expect(page.locator('.chat-conversation-heading h2')).toHaveText(
    '银行股估值与风险比较',
  )
  await page.reload()
  await expect(page.locator('.chat-sidebar-title')).toHaveText('银行股估值与风险比较')
  await expect(page.locator('.chat-conversation-heading h2')).toHaveText(
    '银行股估值与风险比较',
  )
})
