import { Card, Tag, Row, Col, Empty } from 'antd'
import type { AgentStage } from '../../types'

interface StageCardProps {
  stage: AgentStage
  index: number
}

const stageLabels: Record<string, string> = {
  technical_analysis: '技术分析',
  intel: '情报分析',
  risk: '风险评估',
  strategy: '策略评估',
  decision: '决策',
}

function getSignalColor(signal: string) {
  switch (signal) {
    case 'buy': return 'green'
    case 'sell': return 'red'
    default: return 'default'
  }
}

function getSignalLabel(signal: string) {
  switch (signal) {
    case 'buy': return '买入'
    case 'sell': return '卖出'
    default: return '持有'
  }
}

export function StageCard({ stage }: StageCardProps) {
  const label = stageLabels[stage.stage_name] || stage.stage_name

  return (
    <Card
      size="small"
      title={label}
      extra={
        <Tag color={stage.status === 'completed' ? 'green' : stage.status === 'failed' ? 'red' : 'orange'}>
          {stage.status === 'completed' ? '完成' : stage.status === 'failed' ? '失败' : '进行中'}
        </Tag>
      }
      style={{ marginBottom: 8 }}
    >
      {stage.opinion ? (
        <Row gutter={16}>
          <Col span={4}>
            <Tag color={getSignalColor(stage.opinion.signal)} style={{ fontSize: 14 }}>
              {getSignalLabel(stage.opinion.signal)}
            </Tag>
            <div style={{ fontSize: 12, color: 'var(--color-text-secondary)', marginTop: 4 }}>
              置信度: {Math.round(stage.opinion.confidence * 100)}%
            </div>
          </Col>
          <Col span={20}>
            <div style={{ fontSize: 13 }}>{stage.opinion.reason || '无'}</div>
          </Col>
        </Row>
      ) : stage.error ? (
        <div style={{ color: 'var(--color-danger)' }}>{stage.error}</div>
      ) : (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} />
      )}
    </Card>
  )
}