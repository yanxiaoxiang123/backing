import { Descriptions, Empty, Result, Statistic, Row, Col, Tag } from 'antd'
import type { BacktestPanelData } from '../../types/agent'

export function BacktestPanel({ data }: { data?: BacktestPanelData | null }) {
  if (!data) {
    return <Empty description="尚无回测结果" />
  }
  return (
    <div>
      {data.passed !== undefined && (
        <Result
          status={data.passed ? 'success' : 'error'}
          title={data.passed ? '回测审计通过' : '回测审计拒绝'}
          subTitle={(data.reasons ?? []).join('；')}
          style={{ padding: '12px 0' }}
        />
      )}
      <Row gutter={16}>
        <Col span={8}>
          <Statistic
            title="总收益"
            value={
              data.total_return != null ? (data.total_return * 100).toFixed(2) : '—'
            }
            suffix="%"
          />
        </Col>
        <Col span={8}>
          <Statistic
            title="年化收益"
            value={
              data.annual_return != null ? (data.annual_return * 100).toFixed(2) : '—'
            }
            suffix="%"
          />
        </Col>
        <Col span={8}>
          <Statistic
            title="最大回撤"
            value={
              data.max_drawdown_pct != null
                ? (data.max_drawdown_pct * 100).toFixed(2)
                : '—'
            }
            suffix="%"
          />
        </Col>
      </Row>
      <Descriptions size="small" column={1} style={{ marginTop: 12 }}>
        <Descriptions.Item label="样本外 Sharpe">
          {data.sharpe_out_of_sample ?? '—'}
        </Descriptions.Item>
        <Descriptions.Item label="策略">{data.strategy_name ?? '—'}</Descriptions.Item>
        <Descriptions.Item label="数据快照">
          {data.snapshot_id ?? '—'}
        </Descriptions.Item>
        {data.reasons?.map((reason, i) => (
          <Descriptions.Item key={i} label="审计">
            <Tag color="blue">{reason}</Tag>
          </Descriptions.Item>
        ))}
      </Descriptions>
    </div>
  )
}
