import { expect, test } from '@playwright/test'
import { mockResearchEntry } from './fixtures/researchEntry'

for (const width of [1440, 375]) {
  test(`unsent copilot input survives close, reload and workspace handoff at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 900 })
    const state = await mockResearchEntry(page)
    await page.goto('/strategies?stock=sh.600000')
    const openCopilot = async () => {
      if (width < 768) {
        await page.getByRole('button', { name: '打开菜单' }).click()
        await page.locator('#mobile-nav .shell-copilot-btn').click()
      } else await page.locator('.shell-sidebar .shell-copilot-btn').click()
    }
    await openCopilot()
    const drawer = page.locator('.research-copilot-drawer')
    await drawer.getByLabel('聊天输入').fill('先核验原始数据，再比较成本假设')
    await drawer.getByRole('button', { name: '关闭副驾驶' }).click()
    await openCopilot()
    await expect(drawer.getByLabel('聊天输入')).toHaveValue(
      '先核验原始数据，再比较成本假设',
    )
    await page.reload()
    await openCopilot()
    await expect(drawer.getByLabel('聊天输入')).toHaveValue(
      '先核验原始数据，再比较成本假设',
    )
    await drawer.getByRole('button', { name: '打开完整工作台' }).click()
    await expect(page.getByLabel('聊天输入')).toHaveValue(
      '先核验原始数据，再比较成本假设',
    )
    expect(page.url()).not.toContain('先核验')
    expect(state.writes).toEqual([])
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    ).toBe(true)
  })
}

test('conversation drafts stay separate through switching, reload and copilot handoff', async ({
  page,
}) => {
  const state = await mockResearchEntry(page)
  await page.goto('/workspace?thread_id=bank')
  await expect(page.getByText('银行研究已保存，请继续核验证据。')).toBeVisible()
  await page.getByLabel('聊天输入').fill('银行问题未发送')
  await page.getByRole('button', { name: /^地产研究会话/ }).click()
  await expect(page.getByText('地产研究已保存，请关注风险。')).toBeVisible()
  await expect(page.getByLabel('聊天输入')).toHaveValue('')
  await page.getByLabel('聊天输入').fill('地产问题未发送')
  await page.getByRole('button', { name: /^银行研究会话/ }).click()
  await expect(page.getByLabel('聊天输入')).toHaveValue('银行问题未发送')
  await page.reload()
  await expect(page.getByLabel('聊天输入')).toHaveValue('银行问题未发送')
  await page.goto('/strategies?thread_id=bank&stock=sh.600000')
  await page.locator('.shell-sidebar .shell-copilot-btn').click()
  await expect(
    page.locator('.research-copilot-drawer').getByLabel('聊天输入'),
  ).toHaveValue('银行问题未发送')
  expect(state.writes).toEqual([])
})

test('stock drafts and deliberate clearing override URL presets without leaking to another stock', async ({
  page,
}) => {
  await mockResearchEntry(page)
  await page.goto('/workspace?stock=sh.600000&prompt=先核验银行数据')
  await expect(page.getByLabel('聊天输入')).toHaveValue('先核验银行数据')
  await page.getByLabel('聊天输入').fill('自己的银行草稿')
  await page.goto('/workspace?stock=sz.000002')
  await expect(page.getByLabel('聊天输入')).toHaveValue('分析一下 sz.000002')
  await page.goto('/workspace?stock=sh.600000&prompt=不能覆盖')
  await expect(page.getByLabel('聊天输入')).toHaveValue('自己的银行草稿')
  await page.getByLabel('聊天输入').fill('')
  await page.reload()
  await expect(page.getByLabel('聊天输入')).toHaveValue('')
})

test('first submission rejection keeps the draft under the created thread for reload and retry', async ({
  page,
}) => {
  await mockResearchEntry(page)
  let fail = true
  const contents: unknown[] = []
  await page.route('**/api/v1/agent-chats/bank/turns', async (route) => {
    contents.push(route.request().postDataJSON()?.content)
    if (fail)
      return route.fulfill({
        status: 503,
        json: { error: { code: 'unavailable', message: '暂时未接收，请重试' } },
      })
    return route.fallback()
  })
  await page.goto('/workspace?stock=sh.600000')
  await page.getByLabel('聊天输入').fill('核对交易成本原始依据')
  await page.getByRole('button', { name: '发送消息' }).click()
  await expect(page.getByText('暂时未接收，请重试', { exact: true })).toBeVisible()
  await expect(page.getByLabel('聊天输入')).toHaveValue('核对交易成本原始依据')
  await expect(page).toHaveURL(/thread_id=bank/)
  await page.reload()
  await expect(page.getByLabel('聊天输入')).toHaveValue('核对交易成本原始依据')
  fail = false
  await page.getByRole('button', { name: '发送消息' }).click()
  await expect(page.getByLabel('聊天输入')).toHaveValue('')
  await page.reload()
  await expect(page.getByLabel('聊天输入')).toHaveValue('')
  expect(contents).toEqual(['核对交易成本原始依据', '核对交易成本原始依据'])
})

test('a pending first submission stays protected when the copilot closes and reopens', async ({
  page,
}) => {
  await mockResearchEntry(page)
  let release!: () => void
  const wait = new Promise<void>((resolve) => {
    release = resolve
  })
  let posts = 0
  await page.route('**/api/v1/agent-chats/bank/turns', async (route) => {
    posts++
    await wait
    await route.fulfill({
      status: 503,
      json: { error: { code: 'unavailable', message: '本次未接收' } },
    })
  })
  await page.goto('/strategies?stock=sh.600000')
  await page.locator('.shell-sidebar .shell-copilot-btn').click()
  const drawer = page.locator('.research-copilot-drawer')
  await drawer.getByLabel('聊天输入').fill('等待确认的原文')
  await drawer.getByRole('button', { name: '发送消息' }).click()
  await expect.poll(() => posts).toBe(1)
  await drawer.getByRole('button', { name: '关闭副驾驶' }).click()
  await page.locator('.shell-sidebar .shell-copilot-btn').click()
  await expect(drawer.getByLabel('聊天输入')).toHaveValue('等待确认的原文')
  await expect(drawer.getByRole('button', { name: '发送消息' })).toBeDisabled()
  release()
  await expect(drawer.getByRole('button', { name: '发送消息' })).toBeEnabled()
  expect(posts).toBe(1)
})

for (const host of ['workspace', 'strategies']) {
  test(`restored draft stays editable but cannot submit until ${host} thread loading succeeds`, async ({
    page,
  }) => {
    const state = await mockResearchEntry(page)
    await page.goto('/workspace?thread_id=bank')
    await expect(page.getByText('银行研究已保存，请继续核验证据。')).toBeVisible()
    await page.getByLabel('聊天输入').fill('只发送给银行会话的问题')
    let release!: () => void
    const pending = new Promise<void>((resolve) => {
      release = resolve
    })
    let fail = true
    await page.route('**/api/v1/agent-chats/bank?*', async (route) => {
      await pending
      if (fail)
        return route.fulfill({
          status: 503,
          json: { error: { code: 'unavailable', message: '会话读取暂时失败' } },
        })
      return route.fallback()
    })
    await page.goto(`/${host}?thread_id=bank&stock=sh.600000`)
    if (host === 'strategies')
      await page.locator('.shell-sidebar .shell-copilot-btn').click()
    const input = page.getByLabel('聊天输入')
    await expect(input).toHaveValue('只发送给银行会话的问题')
    await expect(input).toBeEditable()
    await input.fill('加载中仍能修改银行问题')
    const send = page.getByRole('button', { name: '发送消息' })
    await expect(send).toBeDisabled()
    await input.press('Enter')
    expect(state.writes).toEqual([])
    release()
    await expect(page.getByText('会话读取暂时失败', { exact: true })).toBeVisible()
    await expect(send).toBeDisabled()
    await expect(input).toHaveValue('加载中仍能修改银行问题')
    fail = false
    if (host === 'strategies') {
      await page.getByRole('button', { name: '关闭副驾驶' }).click()
      await page.locator('.shell-sidebar .shell-copilot-btn').click()
    } else await page.getByRole('button', { name: /^银行研究会话/ }).click()
    await expect(page.getByText('银行研究已保存，请继续核验证据。')).toBeVisible()
    await page.getByRole('button', { name: '发送消息' }).click()
    await expect(page.getByLabel('聊天输入')).toHaveValue('')
    expect(state.writes).toEqual(['/api/v1/agent-chats/bank/turns'])
  })
}

test('acceptance of an older thread does not clear the other thread draft', async ({
  page,
}) => {
  await mockResearchEntry(page)
  let release!: () => void
  const wait = new Promise<void>((resolve) => {
    release = resolve
  })
  let posts = 0
  await page.route('**/api/v1/agent-chats/bank/turns', async (route) => {
    posts++
    await wait
    return route.fallback()
  })
  await page.goto('/workspace?thread_id=property')
  await expect(page.getByText('地产研究已保存，请关注风险。')).toBeVisible()
  await page.getByLabel('聊天输入').fill('另一会话的后续问题')
  await page.getByRole('button', { name: /^银行研究会话/ }).click()
  await expect(page.getByText('银行研究已保存，请继续核验证据。')).toBeVisible()
  await page.getByLabel('聊天输入').fill('提交银行问题')
  await page.getByRole('button', { name: '发送消息' }).click()
  await expect.poll(() => posts).toBe(1)
  await page.getByRole('button', { name: /^地产研究会话/ }).click()
  await expect(page.getByText('地产研究已保存，请关注风险。')).toBeVisible()
  await page.getByLabel('聊天输入').fill('等待其他提交时仍可修改的问题')
  release()
  await expect(page.getByLabel('聊天输入')).toHaveValue('等待其他提交时仍可修改的问题')
  await page.getByRole('button', { name: /^银行研究会话/ }).click()
  await expect(page.getByLabel('聊天输入')).toHaveValue('')
})
