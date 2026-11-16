import { Descriptions, Empty } from 'antd'
import { formatNumber } from '../../utils/dataFormat'

const labels: Record<string, string> = {
  short_window: '短期窗口',
  long_window: '长期窗口',
  short_period: '短期周期',
  long_period: '长期周期',
  lookback: '回看窗口',
  period: '周期',
  threshold: '阈值',
  stop_loss: '止损',
  take_profit: '止盈',
}

function readable(value: unknown): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'boolean') return value ? '是' : '否'
  if (typeof value === 'number')
    return Number.isInteger(value) ? formatNumber(value, 0) : String(value)
  if (Array.isArray(value)) return value.map(readable).join('、')
  if (typeof value === 'object')
    return Object.entries(value)
      .map(([key, item]) => `${labels[key] || key}：${readable(item)}`)
      .join('；')
  return String(value)
}

export function ParameterSnapshot({
  parameters,
}: {
  parameters?: Record<string, unknown> | null
}) {
  if (!parameters || !Object.keys(parameters).length) {
    return (
      <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="未保存参数（旧记录）" />
    )
  }
  return (
    <Descriptions
      size="small"
      bordered
      column={{ xs: 1, sm: 2, md: 2, lg: 2, xl: 2, xxl: 2 }}
      className="parameter-snapshot"
    >
      {Object.entries(parameters).map(([key, value]) => (
        <Descriptions.Item key={key} label={labels[key] || key}>
          {readable(value)}
        </Descriptions.Item>
      ))}
    </Descriptions>
  )
}
