import { expect, test, type Page } from '@playwright/test'
import { mockResearchApi } from './fixtures/research'
import { FONT_SIZE } from '../src/styles/typography'

const routes = [
  '/',
  '/stocks',
  '/stocks/sz.000002',
  '/watchlist',
  '/screener',
  '/strategies?stock=sz.000002',
  '/portfolio',
  '/history',
  '/dl-prediction',
  '/agent',
  '/workspace',
]

const allowedSizes = new Set(Object.values(FONT_SIZE))

type TextSample = {
  route: string
  viewport: string
  tag: string
  className: string
  text: string
  size: number
  family: string
}

async function mockSite(page: Page) {
  await mockResearchApi(page)
  await page.route('**/api/v1/agent-chats**', (route) => {
    const path = new URL(route.request().url()).pathname
    const json = path.endsWith('/status')
      ? { backend: 'native', available: true, reason: null }
      : { threads: [], total: 0 }
    return route.fulfill({ json })
  })
}

async function loadedFontPair(page: Page) {
  return page.evaluate(async () => {
    const load = async (family: string, text: string) => {
      const faces = await document.fonts.load(`14px "${family}"`, text)
      return faces.length > 0 && faces.every((face) => face.status === 'loaded')
    }
    return {
      latin: await load('Inter Variable', '0123 ABC'),
      chinese: await load('Noto Sans SC Variable', '股票成交量'),
    }
  })
}

async function visibleText(
  page: Page,
): Promise<Omit<TextSample, 'route' | 'viewport'>[]> {
  return page.evaluate(() => {
    const samples: Omit<TextSample, 'route' | 'viewport'>[] = []
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT)
    let node = walker.nextNode()
    while (node) {
      const text = node.textContent?.trim() ?? ''
      const parent = node.parentElement
      if (
        text &&
        parent &&
        !parent.closest(
          '.anticon, [aria-hidden="true"], script, style, noscript, .ant-empty-img, .sr-only',
        )
      ) {
        const style = getComputedStyle(parent)
        if (
          style.display !== 'none' &&
          style.visibility !== 'hidden' &&
          parent.getClientRects().length > 0
        ) {
          samples.push({
            tag: parent.tagName.toLowerCase(),
            className: parent.className?.toString().slice(0, 90) ?? '',
            text: text.slice(0, 40),
            size: Number.parseFloat(style.fontSize),
            family: style.fontFamily,
          })
        }
      }
      node = walker.nextNode()
    }
    return samples
  })
}

test('Ant Design portals inherit the shared font pair', async ({ page }) => {
  await mockSite(page)
  await page.goto('/stocks')
  await page.getByRole('button', { name: /同步K线数据/ }).click()
  await expect(page.getByRole('dialog')).toBeVisible()
  const modal = await page.locator('.ant-modal-content').evaluate((node) => {
    const style = getComputedStyle(node)
    return { family: style.fontFamily, size: Number.parseFloat(style.fontSize) }
  })
  expect(modal.family).toContain('Inter Variable')
  expect(modal.family).toContain('Noto Sans SC Variable')
  expect(modal.size).toBe(14)
  await page.keyboard.press('Escape')

  await page.goto('/dl-prediction')
  await page.locator('.dl-field:has(#dl-model) .ant-select-selector').click()
  const option = page.locator('.ant-select-item-option').first()
  await expect(option).toBeVisible()
  const popup = await option.evaluate((node) => {
    const style = getComputedStyle(node)
    return { family: style.fontFamily, size: Number.parseFloat(style.fontSize) }
  })
  expect(popup.family).toContain('Inter Variable')
  expect(popup.family).toContain('Noto Sans SC Variable')
  expect(popup.size).toBe(14)
})

test('login page uses the same four sizes and fonts', async ({ page }) => {
  await mockSite(page)
  await page.route('**/api/v1/auth/me', (route) =>
    route.fulfill({ json: { authenticated: false } }),
  )
  await page.goto('/login')
  await expect(page.locator('.login-shell')).toBeVisible()
  await page.evaluate(() => document.fonts.ready)
  const samples = await visibleText(page)
  const summary = [
    ...new Set(
      samples
        .filter((sample) => !allowedSizes.has(sample.size))
        .map(
          (sample) =>
            `${sample.size}px ${sample.tag}.${sample.className} "${sample.text}"`,
        ),
    ),
  ]
  expect(summary).toEqual([])
  expect(samples.every((sample) => sample.family.includes('Inter Variable'))).toBe(true)
  expect(await loadedFontPair(page)).toEqual({ latin: true, chinese: true })
})

test('charts and delayed CJK subsets use the shared font', async ({ page }) => {
  await mockSite(page)
  await page.goto('/stocks/sz.000002')
  await expect(page.locator('main h1').first()).toBeVisible()
  await expect(page.locator('[data-chart-font]').first()).toBeVisible()
  const fonts = await loadedFontPair(page)
  const chart = await page
    .locator('[data-chart-font]')
    .first()
    .getAttribute('data-chart-font')
  expect(fonts).toEqual({ latin: true, chinese: true })
  expect(chart).toEqual(expect.stringContaining('Inter Variable'))
})

test('application screens use four text sizes and the shared font pair', async ({
  page,
}) => {
  test.setTimeout(180_000)
  await mockSite(page)
  const violations: TextSample[] = []
  const familyViolations: TextSample[] = []
  const fonts = new Set<string>()

  for (const viewport of [
    { width: 1440, height: 900 },
    { width: 390, height: 844 },
  ]) {
    await page.setViewportSize(viewport)
    for (const route of routes) {
      await page.goto(route)
      await expect(page.locator('main h1').first()).toBeVisible()
      await page.evaluate(() => document.fonts.ready)
      const samples = await visibleText(page)
      for (const sample of samples) {
        fonts.add(sample.family)
        if (
          !sample.family.includes('Inter Variable') ||
          !sample.family.includes('Noto Sans SC Variable')
        ) {
          familyViolations.push({
            route,
            viewport: `${viewport.width}px`,
            ...sample,
          })
        }
        if (!allowedSizes.has(sample.size)) {
          violations.push({
            route,
            viewport: `${viewport.width}px`,
            ...sample,
          })
        }
      }
    }
  }

  const summary = [
    ...new Set(
      violations.map(
        (item) =>
          `${item.route} ${item.viewport} ${item.size}px ${item.tag}.${item.className} "${item.text}"`,
      ),
    ),
  ]
  if (summary.length) {
    console.log(JSON.stringify(summary, null, 2))
  }
  expect(summary).toEqual([])
  expect([
    ...new Set(
      familyViolations.map((item) => `${item.route} ${item.viewport} ${item.family}`),
    ),
  ]).toEqual([])
  expect(await loadedFontPair(page)).toEqual({ latin: true, chinese: true })
  expect([...fonts].filter((family) => family.includes('Inter Variable'))).not.toEqual(
    [],
  )
  expect(
    await page.evaluate(() => {
      const style = getComputedStyle(document.body)
      return {
        family: style.fontFamily,
        size: Number.parseFloat(style.fontSize),
      }
    }),
  ).toEqual({
    family: expect.stringContaining('Inter Variable'),
    size: 14,
  })
})
