import { expect, test, type Page } from '@playwright/test'
import fs from 'node:fs/promises'

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
  await page.getByText('滑动微调天数', { exact: true }).click()
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
  await page.getByText('逐日预测与 K 线明细', { exact: true }).click()
  await expect(page.getByRole('heading', { name: '预测 K 线明细' })).toBeVisible()
  expect(submitted).toMatchObject({
    model: 'kronos-small',
    stock_code: 'sh.600000',
    kline_days: 256,
    prediction_days: 1,
  })
  await page.reload()
  await page.getByText('逐日预测与 K 线明细', { exact: true }).click()
  await expect(page.getByRole('heading', { name: '预测 K 线明细' })).toBeVisible()
  expect(submissions).toBe(1)
  await page.getByText('滑动微调天数', { exact: true }).click()
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

async function mockExperiments(
  page: Page,
  options?: { fail?: boolean; pending?: boolean },
) {
  const submitted: Array<{ kind: string; request: Record<string, unknown> }> = []
  let cancelled = false
  await page.route('**/api/v1/**', async (route) => {
    const path = new URL(route.request().url()).pathname
    let body: unknown = {}
    if (path.endsWith('/auth/me')) body = { authenticated: true }
    else if (path.endsWith('/stocks'))
      body = [
        { id: 1, code: 'sh.600000', name: '浦发银行', market: 'sh', created_at: '' },
      ]
    else if (path.includes('/stocks/'))
      body = {
        id: 1,
        code: 'sh.600000',
        name: '浦发银行',
        market: 'sh',
        created_at: '',
      }
    else if (path.endsWith('/dl/models'))
      body = {
        models: ['kronos-small', 'kronos-base', 'timesfm-2.5', 'legacy'].map((id) => ({
          id,
          name: id,
          available: true,
          min_context: 60,
          max_context: 512,
          min_horizon: 1,
          max_horizon: 30,
        })),
        remote: { available: true },
      }
    else if (path.endsWith('/submit')) {
      const kind = path.includes('/backtest/') ? 'backtest' : 'predict'
      submitted.push({ kind, request: route.request().postDataJSON() })
      body = {
        job_id: `experiment-${submitted.length - 1}`,
        status: 'pending',
        message: '已排队',
      }
    } else if (path.endsWith('/cancel')) {
      cancelled = true
      body = { status: 'cancelled' }
    } else if (/\/jobs\/experiment-\d+$/.test(path)) {
      const index = Number(path.split('-').pop())
      const entry = submitted[index]
      const data =
        entry.kind === 'predict'
          ? {
              stock_code: entry.request.stock_code,
              model: entry.request.model,
              forecast_target:
                entry.request.model === 'timesfm-2.5' ? 'close' : 'ohlcv_amount',
              current_price: 10,
              last_date: '2026-10-30',
              prediction_dates: ['2026-11-02', '2026-11-03'],
              predicted_prices: [11, 12],
              kline_data: [
                {
                  date: '2026-10-29',
                  open: 9,
                  high: 10,
                  low: 8,
                  close: 9,
                  volume: 1000,
                },
                {
                  date: '2026-10-30',
                  open: 9,
                  high: 11,
                  low: 9,
                  close: 10,
                  volume: 1200,
                },
              ],
              execution_time_ms: 1500,
            }
          : {
              model: entry.request.model,
              experiment: entry.request,
              dates: ['2026-10-29', '2026-10-30'],
              close_prices: [9, 10],
              total_return: 5,
              annualized_return: 8,
              sharpe_ratio: 1.2,
              max_drawdown: 2,
              win_rate: 50,
              total_trades: 2,
              portfolio_values: [250000, 262500],
              trades: [
                {
                  date: '2026-10-29',
                  action: 'BUY',
                  price: 9,
                  quantity: 100,
                  cost: 901,
                },
                {
                  date: '2026-10-30',
                  action: 'SELL',
                  price: 10,
                  quantity: 100,
                  revenue: 999,
                  return: 10.87,
                  profit: 98,
                },
              ],
            }
      body = {
        id: `experiment-${index}`,
        job_type: `dl_${entry.kind}`,
        status: cancelled
          ? 'failed'
          : options?.fail
            ? 'failed'
            : options?.pending
              ? 'running'
              : 'completed',
        progress: options?.pending ? 0.25 : 1,
        message: '实验任务',
        error: cancelled
          ? '任务已取消'
          : options?.fail
            ? '远程模型显存不足'
            : undefined,
        created_at: '2026-11-05T04:00:00',
        updated_at: '2026-11-05T04:34:53',
        payload: entry.request,
        result: { success: true, data },
      }
    } else if (path.endsWith('/paper/alerts')) body = { alerts: [] }
    else if (path.endsWith('/jobs/metrics')) body = { counters: [], durations: [] }
    await route.fulfill({ json: body })
  })
  return submitted
}

test('TimesFM supports shared horizon controls, close-only details and restored jobs', async ({
  page,
}) => {
  const submitted = await mockExperiments(page)
  await page.goto('/dl-prediction')
  await page.locator('.ant-select-selector').first().click()
  await page
    .locator('.ant-select-item-option')
    .filter({ hasText: 'TimesFM 2.5 200M' })
    .click()
  await page.getByLabel('股票代码').fill('浦发')
  await page.getByTitle('sh.600000 - 浦发银行').click()
  await page.getByRole('button', { name: '30日', exact: true }).click()
  await page.getByRole('button', { name: '预测未来 30 个交易日' }).click()
  await expect(page.locator('.dl-run-status')).toHaveText('运行完成')
  expect(submitted[0].request).toMatchObject({
    model: 'timesfm-2.5',
    prediction_days: 30,
    kline_days: 256,
  })
  await page.getByText('逐日预测与 K 线明细', { exact: true }).click()
  await expect(page.getByText(/TimesFM 收盘价点预测/)).toBeVisible()
  await expect(page.getByRole('heading', { name: '预测 K 线明细' })).toHaveCount(0)
  await page.reload()
  await expect(page.locator('.dl-run-status')).toHaveText('运行完成')
  expect(submitted).toHaveLength(1)
})

test('presets, backtest dates and capital, chart tabs, history and result export remain usable', async ({
  page,
}) => {
  const submitted = await mockExperiments(page)
  await page.goto('/dl-prediction')
  await expect(page.getByRole('button', { name: '导出结果' })).toBeDisabled()
  await page.getByLabel('股票代码').fill('浦发')
  await page.getByTitle('sh.600000 - 浦发银行').click()
  await page.getByRole('button', { name: '15日', exact: true }).click()
  await expect(page.getByLabel('预测交易日数')).toHaveValue('15')
  await page.getByRole('button', { name: '预测未来 15 个交易日' }).click()
  await expect(page.locator('.dl-run-status')).toHaveText('运行完成')
  await expect(page.locator('.dl-result-grid')).toContainText('2026-11-05 12:34')
  await expect(page.locator('.dl-chart-metrics')).toContainText('12.00')
  await expect(page.getByText('演示数据', { exact: true })).toHaveCount(0)
  await expect(page.getByText(/网络异常/)).toHaveCount(0)
  await page.getByLabel('初始资金').fill('250000')
  await page.getByLabel('回测区间').fill('2025.01.02')
  await page.getByLabel('回测区间').press('Tab')
  await page.locator('#dl-end-date').click()
  await page.locator('#dl-end-date').fill('2026.10.30')
  await page.locator('#dl-end-date').press('Enter')
  await page.locator('#dl-end-date').press('Tab')
  await expect
    .poll(() =>
      page.evaluate(() =>
        JSON.parse(sessionStorage.getItem('backing_dl_dateRange') || '[]'),
      ),
    )
    .toEqual(['2025-01-02', '2026-10-30'])
  await page.getByRole('button', { name: '执行回测' }).click()
  await expect(
    page.getByRole('heading', { name: '回测结果', exact: true }),
  ).toBeVisible()
  await expect(page.locator('.dl-run-status')).toHaveText('运行完成')
  expect(submitted[1]).toEqual({
    kind: 'backtest',
    request: {
      stock_code: 'sh.600000',
      model: 'kronos-small',
      prediction_days: 15,
      kline_days: 256,
      start_date: '2025-01-02',
      end_date: '2026-10-30',
      initial_capital: 250000,
    },
  })
  await page.getByText('交易记录（2）', { exact: true }).click()
  await expect(page.getByRole('cell', { name: '10.87%' })).toBeVisible()
  await page
    .locator('.ant-segmented-item-label')
    .getByText('价格预测', { exact: true })
    .click()
  await expect(page.locator('.dl-chart-metrics')).toContainText('12.00')
  const downloadPromise = page.waitForEvent('download')
  await page.getByRole('button', { name: '导出结果' }).click()
  const download = await downloadPromise
  expect(download.suggestedFilename()).toBe('dl-predict-sh.600000-experiment-0.json')
  const exported = JSON.parse(await fs.readFile((await download.path())!, 'utf8'))
  expect(exported.response.data.predicted_prices).toEqual([11, 12])
  expect(exported.request.prediction_days).toBe(15)
  await page.getByRole('button', { name: '历史记录' }).click()
  const drawer = page.getByRole('dialog', { name: '实验历史' })
  await expect(drawer.locator('.dl-history-list button')).toHaveCount(2)
  await drawer.getByRole('button', { name: /历史回测/ }).click()
  await expect(
    page.getByRole('heading', { name: '回测结果', exact: true }),
  ).toBeVisible()
  await expect(page.locator('.dl-run-status')).toHaveText('运行完成')
  expect(submitted).toHaveLength(2)
  await expect(drawer).not.toBeVisible()
  await page.getByLabel('预测模型').press('ArrowDown')
  await page.getByTitle('现有预测器（含技术指标降级）', { exact: true }).click()
  await expect(page.getByLabel('预测交易日数')).toHaveValue('5')
  await expect(page.getByLabel('历史 K 线')).toHaveValue('250')
  await expect(page.getByRole('button', { name: '30日', exact: true })).toBeDisabled()
  await page.getByRole('button', { name: '预测未来 5 个交易日' }).click()
  await expect(page.locator('.dl-run-status')).toHaveText('运行完成')
  expect(submitted[2].request).toMatchObject({
    model: 'legacy',
    kline_days: 250,
    prediction_days: 5,
  })
})

test('failed experiments keep an honest error and recoverable controls', async ({
  page,
}) => {
  await mockExperiments(page, { fail: true })
  await page.goto('/dl-prediction')
  await page.getByLabel('股票代码').fill('浦发')
  await page.getByTitle('sh.600000 - 浦发银行').click()
  const predict = page.getByRole('button', { name: '预测未来 5 个交易日' })
  await predict.click()
  await expect(page.getByText('远程模型显存不足', { exact: true })).toBeVisible()
  await expect(predict).toBeEnabled()
  await expect(page.getByRole('button', { name: '导出结果' })).toBeDisabled()
})

test('a running experiment can be cancelled without showing its late result', async ({
  page,
}) => {
  await mockExperiments(page, { pending: true })
  await page.goto('/dl-prediction')
  await page.getByLabel('股票代码').fill('浦发')
  await page.getByTitle('sh.600000 - 浦发银行').click()
  await page.getByRole('button', { name: '预测未来 5 个交易日' }).click()
  await expect(page.getByLabel('预测交易日数')).toBeDisabled()
  await page.getByRole('button', { name: '取消任务' }).click()
  await expect(page.getByText('任务已取消', { exact: true })).toBeVisible()
  await expect(page.getByLabel('预测交易日数')).toBeEnabled()
  await expect(page.getByRole('button', { name: '导出结果' })).toBeDisabled()
})

test('the reference layout fills the desktop and navigation stays separate from bottom utilities', async ({
  page,
}) => {
  await mockExperiments(page)
  await page.setViewportSize({ width: 1592, height: 988 })
  await page.goto('/dl-prediction')
  const sidebar = page.locator('.shell-sidebar')
  const config = page.locator('.dl-config-panel')
  const analysis = page.locator('.dl-analysis-column')
  await expect(config).toBeVisible()
  const sideBox = (await sidebar.boundingBox())!
  const configBox = (await config.boundingBox())!
  const analysisBox = (await analysis.boundingBox())!
  expect(sideBox.width).toBe(250)
  expect(configBox.width).toBe(340)
  expect(configBox.x - (sideBox.x + sideBox.width)).toBe(24)
  expect(analysisBox.x - (configBox.x + configBox.width)).toBe(18)
  expect(1592 - analysisBox.x - analysisBox.width).toBe(24)
  const item = sidebar.getByRole('link', { name: '自选股', exact: true })
  const text = item.locator('.shell-nav-content')
  const original = await text.boundingBox()
  await item.hover()
  await expect
    .poll(async () => {
      const highlight = (await sidebar.locator('.shell-nav-highlight').boundingBox())!
      const row = (await item.boundingBox())!
      return Math.abs(highlight.width - row.width) + Math.abs(highlight.y - row.y)
    })
    .toBeLessThan(1)
  expect(await text.boundingBox()).toEqual(original)
  await page.setViewportSize({ width: 1592, height: 600 })
  await sidebar.evaluate((node) => {
    node.scrollTop = node.scrollHeight
  })
  const navBox = (await sidebar.locator('nav').boundingBox())!
  const bottomBox = (await sidebar.locator('.shell-sidebar-bottom').boundingBox())!
  expect(navBox.y + navBox.height).toBeLessThanOrEqual(bottomBox.y)
  await expect(sidebar.getByRole('button', { name: '退出登录' })).toBeInViewport()
})
