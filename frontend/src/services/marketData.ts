import api from './api'

export interface DataQuality {
  total_stocks: number
  covered_stocks: number
  missing_stocks: number
  coverage_pct: number
  invalid_bars: number
  total_bars: number
  raw_covered_stocks: number
  versioned_bars: number
  calendar_rows: number
}

export async function getDataQuality(): Promise<DataQuality> {
  const response = await api.get<DataQuality>('/data/quality', { params: { limit: 1 } })
  return response.data
}

export async function syncRawHistory(codes: string[], days = 730): Promise<string> {
  const now = new Date()
  // Always request through yesterday; the server validates completed sessions.
  const end = new Date(now.getTime() - 86400000)
  const start = new Date(end.getTime() - days * 86400000)
  const iso = (value: Date) =>
    new Intl.DateTimeFormat('en-CA', {
      timeZone: 'Asia/Shanghai',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    }).format(value)
  const response = await api.post<{ job_id: string }>('/data/history/sync', {
    codes,
    start_date: iso(start),
    end_date: iso(end),
    metadata: true,
  })
  return response.data.job_id
}

export async function syncResearchHistory(
  code: string,
  start: string,
  end: string,
): Promise<string> {
  return syncResearchHistories([code], start, end)
}

export async function syncResearchHistories(
  codes: string[],
  start: string,
  end: string,
): Promise<string> {
  const response = await api.post<{ job_id: string }>('/data/history/sync', {
    codes,
    start_date: start,
    end_date: end,
    metadata: true,
  })
  return response.data.job_id
}
