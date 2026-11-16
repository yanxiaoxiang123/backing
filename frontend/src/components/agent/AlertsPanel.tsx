import { useEffect, useRef } from 'react'
import { Alert, Button, Empty, List, Space, Skeleton, Tag } from 'antd'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getAlerts, markAlertRead } from '../../services/agentRuns'

export interface AlertItem {
  id: number
  alert_type: string
  severity: string
  message: string
  run_id?: string | null
  value?: number | null
  threshold?: number | null
  is_read: boolean
  created_at?: string | null
}

const SEVERITY_COLOR: Record<string, string> = {
  info: 'blue',
  warning: 'orange',
  critical: 'red',
}
const ALERTS_KEY = ['system', 'alerts'] as const

export function AlertsPanel({ selectedAlertId }: { selectedAlertId?: number | null }) {
  const queryClient = useQueryClient()
  const selectedRef = useRef<HTMLDivElement>(null)
  const query = useQuery({
    queryKey: ALERTS_KEY,
    queryFn: getAlerts,
    staleTime: 60_000,
    retry: false,
  })
  const alerts: AlertItem[] = query.data?.alerts ?? []
  const hasSelected = alerts.some((alert) => alert.id === selectedAlertId)
  const markRead = useMutation({
    mutationFn: markAlertRead,
    onSuccess: (_data, id) => {
      queryClient.setQueryData<Awaited<ReturnType<typeof getAlerts>>>(
        ALERTS_KEY,
        (current) =>
          current
            ? {
                ...current,
                alerts: current.alerts.map((alert) =>
                  alert.id === id ? { ...alert, is_read: true } : alert,
                ),
              }
            : current,
      )
      void queryClient.invalidateQueries({ queryKey: ALERTS_KEY })
    },
  })

  useEffect(() => {
    if (hasSelected) selectedRef.current?.scrollIntoView({ block: 'nearest' })
  }, [selectedAlertId, hasSelected])

  if (query.isPending)
    return (
      <div aria-label="正在加载告警">
        <Skeleton active paragraph={{ rows: 3 }} />
      </div>
    )

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <Button
        size="small"
        loading={query.isFetching}
        onClick={() => void query.refetch()}
        aria-label="刷新告警"
      >
        刷新告警
      </Button>
      {query.isError ? (
        <Alert
          type="error"
          showIcon
          message={query.data ? '告警刷新失败' : '告警加载失败'}
          description={
            query.data
              ? '已保留上次读取的记录，请稍后重试。'
              : '暂时无法读取告警，请稍后重试。'
          }
          action={
            <Button size="small" onClick={() => void query.refetch()}>
              重试
            </Button>
          }
        />
      ) : null}
      {markRead.isError ? (
        <Alert
          type="error"
          showIcon
          message="标记已读失败"
          description="记录仍保持未读，请再次点击该记录的标记已读。"
        />
      ) : null}
      {selectedAlertId && !hasSelected && !query.isError ? (
        <Alert
          type="info"
          showIcon
          message="未找到指定告警"
          description="当前返回的列表中没有这条记录，可以刷新或查看其他告警。"
        />
      ) : null}
      {alerts.length ? (
        <List
          size="small"
          dataSource={alerts}
          renderItem={(item) => (
            <List.Item
              data-alert-id={item.id}
              aria-current={item.id === selectedAlertId ? 'true' : undefined}
              ref={item.id === selectedAlertId ? selectedRef : undefined}
              actions={[
                item.is_read ? (
                  <span key="read">已读</span>
                ) : (
                  <Button
                    key="read"
                    size="small"
                    loading={markRead.isPending && markRead.variables === item.id}
                    disabled={markRead.isPending}
                    onClick={() => markRead.mutate(item.id)}
                  >
                    标记已读
                  </Button>
                ),
              ]}
            >
              <List.Item.Meta
                title={
                  <span>
                    {item.id === selectedAlertId ? (
                      <Tag color="blue">当前告警</Tag>
                    ) : null}
                    <Tag color={SEVERITY_COLOR[item.severity] ?? 'default'}>
                      {item.severity}
                    </Tag>
                    <Tag>{item.alert_type}</Tag>
                    {item.message}
                  </span>
                }
                description={
                  <span>
                    {item.value != null && `数值：${item.value} · `}
                    {item.threshold != null && `阈值：${item.threshold} · `}
                    {item.created_at ?? ''}
                  </span>
                }
              />
            </List.Item>
          )}
        />
      ) : !query.isError ? (
        <Empty description="暂无告警" />
      ) : null}
    </Space>
  )
}
