import { expect, test } from '@playwright/test'

test('DL page submits Kronos, restores a job after reload, and labels changed settings', async ({
  page,
}, testInfo) => {
  let submitted: Record<string, unknown> | undefined
  let submissions = 0
  await page.route('**/api/v1/**', async (route) => {
    const path = new URL(route.request().url()).pathname
    let body: unknown = {}
    if (path.endsWith('/auth/me')) body = { authenticated: true }
    else if (path.endsWith('/stocks')) {
      body = [{ id: 1, code: 'sh.600000', name: '浦发银行', market: 'sh' }]
    } else if (path.endsWith('/dl/models')) {
      body = {
        models: [{ id: 'kronos-small', name: 'Kronos-small', available: true }],
        remote: { available: true },
      }
    } else if (path.endsWith('/dl/predict/submit')) {
      submissions++
      submitted = route.request().postDataJSON()
      body = { job_id: 'dl-fixture', status: 'pending', message: 'queued' }
    } else if (path.endsWith('/jobs/dl-fixture')) {
      body = {
        id: 'dl-fixture',
        job_type: 'dl_predict',
        status: 'completed',
        progress: 1,
        message: '实验完成',
        result: {
          success: true,
          data: {
            stock_code: 'sh.600000',
            model: 'kronos-small',
            current_price: 10,
            last_date: '2026-10-30',
            input_start: '2025-10-10',
            execution_time_ms: 1000,
            prediction_dates: ['2026-11-02'],
            predicted_prices: [11],
            kline_data: [
              {
                date: '2026-10-30',
                open: 10,
                high: 11,
                low: 9,
                close: 10,
                volume: 100000,
              },
            ],
            predicted_klines: [
              {
                date: '2026-11-02',
                open: 10.2,
                high: 11.2,
                low: 10.1,
                close: 11,
                volume: 120000,
                amount: 1300000,
                ohlc_valid: true,
              },
            ],
          },
        },
      }
    } else if (path.endsWith('/paper/alerts')) body = { items: [], total: 0 }
    await route.fulfill({ json: body })
  })
  await page.goto('/dl-prediction')
  await page.getByLabel('股票代码').fill('浦发')
  await page.getByTitle('sh.600000 - 浦发银行').click()
  const horizonSlider = page.getByRole('slider', { name: '滑动选择预测天数' })
  const horizonInput = page.getByLabel('预测交易日数')
  await expect(horizonSlider).toHaveAttribute('aria-valuenow', '5')
  await horizonSlider.press('End')
  await expect(horizonInput).toHaveValue('30')
  await horizonInput.fill('17')
  await expect(horizonSlider).toHaveAttribute('aria-valuenow', '17')
  const handle = await horizonSlider.boundingBox()
  const rail = await page.locator('.ant-slider-rail').boundingBox()
  expect(handle).not.toBeNull()
  expect(rail).not.toBeNull()
  await page.mouse.move(handle!.x + handle!.width / 2, handle!.y + handle!.height / 2)
  await page.mouse.down()
  await page.mouse.move(rail!.x, rail!.y + rail!.height / 2, { steps: 10 })
  await page.mouse.up()
  await expect(horizonInput).toHaveValue('1')
  await page.getByLabel('预测交易日数').fill('1')
  await page.getByRole('button', { name: '预测未来 1 个交易日' }).click()
  await expect(page.getByRole('heading', { name: '预测 K 线明细' })).toBeVisible()
  expect(submitted).toMatchObject({
    model: 'kronos-small',
    stock_code: 'sh.600000',
    kline_days: 256,
    prediction_days: 1,
  })
  await page.reload()
  await expect(page.getByRole('heading', { name: '预测 K 线明细' })).toBeVisible()
  expect(submissions).toBe(1)
  await expect(horizonSlider).toHaveAttribute('aria-valuenow', '1')
  await page.getByLabel('预测交易日数').fill('10')
  await expect(horizonSlider).toHaveAttribute('aria-valuenow', '10')
  await expect(page.getByText(/当前显示原实验/)).toBeVisible()
  for (const width of [1440, 768, 390]) {
    await page.setViewportSize({ width, height: 900 })
    await expect
      .poll(() =>
        page.evaluate(() => document.documentElement.scrollWidth > innerWidth),
      )
      .toBe(false)
    await page.screenshot({
      path: testInfo.outputPath(`dl-horizon-${width}.png`),
      fullPage: true,
    })
  }
})
