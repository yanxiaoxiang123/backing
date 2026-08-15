import { useCallback, useEffect, useState } from 'react'
import { Button, Empty, List, Space, Spin, Tag } from 'antd'
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

/** 告警面板（US-3.4）：列表 + 已读 + 刷新（阈值可配置，落库 + 面板展示）。 */
export function AlertsPanel() {
  const [alerts, setAlerts] = useState<AlertItem[]>([])
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(() => {
    setLoading(true)
    void getAlerts()
      .then((d) => setAlerts(d.alerts ?? []))
      .catch(() => setAlerts([]))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  const markRead = (id: number) => {
    void markAlertRead(id).then(() => refresh())
  }

  if (loading) return <Spin />
  if (alerts.length === 0) return <Empty description="暂无告警" />

  return (
    <div>
      <Space style={{ marginBottom: 8 }}>
        <Button size="small" onClick={refresh}>
          刷新
        </Button>
      </Space>
      <List
        size="small"
        dataSource={alerts}
        renderItem={(item) => (
          <List.Item
            actions={[
              !item.is_read ? (
                <Button key="read" size="small" onClick={() => markRead(item.id)}>
                  已读
                </Button>
              ) : null,
            ]}
          >
            <List.Item.Meta
              title={
                <span>
                  <Tag color={SEVERITY_COLOR[item.severity] ?? 'default'}>
                    {item.severity}
                  </Tag>
                  <Tag>{item.alert_type}</Tag>
                  {item.message}
                </span>
              }
              description={
                <span>
                  {item.value != null && `value: ${item.value} · `}
                  {item.threshold != null && `threshold: ${item.threshold} · `}
                  {item.created_at ?? ''}
                </span>
              }
            />
          </List.Item>
        )}
      />
    </div>
  )
}
