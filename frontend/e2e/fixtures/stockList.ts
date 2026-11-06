import type { Page } from '@playwright/test'
import { mockResearchApi } from './research'

/** Test-only instruments for checking a full table and real server pagination. */
export const stockListRows = [
  ['sz.000001', '平安银行', '1991-04-03'],
  ['sz.000002', '万科A', '1991-01-29'],
  ['sz.000006', '深振业A', '1992-04-27'],
  ['sz.000007', '全新好', '1992-04-13'],
  ['sz.000008', '神州高铁', '1992-05-07'],
  ['sz.000009', '中国宝安', '1991-06-25'],
  ['sz.000010', '美丽生态', '1995-10-27'],
  ['sz.000011', '深物业A', '1992-03-30'],
  ['sz.000012', '南玻A', '1992-02-28'],
  ['sz.000014', '沙河股份', '1992-06-02'],
  ['sz.000016', '深康佳A', '1992-03-27'],
  ['sz.000157', '中联重科', '2000-10-12'],
  ['sh.600000', '浦发银行', '1999-11-10'],
  ['sh.600036', '招商银行', '2002-04-09'],
  ['sh.600519', '贵州茅台', '2001-08-27'],
  ['sh.601169', '北京银行', '2007-09-19'],
  ['bj.835185', '贝特瑞', '2021-11-15'],
  ['bj.836077', '吉林碳谷', '2021-11-15'],
].map(([code, name, list_date], index) => ({
  id: index + 1,
  code,
  name,
  list_date,
  market: code.slice(0, 2),
  created_at: '2026-01-01T00:00:00Z',
}))

export async function mockStockListApi(page: Page) {
  const requests = await mockResearchApi(page)
  const listRequests: {
    cursor: number
    limit: number
    search: string
    market: string
  }[] = []
  const submissions: { path: string; body: unknown }[] = []
  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url())
    if (url.pathname.endsWith('/stocks') && route.request().method() === 'GET') {
      const params = {
        cursor: Number(url.searchParams.get('cursor')) || 0,
        limit: Number(url.searchParams.get('limit')) || 20,
        search: url.searchParams.get('search') || '',
        market: url.searchParams.get('market') || '',
      }
      listRequests.push(params)
      const matching = stockListRows.filter(
        (row) =>
          (!params.market || params.market === row.market) &&
          `${row.name} ${row.code}`.includes(params.search),
      )
      await route.fulfill({
        json: matching.slice(params.cursor, params.cursor + params.limit),
        headers: { 'x-total-count': String(matching.length) },
      })
    } else if (
      url.pathname.endsWith('/stocks/sync/submit') ||
      url.pathname.endsWith('/stocks/sync-kline/submit')
    ) {
      submissions.push({ path: url.pathname, body: route.request().postDataJSON() })
      await route.fulfill({ json: { job_id: 'stock-list-sync', message: '已排队' } })
    } else if (url.pathname.endsWith('/data/quality')) {
      await route.fulfill({
        json: {
          total_stocks: stockListRows.length,
          covered_stocks: 2,
          missing_stocks: stockListRows.length - 2,
          coverage_pct: 11.1,
          invalid_bars: 0,
          total_bars: 1138924,
          raw_covered_stocks: 8,
          versioned_bars: 1138924,
          calendar_rows: 5000,
        },
      })
    } else return route.fallback()
  })
  return { requests, listRequests, submissions }
}
