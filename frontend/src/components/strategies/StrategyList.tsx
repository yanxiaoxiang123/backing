import { Card, Empty } from 'antd'
import { LineChartOutlined } from '@ant-design/icons'
import type { StrategyInfo } from '../../types'
import { STRATEGY_METADATA } from '../../constants/strategy'

interface StrategyListProps {
  strategies: StrategyInfo[]
  selectedStrategy: string | null
  loading: boolean
  onSelect: (name: string) => void
}

export function StrategyList({ strategies, selectedStrategy, loading, onSelect }: StrategyListProps) {
  return (
    <Card
      title={<><LineChartOutlined style={{ marginRight: 8 }} />策略列表</>}
      loading={loading}
      style={{ position: 'sticky', top: 80 }}
      bodyStyle={{ padding: 'var(--space-sm)', maxHeight: 'calc(100vh - 180px)', overflowY: 'auto' }}
    >
      {strategies.length === 0 && !loading ? (
        <Empty description="暂无策略" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      ) : (
        strategies.map(strategy => {
          const meta = STRATEGY_METADATA[strategy.name] || { name: strategy.name, description: strategy.description, color: '#86868b' }
          const isSelected = selectedStrategy === strategy.name

          return (
            <div
              key={strategy.name}
              onClick={() => onSelect(strategy.name)}
              style={{
                padding: 'var(--space-md)',
                marginBottom: 'var(--space-sm)',
                borderRadius: 'var(--radius-md)',
                cursor: 'pointer',
                border: `2px solid ${isSelected ? meta.color : 'transparent'}`,
                background: isSelected ? `${meta.color}10` : 'var(--color-bg-secondary)',
                transition: 'all var(--transition-fast)'
              }}
            >
              <div style={{
                fontWeight: 600,
                fontSize: 'var(--font-size-sm)',
                color: isSelected ? meta.color : 'var(--color-text-primary)',
                marginBottom: 'var(--space-xs)'
              }}>
                {meta.name}
              </div>
              <div style={{
                fontSize: 'var(--font-size-xs)',
                color: 'var(--color-text-secondary)',
                lineHeight: 1.4
              }}>
                {meta.description}
              </div>
            </div>
          )
        })
      )}
    </Card>
  )
}