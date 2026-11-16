import { expect, test } from '@playwright/test'
import { mockResearchEntry } from './fixtures/researchEntry'

test('copilot hands off the active stock and saved conversation without another submission', async ({
  page,
}) => {
  const state = await mockResearchEntry(page)
  await page.goto('/strategies?stock=sh.600000&unrelated=discard')
  await page.locator('.shell-sidebar .shell-copilot-btn').click()
  const copilot = page.locator('.research-copilot-drawer')
  await copilot.getByLabel('聊天输入').fill('核验当前研究证据')
  await copilot.getByRole('button', { name: '发送消息' }).click()
  await expect(copilot.getByText('银行研究已保存，请继续核验证据。')).toBeVisible()
  expect(state.contexts).toEqual([
    { route: '/strategies', entity_type: 'stock', entity_id: 'sh.600000' },
  ])
  const writes = state.writes.length
  await copilot.getByRole('button', { name: '打开完整工作台' }).click()
  await expect(page).toHaveURL(/\/workspace\?thread_id=bank&stock=sh.600000$/)
  await expect(page.locator('.chat-conversation-heading')).toContainText('sh.600000')
  await expect(page.getByText('银行研究已保存，请继续核验证据。')).toBeVisible()
  await page.reload()
  await expect(page.getByText('银行研究已保存，请继续核验证据。')).toBeVisible()
  expect(state.writes).toHaveLength(writes)
})

test('copilot without a conversation hands off only the stock and does not start research', async ({
  page,
}) => {
  const state = await mockResearchEntry(page)
  await page.goto('/strategies?stock=sz.000002')
  await page.locator('.shell-sidebar .shell-copilot-btn').click()
  await page.getByRole('button', { name: '打开完整工作台' }).click()
  await expect(page).toHaveURL(/\/workspace\?stock=sz.000002$/)
  await expect(page.getByLabel('聊天输入')).toHaveValue('分析一下 sz.000002')
  expect(state.writes).toEqual([])
})

test('workspace panels keep conversation parameters and follow browser history', async ({
  page,
}) => {
  await mockResearchEntry(page)
  await page.goto('/workspace?thread_id=bank&stock=sh.600000&keep=1')
  await expect(page.getByText('银行研究已保存，请继续核验证据。')).toBeVisible()
  await page.getByRole('tab', { name: '证据', exact: true }).click()
  await expect(page).toHaveURL(/panel=evidence/)
  expect(new URL(page.url()).searchParams.get('thread_id')).toBe('bank')
  expect(new URL(page.url()).searchParams.get('keep')).toBe('1')
  await page.getByRole('tab', { name: '告警', exact: true }).click()
  await page.goBack()
  await expect(page.getByRole('tab', { name: '证据', exact: true })).toHaveAttribute(
    'aria-selected',
    'true',
  )
  await page.reload()
  await expect(page.getByRole('tab', { name: '证据', exact: true })).toHaveAttribute(
    'aria-selected',
    'true',
  )
  await page.getByRole('button', { name: /^地产研究会话/ }).click()
  await expect(page.getByText('地产研究已保存，请关注风险。')).toBeVisible()
  expect(new URL(page.url()).searchParams.get('panel')).toBe('evidence')
  expect(new URL(page.url()).searchParams.get('thread_id')).toBe('property')
})

test('same-route thread navigation restores the requested conversation and can return to an empty session', async ({
  page,
}) => {
  await mockResearchEntry(page)
  await page.goto('/workspace?thread_id=bank')
  await expect(page.getByText('银行研究已保存，请继续核验证据。')).toBeVisible()
  await page.evaluate(() => {
    history.pushState(history.state, '', '/workspace?thread_id=property&panel=evidence')
    dispatchEvent(new PopStateEvent('popstate'))
  })
  await expect(page.getByText('地产研究已保存，请关注风险。')).toBeVisible()
  await page.goBack()
  await expect(page.getByText('银行研究已保存，请继续核验证据。')).toBeVisible()
  await page.evaluate(() => {
    history.pushState(history.state, '', '/workspace')
    dispatchEvent(new PopStateEvent('popstate'))
  })
  await expect(page.locator('.chat-conversation-heading h2')).toHaveText('新研究会话')
  await expect(page.getByText('银行研究已保存，请继续核验证据。')).toBeHidden()
})

test('dashboard alert opens its record even when the desktop research panel was collapsed', async ({
  page,
}) => {
  const state = await mockResearchEntry(page)
  await page.addInitScript(() =>
    localStorage.setItem('agent-workspace.research-collapsed', 'true'),
  )
  await page.goto('/')
  await page.locator('.dash-alert').filter({ hasText: '万科A风险记录需要复核' }).click()
  await expect(page).toHaveURL(/panel=alerts&alert=2/)
  await expect(page.getByRole('tab', { name: '告警', exact: true })).toHaveAttribute(
    'aria-selected',
    'true',
  )
  await expect(page.getByText('当前告警', { exact: true })).toBeVisible()
  await expect(page.locator('[data-alert-id="2"]')).toBeInViewport()
  await page.getByRole('button', { name: '收起研究区' }).click()
  await expect(page.getByRole('button', { name: '展开研究区' })).toBeVisible()
  expect(state.writes).toEqual([])
})

test('mobile unread alert link opens a closable panel, refresh restores it and invalid targets recover', async ({
  page,
}) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await mockResearchEntry(page)
  await page.goto('/workspace')
  await page.getByRole('button', { name: '打开菜单' }).click()
  await page
    .locator('#mobile-nav .shell-status-row')
    .filter({ hasText: '告警' })
    .click()
  await expect(page.getByRole('tab', { name: '告警', exact: true })).toBeVisible()
  await page.getByRole('button', { name: '关闭研究面板' }).click()
  await expect(page.getByRole('tab', { name: '告警', exact: true })).toBeHidden()
  await page.reload()
  await expect(page.getByRole('tab', { name: '告警', exact: true })).toBeVisible()
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
  ).toBe(true)
  await page.goto('/workspace?panel=alerts&alert=999')
  await expect(page.getByText('未找到指定告警', { exact: true })).toBeVisible()
  await page.goto('/workspace?panel=invalid&alert=-1')
  await page.getByRole('button', { name: '打开研究面板' }).click()
  await expect(page.getByRole('tab', { name: '行情与结论' })).toHaveAttribute(
    'aria-selected',
    'true',
  )
})

for (const viewport of [
  { width: 1440, height: 900 },
  { width: 375, height: 812 },
]) {
  test(`a delayed conversation restore respects a dismissed panel at ${viewport.width}px`, async ({
    page,
  }) => {
    await page.setViewportSize(viewport)
    await mockResearchEntry(page)
    let release!: () => void
    const delayed = new Promise<void>((resolve) => {
      release = resolve
    })
    await page.route('**/api/v1/agent-chats/bank**', async (route) => {
      if (new URL(route.request().url()).pathname.endsWith('/bank')) await delayed
      return route.fallback()
    })
    await page.goto('/workspace?thread_id=bank&panel=alerts')
    const mobile = viewport.width < 1280
    await page
      .getByRole('button', { name: mobile ? '关闭研究面板' : '收起研究区' })
      .click()
    const tab = page.getByRole('tab', { name: '告警', exact: true })
    await expect(tab).toBeHidden()
    release()
    await expect(page.getByText('银行研究已保存，请继续核验证据。')).toBeVisible()
    await expect(tab).toBeHidden()
    if (mobile) await page.getByRole('button', { name: '打开菜单' }).click()
    await page
      .locator(
        mobile ? '#mobile-nav .shell-status-row' : '.shell-sidebar .shell-status-row',
      )
      .filter({ hasText: '告警' })
      .click()
    await expect(tab).toBeVisible()
  })
}

test('workspace URL updates preserve caller navigation state', async ({ page }) => {
  await mockResearchEntry(page)
  await page.goto('/workspace')
  await page.evaluate(() => {
    history.pushState(
      { ...history.state, usr: { returnTo: '/strategies?stock=sh.600000' } },
      '',
      '/workspace?thread_id=bank&panel=alerts',
    )
    dispatchEvent(new PopStateEvent('popstate'))
  })
  await expect(page.getByText('银行研究已保存，请继续核验证据。')).toBeVisible()
  expect(await page.evaluate(() => history.state.usr)).toEqual({
    returnTo: '/strategies?stock=sh.600000',
  })
  await page.getByRole('tab', { name: '证据', exact: true }).click()
  expect(await page.evaluate(() => history.state.usr)).toEqual({
    returnTo: '/strategies?stock=sh.600000',
  })
})

test('alert fetch errors stay explicit, can retry, and preserve records during failed refresh', async ({
  page,
}) => {
  const state = await mockResearchEntry(page)
  state.failList = true
  await page.goto('/workspace?panel=alerts')
  await expect(page.getByText('告警加载失败', { exact: true })).toBeVisible()
  await expect(page.getByText('暂无告警', { exact: true })).toBeHidden()
  state.failList = false
  await page.getByRole('button', { name: /重\s*试/ }).click()
  await expect(page.locator('[data-alert-id="1"]')).toContainText(
    '浦发银行数据覆盖需要核验',
  )
  state.failList = true
  await page.getByRole('button', { name: '刷新告警' }).click()
  await expect(page.getByText('告警刷新失败', { exact: true })).toBeVisible()
  await expect(page.locator('[data-alert-id="1"]')).toBeVisible()
})

test('failed mark-read keeps the record unread and successful retry updates the shell count', async ({
  page,
}) => {
  const state = await mockResearchEntry(page)
  state.failRead = true
  await page.goto('/workspace?panel=alerts&alert=2')
  const selected = page.locator('[data-alert-id="2"]')
  await selected.getByRole('button', { name: '标记已读' }).click()
  await expect(page.getByText('标记已读失败', { exact: true })).toBeVisible()
  await expect(selected.getByRole('button', { name: '标记已读' })).toBeEnabled()
  await expect(
    page.locator('.shell-sidebar .shell-status-row').filter({ hasText: '告警' }),
  ).toContainText('2')
  state.failRead = false
  await selected.getByRole('button', { name: '标记已读' }).click()
  await expect(selected.getByText('已读', { exact: true })).toBeVisible()
  await expect(
    page.locator('.shell-sidebar .shell-status-row').filter({ hasText: '告警' }),
  ).toContainText('1')
})
