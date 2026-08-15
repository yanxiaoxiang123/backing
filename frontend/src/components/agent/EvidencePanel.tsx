import { Empty, Tag, Typography } from 'antd'
import type { Claim } from '../../types/agent'

const categoryText: Record<string, string> = {
  technical: '技术面',
  fundamental: '基本面',
  news: '新闻/政策',
  policy: '政策',
  capital_flow: '资金面',
  other: '其他',
}

const directionColor: Record<string, string> = {
  bullish: 'red',
  bearish: 'green',
  neutral: 'default',
}

export function EvidencePanel({ claims }: { claims: Claim[] }) {
  if (!claims || claims.length === 0) {
    return <Empty description="暂无证据条目" />
  }
  return (
    <div className="agent-evidence-list">
      {claims.map((claim, index) => (
        <div key={index} className="agent-evidence-item">
          <div className="agent-evidence-head">
            <Tag color={categoryText[claim.category] ? 'blue' : 'default'}>
              {categoryText[claim.category] ?? claim.category}
            </Tag>
            {claim.direction && (
              <Tag color={directionColor[claim.direction]}>{claim.direction}</Tag>
            )}
            <Tag color={claim.hypothesis ? 'orange' : 'green'}>
              {claim.hypothesis ? '假设（无证据）' : '有证据'}
            </Tag>
            <span className="agent-evidence-confidence">
              置信度 {Math.round(claim.confidence * 100)}%
            </span>
          </div>
          <Typography.Paragraph className="agent-evidence-claim">
            {claim.claim}
          </Typography.Paragraph>
          {claim.evidence.map((item, i) => (
            <div key={i} className="agent-evidence-source">
              <Tag>{item.vendor}</Tag>
              <span>{item.source_id}</span>
              <span className="agent-evidence-asof">{item.as_of}</span>
              <div className="agent-evidence-summary">{item.summary}</div>
            </div>
          ))}
        </div>
      ))}
    </div>
  )
}
