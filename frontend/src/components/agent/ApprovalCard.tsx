import { Button, Card, Descriptions, Tag, message } from 'antd'
import type { ApprovalRequest } from '../../types/agent'

interface ApprovalCardProps {
  approval: ApprovalRequest
  onDecide?: (approval: ApprovalRequest, decision: 'approved' | 'rejected') => void
}

/**
 * 高风险操作审批卡：方向 / 目标仓位 / 风险摘要 / 有效期。
 * 批准后仅进入模拟盘（P3 前为演示组件，不产生真实成交）。
 */
export function ApprovalCard({ approval, onDecide }: ApprovalCardProps) {
  const pending = approval.status === 'pending'

  const decide = (decision: 'approved' | 'rejected') => {
    message.info(
      `审批：${decision === 'approved' ? '批准' : '拒绝'} ${approval.action}`,
    )
    onDecide?.(approval, decision)
  }

  return (
    <Card
      size="small"
      title={
        <span>
          <Tag color="orange">待审批</Tag>
          {approval.action}
        </span>
      }
      className="agent-approval-card"
    >
      <Descriptions size="small" column={1}>
        <Descriptions.Item label="摘要">{approval.summary}</Descriptions.Item>
        <Descriptions.Item label="方向">{approval.direction ?? '—'}</Descriptions.Item>
        <Descriptions.Item label="目标仓位">
          {approval.target_position_pct != null
            ? `${(approval.target_position_pct * 100).toFixed(1)}%`
            : '—'}
        </Descriptions.Item>
        <Descriptions.Item label="风险摘要">
          {approval.risk_summary ?? '—'}
        </Descriptions.Item>
        <Descriptions.Item label="有效期">
          {approval.expires_at ?? '—'}
        </Descriptions.Item>
      </Descriptions>
      {pending && (
        <div className="agent-approval-actions">
          <Button type="primary" danger onClick={() => decide('rejected')}>
            拒绝
          </Button>
          <Button type="primary" onClick={() => decide('approved')}>
            批准（仅模拟盘）
          </Button>
        </div>
      )}
      {!pending && (
        <Tag color={approval.status === 'approved' ? 'green' : 'red'}>
          {approval.status}
        </Tag>
      )}
    </Card>
  )
}
