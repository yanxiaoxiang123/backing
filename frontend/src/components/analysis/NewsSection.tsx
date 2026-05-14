import { Card } from 'antd'
import type { AgentNewsItem } from '../../../types'

interface NewsSectionProps {
  newsItems?: AgentNewsItem[]
}

export function NewsSection({ newsItems }: NewsSectionProps) {
  if (!newsItems || newsItems.length === 0) {
    return null
  }

  return (
    <Card style={{ marginTop: 16 }}>
      <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>相关新闻</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {newsItems.map((item, index) => (
          <div
            key={`${item.url}-${index}`}
            style={{
              padding: 12,
              borderRadius: 8,
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
                marginBottom: 6
              }}
            >
              {item.title || `新闻 ${index + 1}`}
            </a>
            <div style={{ fontSize: 13, color: 'var(--color-text-secondary)', lineHeight: 1.6, marginBottom: 8 }}>
              {item.content || '暂无摘要'}
            </div>
            <div style={{ fontSize: 12, color: 'var(--color-text-tertiary)' }}>
              来源: {item.url}
              {typeof item.score === 'number' ? ` | 相关度: ${item.score.toFixed(2)}` : ''}
            </div>
          </div>
        ))}
      </div>
    </Card>
  )
}