import type { Page } from '@playwright/test'
import { backtest, mockResearchApi } from './research'

export const historyRecords = Array.from({ length: 26 }, (_, index) => {
  const totalReturn = [5.2, -2.8, 0, 1.7][index % 4]
  const finalCapital = backtest.initial_capital * (1 + totalReturn / 100)
  const stockCode = index % 2 ? 'sh.600036' : 'sh.600000'
  return {
    ...backtest,
    id: 41 + index,
    result_id: 41 + index,
    stock_code: stockCode,
    strategy_name: index % 3 ? 'ma_cross' : 'momentum',
    total_return: totalReturn,
    annual_return: totalReturn,
    final_capital: finalCapital,
    metrics: {
      ...backtest.metrics,
      total_return: totalReturn,
      annual_return: totalReturn,
    },
    portfolio_values: backtest.portfolio_values.map((point, pointIndex, points) => {
      const totalValue =
        backtest.initial_capital +
        ((finalCapital - backtest.initial_capital) * pointIndex) / (points.length - 1)
      return {
        ...point,
        total_value: totalValue,
        position_value: totalValue - point.cash,
        positions: { [stockCode]: { ...point.positions['sh.600000'] } },
      }
    }),
    created_at: `2026-11-${String(6 - Math.floor(index / 5)).padStart(2, '0')}T04:${String(50 - index).padStart(2, '0')}:00Z`,
  }
})

export async function mockHistoryApi(page: Page) {
  await mockResearchApi(page)
  const requests: string[] = []
  await page.route('**/api/v1/backtest/**', (route) => {
    const url = new URL(route.request().url())
    requests.push(url.pathname + url.search)
    if (url.pathname.endsWith('/results')) {
      const rows = historyRecords.filter(
        (row) =>
          row.stock_code.includes(url.searchParams.get('stock_code') || '') &&
          row.strategy_name.includes(url.searchParams.get('strategy_name') || ''),
      )
      if (url.searchParams.get('sort') === 'return')
        rows.sort((a, b) => b.total_return - a.total_return)
      const skip = Number(url.searchParams.get('skip') || 0)
      const limit = Number(url.searchParams.get('limit') || 20)
      return route.fulfill({
        json: rows.slice(skip, skip + limit),
        headers: { 'x-total-count': String(rows.length) },
      })
    }
    const row = historyRecords.find(
      (row) => row.id === Number(url.pathname.split('/').at(-1)),
    )
    return row
      ? route.fulfill({ json: row })
      : route.fulfill({ status: 404, json: { detail: '记录不存在' } })
  })
  return requests
}
