import { Card, Tag } from 'antd'
import type { AgentAnalyzeResponse } from '../../types'
import { Prose } from '../Prose'
import {
  formatNumber,
  formatPercent,
  isFiniteNumber,
  tradeAction,
} from '../../utils/dataFormat'

export function DecisionCard({ result }: { result: AgentAnalyzeResponse }) {
  const signal =
    result.final_signal === 'hold'
      ? { label: '持有', className: 'price-flat' }
      : tradeAction(result.final_signal)
  return (
    <Card style={{ marginBottom: 'var(--space-lg)' }}>
      <section className="analysis-decision" aria-label="分析结论">
        <div className="analysis-decision-heading">
          <Prose as="h2" className={signal.className}>
            {signal.label}
          </Prose>
          <Tag>{result.mode}</Tag>
        </div>
        <div className="analysis-decision-meta">
          <span>
            {result.stock_name || result.stock_code} · {result.stock_code}
          </span>
          <span>
            置信度{' '}
            {formatPercent(
              isFiniteNumber(result.final_confidence)
                ? result.final_confidence * 100
                : null,
              0,
            )}
          </span>
          <span>耗时 {formatNumber(result.duration_s, 1)} 秒</span>
        </div>
        {result.final_reason && (
          <div className="analysis-decision-reason">
            <Prose as="p">{result.final_reason}</Prose>
          </div>
        )}
        <Prose as="p" className="research-data-context">
          结论依据见下方分析阶段与情报来源；置信度为模型输出，仅供研究参考。
        </Prose>
      </section>
    </Card>
  )
}
