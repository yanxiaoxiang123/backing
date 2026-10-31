import { useQuery } from '@tanstack/react-query'
import { getAlerts } from '../services/agentRuns'
import { getJobMetrics } from '../services/jobs'

/**
 * Shell-level status: unread paper-trading alerts and task counters since the
 * backend process started. Both are read-only and fail quietly; the shell shows
 * a grey dash rather than an error banner.
 */
export function useSystemStatus(options?: { enabled?: boolean }) {
  const enabled = options?.enabled ?? true

  const alertsQuery = useQuery({
    queryKey: ['system', 'alerts'],
    queryFn: getAlerts,
    enabled,
    staleTime: 60_000,
    refetchInterval: enabled ? 60_000 : false,
    retry: false,
  })

  const metricsQuery = useQuery({
    queryKey: ['system', 'metrics'],
    queryFn: getJobMetrics,
    enabled,
    staleTime: 60_000,
    refetchInterval: enabled ? 60_000 : false,
    retry: false,
  })

  const alerts = alertsQuery.data?.alerts ?? []
  const counters = metricsQuery.data?.counters ?? []
  const sum = (name: string) =>
    counters
      .filter((counter) => counter.name === name)
      .reduce((total, counter) => total + counter.value, 0)

  return {
    alerts,
    unreadAlerts: alerts.filter((alert) => !alert.is_read).length,
    completed: sum('task.completed'),
    failed: sum('task.failed'),
    isLoading: enabled && (alertsQuery.isLoading || metricsQuery.isLoading),
    alertsError: alertsQuery.isError,
    metricsError: metricsQuery.isError,
    isError: alertsQuery.isError && metricsQuery.isError,
    refetch: () => {
      void alertsQuery.refetch()
      void metricsQuery.refetch()
    },
  }
}
