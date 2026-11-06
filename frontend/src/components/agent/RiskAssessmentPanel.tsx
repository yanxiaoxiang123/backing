import { Prose } from '../Prose'
import { useState } from 'react'
import { Alert, Button, Descriptions, Form, Input, InputNumber, Table } from 'antd'
import { assessRunRisk, proposeRiskOrder } from '../../services/agentRuns'
import { getApiErrorMessage } from '../../services/api'
import type { PortfolioRiskAssessment, RiskPanelData } from '../../types/agent'
import { RiskPanel } from './RiskPanel'

export function RiskAssessmentPanel({
  runId,
  stockCode,
  data,
  onAssessed,
}: {
  runId?: string | null
  stockCode?: string | null
  data?: RiskPanelData | null
  onAssessed?: () => void
}) {
  const [assessment, setAssessment] = useState<PortfolioRiskAssessment | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [proposing, setProposing] = useState<string | null>(null)
  const [proposed, setProposed] = useState<string[]>([])
  const propose = async (order: PortfolioRiskAssessment['orders'][number]) => {
    if (!runId || !assessment) return
    setProposing(order.stock_code)
    setError('')
    try {
      await proposeRiskOrder(runId, {
        stock_code: order.stock_code,
        side: order.side,
        quantity: order.quantity,
        risk_artifact_id: assessment.artifact_id,
      })
      setProposed((codes) => [...codes, order.stock_code])
      onAssessed?.()
    } catch (error) {
      setError(getApiErrorMessage(error))
    } finally {
      setProposing(null)
    }
  }
  const submit = async (values: { weight: number; stop?: number; reason: string }) => {
    if (!runId || !stockCode) return
    setBusy(true)
    setError('')
    setAssessment(null)
    setProposed([])
    try {
      const report = await assessRunRisk(runId, {
        targets: [
          {
            stock_code: stockCode,
            target_weight: values.weight / 100,
            stop_loss_pct: values.stop == null ? null : values.stop / 100,
            reason: values.reason,
          },
        ],
      })
      setAssessment(report)
      onAssessed?.()
    } catch (error) {
      setError(getApiErrorMessage(error))
    } finally {
      setBusy(false)
    }
  }
  return (
    <section aria-label="组合风险评估">
      {runId && stockCode ? (
        <Form
          layout="vertical"
          onFinish={(values) => void submit(values)}
          onValuesChange={() => setAssessment(null)}
        >
          <Prose as="p">
            为 {stockCode} 提供明确目标，按当前账户现金、持仓和风险限制计算建议数量。
          </Prose>
          <Form.Item
            name="weight"
            label="目标仓位（%）"
            rules={[{ required: true, message: '请输入目标仓位' }]}
          >
            <InputNumber
              min={0}
              max={100}
              style={{ width: '100%' }}
              placeholder="如 10"
            />
          </Form.Item>
          <Form.Item
            name="stop"
            label="止损距离（%）"
            extra="加仓及保留持仓须提供止损假设。"
          >
            <InputNumber
              min={0.01}
              max={99.99}
              style={{ width: '100%' }}
              placeholder="如 5"
            />
          </Form.Item>
          <Form.Item
            name="reason"
            label="调整理由"
            rules={[{ required: true, whitespace: true, message: '请说明调整理由' }]}
          >
            <Input.TextArea maxLength={1000} autoSize={{ minRows: 2, maxRows: 4 }} />
          </Form.Item>
          <Button htmlType="submit" loading={busy}>
            计算风险与建议数量
          </Button>
          <Prose as="p">
            提议后须人工审批；获批委托在下个交易日日线核验后，以开盘价模拟记账。
          </Prose>
        </Form>
      ) : null}
      {error ? <Alert type="error" showIcon message={error} /> : null}
      {assessment ? (
        <Descriptions column={1} size="small" style={{ marginBlock: 12 }}>
          <Descriptions.Item label="账户">{assessment.account_id}</Descriptions.Item>
          <Descriptions.Item label="账户权益">
            {assessment.equity.toLocaleString()}
          </Descriptions.Item>
          <Descriptions.Item label="预计剩余现金">
            {assessment.projected_cash.toFixed(2)}
          </Descriptions.Item>
          <Descriptions.Item label="预计费用">
            {assessment.estimated_fees.toFixed(2)}
          </Descriptions.Item>
        </Descriptions>
      ) : null}
      <RiskPanel data={assessment?.proposal ?? data} />
      {assessment?.orders.length ? (
        <Table
          size="small"
          pagination={false}
          rowKey="stock_code"
          dataSource={assessment.orders}
          scroll={{ x: true }}
          columns={[
            { title: '股票', dataIndex: 'stock_code' },
            {
              title: '方向',
              dataIndex: 'side',
              render: (side: string) => (side === 'buy' ? '买入' : '卖出'),
            },
            { title: '建议数量', dataIndex: 'quantity' },
            {
              title: '参考价',
              dataIndex: 'reference_price',
              render: (price: number) => price.toFixed(2),
            },
            {
              title: '数量依据',
              dataIndex: 'sizing_reasons',
              render: (reasons: string[]) => reasons.join('、'),
            },
            {
              title: '委托',
              key: 'propose',
              render: (_, order) => (
                <Button
                  size="small"
                  loading={proposing === order.stock_code}
                  disabled={
                    busy || proposing !== null || proposed.includes(order.stock_code)
                  }
                  onClick={() => void propose(order)}
                >
                  {proposed.includes(order.stock_code)
                    ? '已提议，待审批'
                    : '提议开盘委托'}
                </Button>
              ),
            },
          ]}
        />
      ) : null}
    </section>
  )
}
