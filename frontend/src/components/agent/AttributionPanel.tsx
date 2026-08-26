import { useEffect, useState } from 'react'
import { Col, Descriptions, Empty, Row, Spin, Statistic, Tag } from 'antd'
import { getAttribution } from '../../services/agentRuns'
import type { AttributionData } from '../../types/agent'

function pct(v: number | undefined | null): string {
  return v == null ? '—' : `${(v * 100).toFixed(2)}%`
}

/** 盘后归因面板（US-3.3）：组合相对 sh.000300 的收益分解。 */
export function AttributionPanel({ runId }: { runId: string | null }) {
  const [data, setData] = useState<AttributionData | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    let cancelled = false
    setData(null)
    if (!runId) {
      setLoading(false)
      return () => {
        cancelled = true
      }
    }
    setLoading(true)
    void getAttribution(runId)
      .then((d) => {
        if (!cancelled) setData(d)
      })
      .catch(() => {
        if (!cancelled) setData(null)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [runId])

  if (loading) return <Spin />
  if (!runId) return <Empty description="请先运行一次股票研究" />
  if (!data) return <Empty description="当前 Run 暂无归因数据（模拟盘尚无成交）" />

  return (
    <div>
      <Row gutter={16}>
        <Col span={8}>
          <Statistic title="组合收益" value={pct(data.total_portfolio_return)} />
        </Col>
        <Col span={8}>
          <Statistic title="基准收益" value={pct(data.total_benchmark_return)} />
        </Col>
        <Col span={8}>
          <Statistic
            title="Alpha（超额）"
            value={pct(data.alpha)}
            valueStyle={{ color: data.alpha >= 0 ? '#3f8600' : '#cf1322' }}
          />
        </Col>
      </Row>
      <Descriptions size="small" column={2} style={{ marginTop: 12 }}>
        <Descriptions.Item label="Beta（暴露）">{data.beta}</Descriptions.Item>
        <Descriptions.Item label="暴露贡献">
          {pct(data.exposure_effect)}
        </Descriptions.Item>
        <Descriptions.Item label="选股/择时残差">
          {pct(data.selection_effect)}
        </Descriptions.Item>
        <Descriptions.Item label="费用拖累">{pct(data.cost_drag)}</Descriptions.Item>
        <Descriptions.Item label="区间">
          {data.start_date} → {data.end_date}
        </Descriptions.Item>
        <Descriptions.Item label="基准">
          {data.benchmark_available ? (
            <Tag color="green">sh.000300</Tag>
          ) : (
            <Tag>基准不可用（退化）</Tag>
          )}
        </Descriptions.Item>
      </Descriptions>
    </div>
  )
}
