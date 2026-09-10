export const stockKeys = {
  all: ['stocks'] as const,
  list: (filters: {
    market?: string
    cursor: number
    limit: number
    search?: string
  }) => [...stockKeys.all, 'list', filters] as const,
  detail: (code: string) => [...stockKeys.all, 'detail', code] as const,
  overview: (code: string) => [...stockKeys.all, 'overview', code] as const,
  kline: (code: string, startDate?: string, endDate?: string) =>
    [...stockKeys.all, 'kline', code, startDate ?? null, endDate ?? null] as const,
}

export const stockSearchKeys = {
  all: [...stockKeys.all, 'search'] as const,
  query: (query: string) =>
    [...stockSearchKeys.all, query.trim().toLowerCase()] as const,
}

export const watchlistKeys = {
  all: ['watchlist'] as const,
  list: () => [...watchlistKeys.all, 'list'] as const,
  quotes: (codes: string[]) =>
    [...watchlistKeys.all, 'quotes', [...codes].sort()] as const,
}

export const dashboardKeys = {
  all: ['dashboard'] as const,
  watchlist: () => [...dashboardKeys.all, 'watchlist'] as const,
  indices: () => [...dashboardKeys.all, 'indices'] as const,
  quotes: (codes: string[]) =>
    [...dashboardKeys.all, 'quotes', [...codes].sort()] as const,
  trend: (code: string) => [...dashboardKeys.all, 'trend', code] as const,
  briefing: () => [...dashboardKeys.all, 'briefing'] as const,
}

export const strategyKeys = {
  all: ['strategies'] as const,
  catalog: () => [...strategyKeys.all, 'catalog'] as const,
}

export const backtestKeys = {
  all: ['backtests'] as const,
  list: (filters: {
    cursor: number
    limit: number
    strategy?: string
    stock?: string
  }) => [...backtestKeys.all, 'list', filters] as const,
  detail: (id: number) => [...backtestKeys.all, 'detail', id] as const,
}

export const screenerKeys = {
  all: ['screener'] as const,
  history: (limit: number) => [...screenerKeys.all, 'history', limit] as const,
  job: (id: string) => [...screenerKeys.all, 'job', id] as const,
}

export const agentKeys = {
  all: ['agent'] as const,
  history: (cursor: number, limit: number) =>
    [...agentKeys.all, 'history', cursor, limit] as const,
  detail: (id: number) => [...agentKeys.all, 'detail', id] as const,
}
