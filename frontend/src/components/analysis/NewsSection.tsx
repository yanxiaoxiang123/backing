import { Card } from 'antd'
import type { AgentNewsItem } from '../../types'

interface NewsSectionProps {
  newsItems?: AgentNewsItem[]
}

export function NewsSection({ newsItems }: NewsSectionProps) {
  if (!newsItems || newsItems.length === 0) {
    return null
  }

  return (
    <Card style={{ marginTop: 'var(--space-lg)' }}
      styles={{ body: { padding: 'var(--space-lg)' } }}
    >
      <div style={{ fontSize: 'var(--font-size-md)', fontWeight: 600, marginBottom: 'var(--space-lg)' }}>相关新闻</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-lg)' }}>
        {newsItems.map((item, index) => (
          <div
            key={`${item.url}-${index}`}
            style={{
              padding: 'var(--space-lg)',
              borderRadius: 'var(--radius-btn)',
              background: 'var(--color-bg-secondary)',
              border: '1px solid var(--color-border)'
            }}
          >
            <a
              href={item.url}
              target="_blank"
              rel="noreferrer"
              style={{
                display: 'block',
                fontWeight: 600,
                color: 'var(--color-accent)',
                marginBottom: 'var(--space-sm)'
              }}
            >
              {item.title || `新闻 ${index + 1}`}
            </a>
            <div style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-secondary)', lineHeight: 1.8, marginBottom: 'var(--space-md)' }}>
              {item.content || '暂无摘要'}
            </div>
            <div style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-tertiary)' }}>
              来源: {item.url}
              {typeof item.score === 'number' ? ` | 相关度: ${item.score.toFixed(2)}` : ''}
            </div>
          </div>
        ))}
      </div>
    </Card>
  )
}