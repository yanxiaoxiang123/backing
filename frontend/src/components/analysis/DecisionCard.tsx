import { Card, Tag, Row, Col } from 'antd'
import type { AgentAnalyzeResponse } from '../../types'

interface DecisionCardProps {
  result: AgentAnalyzeResponse
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

export function DecisionCard({ result }: DecisionCardProps) {
  const signalColor = result.final_signal === 'buy' ? 'var(--color-success)' :
                      result.final_signal === 'sell' ? 'var(--color-danger)' :
                      'var(--color-text-secondary)'

  return (
    <Card style={{ marginBottom: 16 }}>
      <Row gutter={16} align="middle">
        <Col>
          <div style={{
            fontSize: 48,
            fontWeight: 700,
            color: signalColor
          }}>
            {result.final_signal === 'buy' ? '↑' : result.final_signal === 'sell' ? '↓' : '→'}
          </div>
        </Col>
        <Col flex="auto">
          <div style={{ fontSize: 24, fontWeight: 600, marginBottom: 4 }}>
            {getSignalLabel(result.final_signal)}
          </div>
          <div style={{ color: 'var(--color-text-secondary)' }}>
            置信度: {Math.round(result.final_confidence * 100)}% | 耗时: {result.duration_s.toFixed(1)}s
          </div>
        </Col>
        <Col>
          <Tag color={getSignalColor(result.final_signal)} style={{ fontSize: 16, padding: '4px 12px' }}>
            {result.mode}
          </Tag>
        </Col>
      </Row>
      {result.final_reason && (
        <div style={{ marginTop: 16, padding: 12, background: 'var(--color-bg-secondary)', borderRadius: 8 }}>
          {result.final_reason}
        </div>
      )}
    </Card>
  )
}