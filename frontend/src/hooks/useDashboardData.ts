import { useQuery, useQueryClient } from '@tanstack/react-query'
import { getDashboardSummary } from '../services/api'
import {
  getRealtimeBars,
  getRealtimeIndices,
  getRealtimeQuotes,
} from '../services/market'
import { getWatchlist } from '../services/watchlist'
import { dashboardKeys } from '../services/queryKeys'

export { dashboardKeys }

export function useDashboardWatchlist() {
  return useQuery({
    queryKey: dashboardKeys.watchlist(),
    queryFn: getWatchlist,
  })
}

export function useDashboardIndices() {
  return useQuery({
    queryKey: dashboardKeys.indices(),
    queryFn: getRealtimeIndices,
  })
}

export function useDashboardQuotes(codes: string[]) {
  return useQuery({
    queryKey: dashboardKeys.quotes(codes),
    queryFn: () => getRealtimeQuotes(codes),
    enabled: codes.length > 0,
  })
}

export function useDashboardTrend(code: string | undefined) {
  return useQuery({
    queryKey: dashboardKeys.trend(code || 'none'),
    queryFn: () => getRealtimeBars(code as string, 'daily'),
    enabled: Boolean(code),
  })
}

export function useDashboardBriefing() {
  return useQuery({
    queryKey: dashboardKeys.briefing(),
    queryFn: getDashboardSummary,
    retry: false,
    staleTime: 60_000,
  })
}

export function useRefreshDashboard() {
  const queryClient = useQueryClient()
  return () => queryClient.invalidateQueries({ queryKey: dashboardKeys.all })
}
