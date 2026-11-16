import { expect, test, type Locator, type Page } from '@playwright/test'

async function mockApi(page: Page) {
  await page.route('**/api/v1/**', async (route) => {
    const path = new URL(route.request().url()).pathname
    let body: unknown = {}
    if (path.endsWith('/auth/me')) body = { authenticated: true }
    else if (path.endsWith('/agent-chats/status'))
      body = { backend: 'native', available: true, reason: null }
    else if (path.endsWith('/agent-chats')) body = { threads: [], total: 0 }
    else if (path.endsWith('/agent/history')) body = []
    else if (path.endsWith('/paper/alerts')) body = { alerts: [] }
    else if (path.endsWith('/jobs/metrics'))
      body = { started_at: '2026-11-05T00:00:00Z', counters: [], durations: [] }
    await route.fulfill({ json: body })
  })
}

async function box(locator: Locator) {
  const bounds = await locator.boundingBox()
  expect(bounds).not.toBeNull()
  return bounds!
}

async function expectHighlightAt(nav: Locator, label: string) {
  const link = nav.getByRole('link', { name: label, exact: true })
  await expect
    .poll(async () => {
      const mark = await box(nav.locator('.shell-nav-highlight'))
      const row = await box(link)
      const content = await box(link.locator('.shell-nav-content'))
      return Math.max(
        Math.abs(mark.x - row.x),
        Math.abs(mark.y - row.y),
        Math.abs(mark.height - row.height),
        Math.abs(mark.width - (content.width + 16)),
      )
    })
    .toBeLessThan(1)
}

test.beforeEach(async ({ page }) => {
  await mockApi(page)
  await page.goto('/workspace')
})

test('共享高亮滑动并改变宽度，悬停前后文字位置与字重保持稳定', async ({ page }) => {
  const nav = page.locator('.shell-sidebar nav')
  const shortLink = nav.getByRole('link', { name: '自选股', exact: true })
  const label = shortLink.locator('.shell-nav-content > span:last-child')
  await expectHighlightAt(nav, 'Agent 工作台')
  const wide = await box(nav.locator('.shell-nav-highlight'))
  const before = await box(label)
  const beforeWeight = await label.evaluate((node) => getComputedStyle(node).fontWeight)
  await shortLink.hover()
  const during = await box(label)
  expect(during).toEqual(before)
  await expectHighlightAt(nav, '自选股')
  const narrow = await box(nav.locator('.shell-nav-highlight'))
  expect(narrow.width).toBeLessThan(wide.width - 20)
  expect(await box(label)).toEqual(before)
  expect(await label.evaluate((node) => getComputedStyle(node).fontWeight)).toBe(
    beforeWeight,
  )
  await page.mouse.move(500, 100)
  await expectHighlightAt(nav, 'Agent 工作台')
  await page.screenshot({
    path: '../.taste-skill/navigation/desktop-active.png',
    fullPage: true,
  })
})

test('键盘聚焦跟随目标，路由切换和浏览器返回后跟随当前页面', async ({ page }) => {
  const nav = page.locator('.shell-sidebar nav')
  const report = nav.getByRole('link', { name: '分析报告', exact: true })
  await report.focus()
  await expectHighlightAt(nav, '分析报告')
  await page.keyboard.press('Tab')
  await expect(
    nav.getByRole('link', { name: 'Agent 工作台', exact: true }),
  ).toBeFocused()
  await expectHighlightAt(nav, 'Agent 工作台')
  await report.click()
  await expect(page).toHaveURL(/\/agent$/)
  await expectHighlightAt(nav, '分析报告')
  await expect(report).toHaveAttribute('aria-current', 'page')
  await page.goBack()
  await expect(page).toHaveURL(/\/workspace$/)
  await expectHighlightAt(nav, 'Agent 工作台')
})

test('手机菜单首次打开和切换路由后重新定位，桌面恢复后仍对齐', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.getByRole('button', { name: '打开菜单', exact: true }).click()
  const sheet = page.getByRole('dialog', { name: '导航菜单', exact: true })
  const nav = sheet.getByRole('navigation', { name: '主导航', exact: true })
  await expectHighlightAt(nav, 'Agent 工作台')
  await page.screenshot({
    path: '../.taste-skill/navigation/mobile-menu.png',
    fullPage: true,
  })
  await nav.getByRole('link', { name: '分析报告', exact: true }).click()
  await expect(sheet).toBeHidden()
  await page.getByRole('button', { name: '打开菜单', exact: true }).click()
  await expectHighlightAt(nav, '分析报告')
  await page.getByRole('button', { name: '关闭菜单', exact: true }).click()
  await page.setViewportSize({ width: 1440, height: 900 })
  await expectHighlightAt(page.locator('.shell-sidebar nav'), '分析报告')
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
  ).toBe(true)
})

test('减少动态效果模式直接定位高亮，快速经过不同项目后不残留动画', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  const nav = page.locator('.shell-sidebar nav')
  await nav.getByRole('link', { name: '自选股', exact: true }).hover()
  await expectHighlightAt(nav, '自选股')
  expect(
    await nav
      .locator('.shell-nav-highlight')
      .evaluate((node) => node.getAnimations().length),
  ).toBe(0)
  await page.emulateMedia({ reducedMotion: 'no-preference' })
  await nav.getByRole('link', { name: '策略研究', exact: true }).hover()
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await expectHighlightAt(nav, '策略研究')
  expect(
    await nav
      .locator('.shell-nav-highlight')
      .evaluate((node) => node.getAnimations().length),
  ).toBe(0)
  await page.emulateMedia({ reducedMotion: 'no-preference' })
  for (const name of ['仪表盘', '策略研究', '自选股', 'Agent 工作台']) {
    await nav.getByRole('link', { name, exact: true }).hover()
  }
  await expectHighlightAt(nav, 'Agent 工作台')
  await expect
    .poll(() =>
      nav
        .locator('.shell-nav-highlight')
        .evaluate((node) => node.getAnimations().length),
    )
    .toBe(0)
})
