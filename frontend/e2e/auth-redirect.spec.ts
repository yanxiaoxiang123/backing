import { expect, test } from '@playwright/test'

test.describe('auth redirect and login next', () => {
  test.beforeEach(async ({ page }) => {
    await page.route('**/api/v1/auth/me', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ authenticated: false }),
      }),
    )
    await page.route('**/api/v1/stocks**', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ items: [], total: 0, nextCursor: null }),
      }),
    )
  })

  test('unauthenticated app route redirects to welcome with next', async ({ page }) => {
    await page.goto('/stocks')
    await expect(page).toHaveURL(/\/welcome\/\?next=%2Fstocks$/)
  })

  test('login returns to the next path and links back to welcome', async ({ page }) => {
    await page.route('**/api/v1/auth/session', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true }),
      }),
    )
    await page.goto('/login?next=%2Fstocks')
    await expect(page.getByRole('link', { name: '了解 Backing' })).toHaveAttribute(
      'href',
      '/welcome/',
    )
    await page.getByLabel('账号').fill('analyst')
    await page.getByLabel('登录密码').fill('test-key')
    await page.getByRole('button', { name: /进入量化系统/ }).click()
    await expect(page).toHaveURL(/\/stocks$/)
  })
})
