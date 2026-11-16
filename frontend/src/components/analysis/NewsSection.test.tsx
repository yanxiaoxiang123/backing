import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { NewsSection } from './NewsSection'

describe('NewsSection', () => {
  it('renders safe http/https links and sanitizes javascript: protocol to #', () => {
    const newsItems = [
      {
        title: '合规新闻',
        url: 'https://finance.example.com/news/1',
        content: '正常市场分析',
        score: 0.95,
      },
      {
        title: '恶意脚本新闻',
        url: 'javascript:alert(document.cookie)',
        content: '恶意测试摘要',
        score: 0.1,
      },
    ]

    render(<NewsSection newsItems={newsItems} />)

    const safeLink = screen.getByRole('link', { name: '合规新闻' })
    expect(safeLink).toHaveAttribute('href', 'https://finance.example.com/news/1')
    expect(safeLink).toHaveAttribute('rel', 'noopener noreferrer')
    expect(safeLink).toHaveAttribute('target', '_blank')

    const maliciousLink = screen.getByRole('link', { name: '恶意脚本新闻' })
    expect(maliciousLink).toHaveAttribute('href', '#')
    expect(maliciousLink).toHaveAttribute('rel', 'noopener noreferrer')
    expect(maliciousLink).toHaveAttribute('target', '_blank')
  })

  it('returns null when newsItems is empty or undefined', () => {
    const { container } = render(<NewsSection newsItems={[]} />)
    expect(container).toBeEmptyDOMElement()
  })
})
