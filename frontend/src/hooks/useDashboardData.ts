import { useQuery } from '@tanstack/react-query'
import { getAnalysisHistory } from '../services/api'
import {
  getRealtimeBars,
  getRealtimeIndices,
  getRealtimeQuotes,
} from '../services/market'
import { getWatchlist } from '../services/watchlist'
import { agentKeys, dashboardKeys } from '../services/queryKeys'

export { dashboardKeys }

export function getMarketPollingInterval(date?: Date): number {
  const now = date instanceof Date ? date : new Date()
  const day = now.getDay()
  if (day === 0 || day === 6) {
    return 60_000 // 周末降频至 60 秒
  }
  const minutes = now.getHours() * 60 + now.getMinutes()
  // 交易时段（9:15-11:35, 12:55-15:05）使用 10 秒刷新，闭市时降频至 60 秒
  const isTradingHours =
    (minutes >= 555 && minutes <= 695) || (minutes >= 775 && minutes <= 905)
  return isTradingHours ? 10_000 : 60_000
}

export function useDashboardWatchlist() {
  return useQuery({
    queryKey: dashboardKeys.watchlist(),
    queryFn: getWatchlist,
  })
}

export function useDashboardIndices() {
  const interval = getMarketPollingInterval()
  return useQuery({
    queryKey: dashboardKeys.indices(),
    queryFn: getRealtimeIndices,
    staleTime: interval,
    refetchInterval: () => getMarketPollingInterval(),
  })
}

export function useDashboardQuotes(codes: string[]) {
  const interval = getMarketPollingInterval()
  return useQuery({
    queryKey: dashboardKeys.quotes(codes),
    queryFn: () => getRealtimeQuotes(codes),
    enabled: codes.length > 0,
    staleTime: interval,
    refetchInterval: () => getMarketPollingInterval(),
  })
}

export function useDashboardTrend(code: string | undefined) {
  return useQuery({
    queryKey: dashboardKeys.trend(code || 'none'),
    queryFn: () => getRealtimeBars(code as string, 'daily'),
    enabled: Boolean(code),
  })
}

/** The day's AI research note: the newest analysis records. */
export function useLatestAnalyses(limit = 5) {
  return useQuery({
    queryKey: agentKeys.history(0, limit),
    queryFn: () => getAnalysisHistory(undefined, 0, limit),
    retry: false,
    staleTime: 60_000,
  })
}
