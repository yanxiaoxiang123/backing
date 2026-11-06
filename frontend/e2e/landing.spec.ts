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
    await expect(page.getByRole('heading', { level: 1 })).toContainText('让策略，')
    await expect(
      page.getByRole('link', { name: '进入研究工作台' }).first(),
    ).toHaveAttribute('href', '/login')
    await expect(page.locator('.faq-item')).toHaveCount(8)
    await expect(page.locator('[data-strategy]')).toHaveCount(13)
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
      page.getByRole('link', { name: '进入研究工作台' }).first(),
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

  test('highlights nearby characters with short neutral feedback', async ({ page }) => {
    await page.goto('/welcome/')
    const heading = page.locator('#strategies-title')
    await heading.scrollIntoViewIfNeeded()
    const chars = heading.locator('.hover-char')
    await expect(chars.first()).toBeVisible()
    await expect
      .poll(() =>
        heading.evaluate((node) => getComputedStyle(node.closest('header')!).transform),
      )
      .toBe('none')
    await chars.nth(3).hover()
    const styles = await chars.evaluateAll((nodes) =>
      nodes.slice(0, 5).map((node) => {
        const overlay = getComputedStyle(node, '::after')
        return {
          opacity: overlay.opacity,
          gradient: overlay.backgroundImage,
          transition: overlay.transitionProperty,
        }
      }),
    )
    await expect
      .poll(async () =>
        chars.nth(3).evaluate((node) => getComputedStyle(node, '::after').opacity),
      )
      .toBe('1')
    await expect
      .poll(async () =>
        chars
          .nth(2)
          .evaluate((node) => Number(getComputedStyle(node, '::after').opacity)),
      )
      .toBeCloseTo(0.62, 2)
    await expect
      .poll(async () =>
        chars
          .nth(4)
          .evaluate((node) => Number(getComputedStyle(node, '::after').opacity)),
      )
      .toBeCloseTo(0.62, 2)
    await expect
      .poll(async () =>
        chars
          .nth(1)
          .evaluate((node) => Number(getComputedStyle(node, '::after').opacity)),
      )
      .toBeCloseTo(0.28, 2)
    expect(
      await chars.first().evaluate((node) => getComputedStyle(node, '::after').opacity),
    ).toBe('0')
    expect(styles[3].gradient).toBe('none')
    expect(styles[3].transition).toContain('clip-path')
    await expect(heading).toHaveAccessibleName('13 个起点，留给你的假设。')
    await page.mouse.move(0, 0)
    await expect
      .poll(async () =>
        chars.nth(3).evaluate((node) => getComputedStyle(node, '::after').opacity),
      )
      .toBe('0')
  })

  test('groups the strategy index and hides unrelated categories when filtering', async ({
    page,
  }) => {
    await page.goto('/welcome/')
    await expect(page.locator('[data-strategy-group]')).toHaveCount(3)
    await page.getByRole('button', { name: '趋势 4', exact: true }).click()
    await expect(page.locator('[data-strategy-group]:visible')).toHaveCount(1)
    await expect(page.locator('[data-strategy]:visible')).toHaveCount(4)
    await page.getByRole('button', { name: '全部 13', exact: true }).click()
    await expect(page.locator('[data-strategy-group]:visible')).toHaveCount(3)
  })

  test('filters the public strategy directory by category', async ({ page }) => {
    await page.goto('/welcome/')
    await expect(page.locator('[data-strategy]:visible')).toHaveCount(13)
    await page.getByRole('button', { name: '趋势 4', exact: true }).click()
    await expect(page.locator('[data-strategy]:visible')).toHaveCount(4)
    await expect(
      page.locator('[data-strategy]:visible').filter({ hasText: 'turtle_trading' }),
    ).toHaveCount(1)
    await expect(page.locator('[data-strategy]:visible').first()).toContainText(
      '均线交叉',
    )
    await page.getByRole('button', { name: '突破 6', exact: true }).click()
    await expect(page.locator('[data-strategy]:visible')).toHaveCount(6)
    await page.getByRole('button', { name: '震荡 3', exact: true }).click()
    await expect(page.locator('[data-strategy]:visible')).toHaveCount(3)
    await page.getByRole('button', { name: '全部 13', exact: true }).click()
    await expect(page.locator('[data-strategy]:visible')).toHaveCount(13)
  })

  test('keeps reading content visible when the enhancement script fails', async ({
    page,
  }) => {
    await page.route('**/welcome/landing.js', (route) => route.abort())
    await page.goto('/welcome/')
    for (const id of ['features', 'workflow', 'strategies', 'trust', 'faq']) {
      const section = page.locator(`#${id}`)
      await section.scrollIntoViewIfNeeded()
      await expect(section.getByRole('heading', { level: 2 })).toBeVisible()
      const opacity = await section
        .getByRole('heading', { level: 2 })
        .evaluate((heading) => {
          let element: Element | null = heading
          while (element) {
            if (getComputedStyle(element).opacity === '0') return '0'
            element = element.parentElement
          }
          return '1'
        })
      expect(opacity).toBe('1')
    }
    await expect(page.locator('[data-strategy]')).toHaveCount(13)
  })

  test('does not propagate unsafe next destinations', async ({ page }) => {
    for (const next of [
      '//example.com',
      '/\\example.com',
      '/\n/example.com',
      '/\t/example.com',
      'https://example.com',
    ]) {
      await page.goto(`/welcome/?next=${encodeURIComponent(next)}`)
      await expect(
        page.getByRole('link', { name: '进入研究工作台', exact: true }).first(),
      ).toHaveAttribute('href', '/login')
    }
  })

  test('exposes the animated tagline to screen readers', async ({ page }) => {
    await page.goto('/welcome/')
    const snapshot = await page.locator('.tagline').ariaSnapshot()
    expect(snapshot).toContain('先让数据回答，')
    expect(snapshot).toContain('再给判断一点时间。')
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
