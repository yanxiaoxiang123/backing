import type { Page } from '@playwright/test'
import { mockResearchApi } from './research'

/** Test-only data exercises the full reference density, never shipped by the app. */
export async function mockDashboardApi(page: Page) {
  const requests = await mockResearchApi(page)
  const stocks = [
    { code: 'sh.600000', name: '浦发银行' },
    { code: 'sz.000002', name: '万科A' },
    { code: 'sh.600036', name: '招商银行' },
    { code: 'sz.000001', name: '平安银行' },
  ]
  const bars = Array.from({ length: 280 }, (_, index) => {
    const date = new Date(Date.UTC(2025, 9, 9 + index))
    return {
      date: date.toISOString().slice(0, 10),
      open: 10 + index * 0.01,
      close: 10 + index * 0.01 + Math.sin(index / 8) * 0.3,
      high: 14,
      low: 9,
      volume: 1200000,
      amount: 12000000,
      symbol: 'sh.600000',
    }
  }).filter((bar) => ![0, 6].includes(new Date(bar.date).getUTCDay()))
  await page.route('**/api/v1/**', async (route) => {
    const path = new URL(route.request().url()).pathname
    let data: unknown
    if (path.endsWith('/watchlist')) {
      data = {
        total: stocks.length,
        items: stocks.map((stock, index) => ({
          id: index + 1,
          stock_code: stock.code,
          stock_name: stock.name,
          added_at: '2026-11-04T00:00:00Z',
        })),
      }
    } else if (path.endsWith('/realtime/indices')) {
      data = {
        success: true,
        data: ['上证指数', '深证成指', '沪深300', '创业板指', '科创50'].map(
          (name, index) => ({
            name,
            symbol: `index-${index}`,
            close: 3000 + index * 300.1,
            change: index === 1 ? -12 : 18.4,
            change_percent: index === 1 ? -0.4 : 0.6,
            prev_close: 2981.6 + index * 300.1,
          }),
        ),
      }
    } else if (path.endsWith('/realtime/quotes')) {
      data = {
        success: true,
        data: stocks.map((stock, index) => ({
          symbol: stock.code,
          open: 10,
          close: 10 + index,
          high: 15,
          low: 9,
          change: index === 3 ? -0.2 : 0.2,
          change_percent: index === 3 ? -2 : 2,
          prev_close: 9.8 + index,
          volume: 1200000,
          amount: 12000000,
        })),
      }
    } else if (path.includes('/realtime/')) {
      const code = decodeURIComponent(path.split('/').pop()!)
      data = {
        success: true,
        code,
        data: bars.map((bar) => ({ ...bar, symbol: code })),
      }
    } else if (path.endsWith('/agent/history')) {
      data = stocks.slice(0, 2).map((stock, index) => ({
        id: index + 1,
        stock_code: stock.code,
        stock_name: stock.name,
        analysis_date: '2026-11-05',
        mode: 'quick',
        final_signal: index ? 'hold' : 'sell',
        final_confidence: index ? 0.56 : 0.55,
        final_reason:
          '风险维度偏空，其余维度证据不足。补齐行情与公告数据后，再核验结论。',
        created_at: '2026-11-05T04:00:00Z',
        duration_s: 12,
      }))
    } else if (path.endsWith('/paper/alerts')) {
      data = {
        alerts: stocks.slice(0, 3).map((stock, index) => ({
          id: index + 1,
          alert_type: 'data_quality',
          severity: 'warning',
          message: `${stock.code} K 线数据待检查，请核验最新交易日覆盖与行情同步状态`,
          is_read: false,
          created_at: '2026-11-05T03:30:00Z',
        })),
      }
    } else if (path.endsWith('/jobs/metrics')) {
      data = {
        counters: [{ name: 'task.completed', value: 1, labels: {} }],
        durations: [],
        started_at: '2026-11-05T00:00:00Z',
      }
    } else {
      return route.fallback()
    }
    await route.fulfill({ json: data })
  })
  return { requests, bars }
}
