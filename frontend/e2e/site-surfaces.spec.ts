import { expect, test, type Page } from '@playwright/test'
import { mockResearchApi } from './fixtures/research'

const routes = [
  '/',
  '/stocks',
  '/stocks/sh.600000',
  '/watchlist',
  '/screener',
  '/strategies?stock=sh.600000',
  '/portfolio',
  '/dl-prediction',
  '/history',
  '/agent',
  '/workspace',
]

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

test('all app routes share three surface levels on desktop, tablet and phone', async ({
  page,
}, info) => {
  test.setTimeout(120000)
  await mockSite(page)
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  for (const route of routes) {
    for (const [width, height] of [
      [1568, 1003],
      [768, 1003],
      [390, 844],
    ]) {
      await page.setViewportSize({ width, height })
      await page.goto(route)
      await expect(page.locator('main h1').first()).toBeVisible()
      const colors = await page.evaluate(() => {
        const style = (selector: string) =>
          getComputedStyle(document.querySelector(selector)!)
        return {
          sidebar: style('.shell-sidebar').backgroundColor,
          main: style('.shell-main').backgroundColor,
          numbers: style('body').fontVariantNumeric,
          overflow: document.documentElement.scrollWidth > innerWidth,
          tail: document.querySelector('main .prose-tail')?.textContent,
        }
      })
      expect(colors.sidebar).toBe('rgb(240, 240, 240)')
      expect(colors.main).toBe('rgb(246, 246, 246)')
      expect(colors.numbers).toContain('tabular-nums')
      expect(colors.overflow, `${route} at ${width}`).toBe(false)
      await page.screenshot({
        path: info.outputPath(
          `${route.replace(/\W/g, '_') || 'dashboard'}-${width}.png`,
        ),
        fullPage: true,
      })
    }
  }
  expect(errors).toEqual([])
})

test('dropdowns, modal and mobile navigation inherit their structural surfaces', async ({
  page,
}) => {
  await mockSite(page)
  await page.goto('/stocks')
  await page.getByRole('button', { name: /同步K线数据/ }).click()
  const dialog = page.getByRole('dialog')
  await expect(dialog).toBeVisible()
  expect(
    await page.locator('.ant-modal-content').evaluate((node) => ({
      background: getComputedStyle(node).backgroundColor,
      shadow: getComputedStyle(node).boxShadow,
    })),
  ).toEqual({ background: 'rgb(252, 252, 252)', shadow: 'none' })
  await page.keyboard.press('Escape')
  await page.goto('/dl-prediction')
  await page.locator('.dl-field:has(#dl-model) .ant-select-selector').click()
  await expect(page.locator('.ant-select-dropdown:visible')).toBeVisible()
  expect(
    await page
      .locator('.ant-select-dropdown:visible')
      .evaluate((node) => getComputedStyle(node).backgroundColor),
  ).toBe('rgb(252, 252, 252)')
  await page.keyboard.press('Escape')
  await page.setViewportSize({ width: 390, height: 844 })
  await page.getByRole('button', { name: '打开菜单', exact: true }).click()
  expect(
    await page.locator('.shell-sheet.open').evaluate((node) => ({
      background: getComputedStyle(node).backgroundColor,
      overflow: node.scrollWidth > node.clientWidth,
    })),
  ).toEqual({ background: 'rgb(240, 240, 240)', overflow: false })
})

test('parameter drag commits its step and remains still after release or cancellation', async ({
  page,
}) => {
  await mockSite(page)
  await page.goto('/dl-prediction')
  await page.getByText('滑动微调天数', { exact: true }).click()
  const slider = page.getByRole('slider', { name: '滑动选择预测天数' })
  const rail = page.locator('.ant-slider-rail')
  const box = (await rail.boundingBox())!
  const drag = async () => {
    const handle = (await slider.boundingBox())!
    await page.mouse.move(handle.x + handle.width / 2, handle.y + handle.height / 2)
    await page.mouse.down()
    await page.mouse.move(box.x + box.width * 0.72, box.y + box.height / 2, {
      steps: 9,
    })
  }
  const sample = () =>
    slider.evaluate((node) => ({
      value: node.getAttribute('aria-valuenow'),
      left: node.getBoundingClientRect().left,
    }))
  await drag()
  await page.mouse.up()
  await page.evaluate(() => new Promise(requestAnimationFrame))
  const released = await sample()
  expect(Number(released.value)).toBeGreaterThan(10)
  expect(Number(released.value) % 1).toBe(0)
  await page.waitForTimeout(250)
  expect(await sample()).toEqual(released)
  await expect(page.getByLabel('预测交易日数')).toHaveValue(released.value!)
  await slider.press('Home')
  await drag()
  await page.evaluate(() => window.dispatchEvent(new Event('pointercancel')))
  const cancelled = await sample()
  await page.mouse.move(box.x + box.width * 0.1, box.y)
  await page.mouse.up()
  await page.waitForTimeout(200)
  expect(await sample()).toEqual(cancelled)
})

test('chart range redraw stops by the next frame after navigator and inside pan', async ({
  page,
}) => {
  await mockSite(page)
  await page.goto('/stocks/sh.600000')
  const chart = page.locator('.stock-chart-panel [role="img"]')
  await expect(chart.locator('canvas')).toBeVisible()
  const box = (await chart.boundingBox())!
  const range = () =>
    chart.evaluate(async (node) => {
      // Read the running chart via its own loaded module, without product debug hooks.
      const source = performance
        .getEntriesByType('resource')
        .find((resource) => /echartsCustom.*\.(js|ts)/.test(resource.name))!.name
      const { default: core } = (await import(source)) as {
        default: {
          getInstanceByDom(element: Element): {
            getOption(): { dataZoom: Array<{ start: number; end: number }> }
          }
        }
      }
      return core
        .getInstanceByDom(node)
        .getOption()
        .dataZoom.map(({ start, end }) => ({ start, end }))
    })
  const pixels = () =>
    chart
      .locator('canvas')
      .first()
      .evaluate((canvas: HTMLCanvasElement) => canvas.toDataURL())
  const initial = await pixels()
  const initialRange = await range()
  // The existing handle is centered just inside the slider's 48px inset.
  await page.mouse.move(box.x + 51, box.y + box.height - 12)
  await page.mouse.down()
  await page.mouse.move(box.x + box.width * 0.4, box.y + box.height - 12, {
    steps: 10,
  })
  await page.mouse.up()
  await page.evaluate(() => new Promise(requestAnimationFrame))
  const released = await pixels()
  const releasedRange = await range()
  expect(released === initial).toBe(false)
  expect(releasedRange).not.toEqual(initialRange)
  await page.waitForTimeout(250)
  expect((await pixels()) === released).toBe(true)
  expect(await range()).toEqual(releasedRange)
  await page.mouse.move(box.x + box.width * 0.4, box.y + 90)
  await page.mouse.down()
  await page.mouse.move(box.x + box.width * 0.6, box.y + 90, { steps: 8 })
  await page.mouse.up()
  // Remove the crosshair; subsequent comparisons cover the plot, axis and navigator.
  await page.mouse.move(0, 0)
  await page.evaluate(() => new Promise(requestAnimationFrame))
  const panned = await pixels()
  const pannedRange = await range()
  expect(panned === released).toBe(false)
  expect(pannedRange).not.toEqual(releasedRange)
  await page.waitForTimeout(250)
  expect((await pixels()) === panned).toBe(true)
  expect(await range()).toEqual(pannedRange)
  await page.mouse.move(box.x + box.width * 0.5, box.y + 90)
  await page.mouse.down()
  await page.mouse.move(box.x + box.width * 0.6, box.y + 90, { steps: 4 })
  await page.evaluate(() => window.dispatchEvent(new Event('pointercancel')))
  const cancelledRange = await range()
  await page.mouse.move(box.x + box.width * 0.3, box.y + 90, { steps: 4 })
  await page.mouse.up()
  await page.waitForTimeout(200)
  expect(await range()).toEqual(cancelledRange)
})

test.describe('touch release', () => {
  test.use({ hasTouch: true })

  test('touchend and touchcancel finish the current stepped value', async ({
    page,
    context,
  }) => {
    await mockSite(page)
    await page.goto('/dl-prediction')
    await page.getByText('滑动微调天数', { exact: true }).click()
    const slider = page.getByRole('slider', { name: '滑动选择预测天数' })
    const rail = (await page.locator('.ant-slider-rail').boundingBox())!
    const input = await context.newCDPSession(page)
    const drag = async (fraction: number) => {
      const handle = (await slider.boundingBox())!
      await input.send('Input.dispatchTouchEvent', {
        type: 'touchStart',
        touchPoints: [
          { x: handle.x + handle.width / 2, y: handle.y + handle.height / 2 },
        ],
      })
      await input.send('Input.dispatchTouchEvent', {
        type: 'touchMove',
        touchPoints: [{ x: rail.x + rail.width * fraction, y: rail.y + 2 }],
      })
    }
    for (const [fraction, type] of [
      [0.8, 'touchEnd'],
      [0.4, 'touchCancel'],
    ] as const) {
      await drag(fraction)
      await input.send('Input.dispatchTouchEvent', { type, touchPoints: [] })
      const value = await slider.getAttribute('aria-valuenow')
      await expect(page.getByLabel('预测交易日数')).toHaveValue(value!)
      await page.waitForTimeout(200)
      await expect(slider).toHaveAttribute('aria-valuenow', value!)
      expect(Number(value)).toBeGreaterThan(5)
    }
    await input.detach()
  })
})

test('login, welcome and legal pages share tokens and retain visible reduced-motion prose', async ({
  page,
}, info) => {
  await page.route('**/api/v1/auth/me', (route) =>
    route.fulfill({ json: { authenticated: false } }),
  )
  await page.emulateMedia({ reducedMotion: 'reduce' })
  for (const route of [
    '/login',
    '/welcome/',
    '/legal/privacy.html',
    '/legal/terms.html',
  ]) {
    for (const width of [1568, 768, 390]) {
      await page.setViewportSize({ width, height: 1003 })
      await page.goto(route)
      await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
      const result = await page.evaluate(() => ({
        main: getComputedStyle(document.documentElement)
          .getPropertyValue('--ui-main')
          .trim(),
        overflow: document.documentElement.scrollWidth > innerWidth,
        tails: document.querySelectorAll('.prose-tail').length,
        hidden: [...document.querySelectorAll('h1,p')].some(
          (node) => getComputedStyle(node).opacity === '0',
        ),
      }))
      expect(result).toMatchObject({ main: '#f6f6f6', overflow: false, hidden: false })
      expect(result.tails).toBeGreaterThan(0)
      await page.screenshot({
        path: info.outputPath(`${route.replace(/\W/g, '_')}-${width}.png`),
        fullPage: true,
      })
    }
  }
})
