import { useMemo, useState } from 'react'
import { Alert, Button, Card, Empty, Input } from 'antd'
import { LineChartOutlined, SearchOutlined } from '@ant-design/icons'
import type { StrategyInfo } from '../../types'
import { STRATEGY_METADATA, STRATEGY_CATEGORIES } from '../../constants/strategy'

interface StrategyListProps {
  strategies: StrategyInfo[]
  selectedStrategy: string | null
  loading: boolean
  onSelect: (name: string) => void
  error?: unknown
  onRetry?: () => void
}

export function StrategyList({
  strategies,
  selectedStrategy,
  loading,
  onSelect,
  error,
  onRetry,
}: StrategyListProps) {
  const [query, setQuery] = useState('')

  const groups = useMemo(() => {
    const q = query.trim().toLowerCase()
    const filtered = strategies.filter((s) => {
      if (!q) return true
      const meta = STRATEGY_METADATA[s.name]
      const haystack =
        `${meta?.name ?? ''} ${meta?.description ?? ''} ${s.name} ${s.description}`.toLowerCase()
      return haystack.includes(q)
    })
    return STRATEGY_CATEGORIES.map((category) => ({
      ...category,
      items: filtered.filter(
        (s) => (STRATEGY_METADATA[s.name]?.category ?? 'trend') === category.key,
      ),
    })).filter((g) => g.items.length > 0)
  }, [strategies, query])

  return (
    <Card
      className="strategy-list-panel"
      title={
        <>
          <LineChartOutlined style={{ marginRight: 8 }} />
          策略列表
        </>
      }
      loading={loading}
      styles={{
        body: {
          padding: 'var(--space-sm)',
          maxHeight: 'calc(100vh - 240px)',
          overflowY: 'auto',
        },
      }}
    >
      {error ? (
        <Alert
          type="error"
          showIcon
          message="策略目录加载失败"
          action={
            onRetry ? (
              <Button size="small" onClick={onRetry}>
                重试
              </Button>
            ) : undefined
          }
        />
      ) : null}
      <Input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="搜索策略（名称/说明）"
        allowClear
        prefix={<SearchOutlined style={{ color: 'var(--color-text-tertiary)' }} />}
        style={{ marginBottom: 'var(--space-sm)' }}
        aria-label="搜索策略"
      />
      {groups.length === 0 && !loading ? (
        <Empty description="暂无策略" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      ) : (
        groups.map((group) => (
          <div
            key={group.key}
            className="strategy-group"
            style={{ marginBottom: 'var(--space-sm)' }}
          >
            <div
              className="strategy-group-title"
              style={{
                fontSize: 'var(--font-size-xs)',
                fontWeight: 600,
                letterSpacing: '0.06em',
                textTransform: 'uppercase',
                color: 'var(--color-text-secondary)',
                padding: 'var(--space-xs) var(--space-sm)',
              }}
            >
              {group.label} · {group.items.length}
            </div>
            {group.items.map((strategy) => {
              const meta = STRATEGY_METADATA[strategy.name] || {
                name: strategy.name,
                description: strategy.description,
                color: '#86868b',
                category: 'trend' as const,
              }
              const isSelected = selectedStrategy === strategy.name

              return (
                <button
                  key={strategy.name}
                  type="button"
                  onClick={() => onSelect(strategy.name)}
                  aria-pressed={isSelected}
                  className="strategy-item"
                  style={{
                    display: 'block',
                    width: '100%',
                    textAlign: 'left',
                    font: 'inherit',
                    padding: 'var(--space-md)',
                    marginBottom: 'var(--space-sm)',
                    borderRadius: 'var(--radius-md)',
                    cursor: 'pointer',
                    border: `2px solid ${isSelected ? meta.color : 'transparent'}`,
                    background: isSelected
                      ? `${meta.color}10`
                      : 'var(--color-bg-secondary)',
                    transition: 'all var(--transition-fast)',
                  }}
                >
                  <div
                    style={{
                      fontWeight: 600,
                      fontSize: 'var(--font-size-sm)',
                      color: isSelected ? meta.color : 'var(--color-text-primary)',
                      marginBottom: 'var(--space-xs)',
                    }}
                  >
                    {meta.name}
                  </div>
                  <div
                    style={{
                      fontSize: 'var(--font-size-xs)',
                      color: 'var(--color-text-secondary)',
                      lineHeight: 1.4,
                    }}
                  >
                    {meta.description}
                  </div>
                </button>
              )
            })}
          </div>
        ))
      )}
    </Card>
  )
}
