import { expect, test } from '@playwright/test'

test.describe('landing page', () => {
  test.beforeEach(async ({ page }) => {
    await page.route('**/api/v1/auth/me', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ authenticated: false }),
      }),
    )
  })

  test('renders the full landing page without JS', async ({ browser }) => {
    const context = await browser.newContext({ javaScriptEnabled: false })
    const page = await context.newPage()
    await page.goto('/welcome/')
    await expect(page.getByRole('heading', { level: 1 })).toContainText(
      '从 K 线到模拟成交',
    )
    await expect(
      page.getByRole('link', { name: '登录研究工作台' }).first(),
    ).toHaveAttribute('href', '/login')
    await expect(page.locator('.faq-item')).toHaveCount(9)
    await expect(page.getByRole('link', { name: '隐私' })).toHaveAttribute(
      'href',
      '/legal/privacy.html',
    )
    await expect(page.getByRole('link', { name: '条款' })).toHaveAttribute(
      'href',
      '/legal/terms.html',
    )
    await context.close()
  })

  test('propagates next into login links', async ({ page }) => {
    await page.goto('/welcome/?next=%2Fstocks%2F600519')
    await expect(
      page.getByRole('link', { name: '登录研究工作台' }).first(),
    ).toHaveAttribute('href', '/login?next=%2Fstocks%2F600519')
  })

  test('opens and closes the mobile menu with Escape', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 })
    await page.goto('/welcome/')
    const toggle = page.getByRole('button', { name: '打开菜单' })
    await toggle.click()
    const menu = page.locator('#mobile-menu')
    await expect(menu).toBeVisible()
    await expect(page.getByRole('button', { name: '关闭菜单' })).toBeFocused()
    await page.keyboard.press('Escape')
    await expect(menu).toBeHidden()
    await expect(toggle).toBeFocused()
  })

  test('has no horizontal scroll at 375, 768 and 1440', async ({ page }) => {
    for (const width of [375, 768, 1440]) {
      await page.setViewportSize({ width, height: 900 })
      await page.goto('/welcome/')
      const overflow = await page.evaluate(
        () =>
          document.documentElement.scrollWidth > document.documentElement.clientWidth,
      )
      expect(overflow).toBe(false)
    }
  })

  test('shows the tagline with reduced motion', async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await page.goto('/welcome/')
    const firstWord = page.locator('.tagline-word').first()
    await expect(firstWord).toBeVisible()
    const opacity = await firstWord.evaluate(
      (element) => getComputedStyle(element).opacity,
    )
    expect(opacity).toBe('1')
  })
})
