import { useState } from 'react'
import { Button, Descriptions, Empty, InputNumber, Result, Space, Tag } from 'antd'
import type { BacktestPanelData } from '../../types/agent'

interface BacktestPanelProps {
  data?: BacktestPanelData | null
  objective?: string | null
  onRerun?: (params: { short_period: number; long_period: number }) => void
}

/**
 * 回测审计面板（US-2.2/2.8）：展示审计结论；可编辑策略参数发起新 run，
 * 参数修改产生新 run_id，旧回测永不覆盖。
 */
export function BacktestPanel({ data, objective, onRerun }: BacktestPanelProps) {
  const [shortPeriod, setShortPeriod] = useState(5)
  const [longPeriod, setLongPeriod] = useState(20)

  if (!data) {
    return (
      <Empty
        description={
          objective
            ? '本次研究未执行回测；请在对话中指定策略和回测目标'
            : '尚无回测结果'
        }
      />
    )
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
      <Space size="small" style={{ marginBottom: 12 }}>
        <Space.Compact>
          <span className="compact-input-label">短均线</span>
          <InputNumber
            size="small"
            min={2}
            max={60}
            value={shortPeriod}
            onChange={(v) => setShortPeriod(v ?? 5)}
          />
        </Space.Compact>
        <Space.Compact>
          <span className="compact-input-label">长均线</span>
          <InputNumber
            size="small"
            min={3}
            max={120}
            value={longPeriod}
            onChange={(v) => setLongPeriod(v ?? 20)}
          />
        </Space.Compact>
        <Button
          size="small"
          type="primary"
          disabled={!objective || !onRerun || longPeriod <= shortPeriod}
          onClick={() =>
            onRerun?.({ short_period: shortPeriod, long_period: longPeriod })
          }
        >
          参数修改 → 新 run
        </Button>
      </Space>
      <Descriptions size="small" column={1}>
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
