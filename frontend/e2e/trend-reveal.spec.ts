import { expect, test, type Locator } from '@playwright/test'
import { mockDashboardApi } from './fixtures/dashboard'

async function lineState(chart: Locator) {
  return chart.evaluate(async (node) => {
    const source = performance
      .getEntriesByType('resource')
      .find((resource) => /echartsCustom.*\.(js|ts)/.test(resource.name))!.name
    const { default: core } = await import(source)
    const instance = core.getInstanceByDom(node)
    const model = instance.getModel().getSeriesByIndex(0)
    const clip = instance.getViewOfSeriesModel(model)._lineGroup.getClipPath()
    return {
      width: clip.shape.width as number,
      gridWidth: model.coordinateSystem.getArea().width as number,
      animation: instance.getOption().series[0].animation as boolean,
      data: instance.getOption().series[0].data as number[],
    }
  })
}

test('首页曲线从左向右展开，切换区间重播，刷新和缩放保持稳定', async ({
  page,
}, info) => {
  await mockDashboardApi(page)
  await page.goto('/')
  const chart = page.locator('.dash-chart-card div[role="img"]')
  await expect(chart.locator('canvas')).toBeVisible()
  const opening = await lineState(chart)
  expect(opening.animation).toBe(true)
  expect(opening.width).toBeLessThan(opening.gridWidth)
  await chart.screenshot({ path: info.outputPath('trend-opening.png') })
  await page.waitForTimeout(180)
  const middle = await lineState(chart)
  expect(middle.width).toBeGreaterThan(opening.width)
  expect(middle.data).toEqual(opening.data)
  await chart.screenshot({ path: info.outputPath('trend-middle.png') })
  await expect.poll(async () => (await lineState(chart)).animation).toBe(false)
  const complete = await lineState(chart)
  expect(complete.width).toBeGreaterThanOrEqual(complete.gridWidth)
  expect(complete.data).toEqual(opening.data)
  await chart.screenshot({ path: info.outputPath('trend-complete.png') })

  await page.getByRole('button', { name: '刷新数据', exact: true }).click()
  await expect(
    page.getByRole('button', { name: '刷新数据', exact: true }),
  ).toBeEnabled()
  expect(await lineState(chart)).toEqual(complete)

  await page
    .getByRole('group', { name: '走势时间范围' })
    .getByRole('button', { name: '1月', exact: true })
    .click()
  await expect(chart).toHaveAttribute('aria-label', /近1个月/)
  const changed = await lineState(chart)
  expect(changed.animation).toBe(true)
  expect(changed.width).toBeLessThan(changed.gridWidth)
  expect(changed.data.length).toBeLessThan(complete.data.length)
  await page.setViewportSize({ width: 1280, height: 720 })
  await expect.poll(async () => (await lineState(chart)).animation).toBe(false)
  const resized = await lineState(chart)
  expect(resized.width).toBeGreaterThanOrEqual(resized.gridWidth)
  await page.waitForTimeout(200)
  expect(await lineState(chart)).toEqual(resized)

  await page.locator('.dash-chart-select .ant-select-selector').click()
  await page.getByTitle('万科A (sz.000002)', { exact: true }).click()
  await expect(chart).toHaveAttribute('aria-label', /^sz\.000002/)
  const instrument = await lineState(chart)
  expect(instrument.animation).toBe(true)
  expect(instrument.width).toBeLessThan(instrument.gridWidth)
})

test('开始操作或切换到减少动态效果时立即完成展开', async ({ page }) => {
  await mockDashboardApi(page)
  await page.goto('/')
  const chart = page.locator('.dash-chart-card div[role="img"]')
  await expect(chart.locator('canvas')).toBeVisible()
  await chart.dispatchEvent('pointerdown')
  await chart.dispatchEvent('pointerup')
  await expect.poll(async () => (await lineState(chart)).animation).toBe(false)
  const stopped = await lineState(chart)
  expect(stopped.width).toBeGreaterThanOrEqual(stopped.gridWidth)

  await page
    .getByRole('group', { name: '走势时间范围' })
    .getByRole('button', { name: '1年', exact: true })
    .click()
  expect((await lineState(chart)).animation).toBe(true)
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await expect.poll(async () => (await lineState(chart)).animation).toBe(false)
  const reduced = await lineState(chart)
  expect(reduced.width).toBeGreaterThanOrEqual(reduced.gridWidth)
  await page.waitForTimeout(200)
  expect(await lineState(chart)).toEqual(reduced)
})

test('系统减少动态效果模式下首次加载与切换区间都直接显示完整曲线', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await mockDashboardApi(page)
  await page.goto('/')
  const chart = page.locator('.dash-chart-card div[role="img"]')
  await expect(chart.locator('canvas')).toBeVisible()
  for (const label of ['1月', '1年']) {
    const state = await lineState(chart)
    expect(state.animation).toBe(false)
    expect(state.width).toBeGreaterThanOrEqual(state.gridWidth)
    await page
      .getByRole('group', { name: '走势时间范围' })
      .getByRole('button', { name: label, exact: true })
      .click()
  }
  expect((await lineState(chart)).animation).toBe(false)
})
