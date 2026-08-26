import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  getRealtimeBars,
  getRealtimeIndices,
  getRealtimeQuotes,
  getWatchlist,
} from '../services/api'

export const dashboardKeys = {
  all: ['dashboard'] as const,
  watchlist: () => [...dashboardKeys.all, 'watchlist'] as const,
  indices: () => [...dashboardKeys.all, 'indices'] as const,
  quotes: (codes: string[]) => [...dashboardKeys.all, 'quotes', codes] as const,
  trend: (code: string) => [...dashboardKeys.all, 'trend', code] as const,
}

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

export function useRefreshDashboard() {
  const queryClient = useQueryClient()
  return () => queryClient.invalidateQueries({ queryKey: dashboardKeys.all })
}
