import { act, render } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { StreamingMarkdown } from '../StreamingMarkdown'

afterEach(() => {
  vi.useRealTimers()
})

describe('StreamingMarkdown', () => {
  it('历史回复直接显示，不重播显现动画，并保护中文段落末尾', () => {
    const { container } = render(
      <StreamingMarkdown
        content="先确认研究口径，然后核对成交量。"
        streaming={false}
      />,
    )
    expect(container.querySelectorAll('.chat-reveal-glyph')).toHaveLength(0)
    expect(container.querySelector('.chat-nowrap-tail')?.textContent).toBe('交量。')
    expect(container.textContent).toBe('先确认研究口径，然后核对成交量。')
  })

  it('相邻字交叠显现，追加文本不会让前面的字重新开始', () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'performance'] })
    const { container, rerender } = render(<StreamingMarkdown content="" streaming />)
    rerender(<StreamingMarkdown content="银行估值" streaming />)
    const first = container.querySelector<HTMLElement>('.chat-reveal-glyph')!
    const second = container.querySelectorAll<HTMLElement>('.chat-reveal-glyph')[1]
    expect(
      parseFloat(second.style.animationDelay) - parseFloat(first.style.animationDelay),
    ).toBe(20)
    act(() => {
      vi.advanceTimersByTime(40)
    })
    rerender(<StreamingMarkdown content="银行估值分析" streaming />)
    expect(
      parseFloat(
        container.querySelector<HTMLElement>('.chat-reveal-glyph')!.style
          .animationDelay,
      ),
    ).toBe(-40)
    act(() => {
      vi.advanceTimersByTime(600)
    })
    expect(container.querySelectorAll('.chat-reveal-glyph')).toHaveLength(0)
    expect(container.textContent).toBe('银行估值分析')
  })

  it('最终事件与最后一段文本同时到达时，保留最后一段的显现', () => {
    const { container, rerender } = render(<StreamingMarkdown content="" streaming />)
    rerender(<StreamingMarkdown content="研究结论" streaming={false} />)
    expect(container.querySelectorAll('.chat-reveal-glyph')).toHaveLength(4)
  })

  it('保留 Markdown、链接和代码语义，代码不做逐字动画', () => {
    const { container, rerender } = render(<StreamingMarkdown content="" streaming />)
    rerender(
      <StreamingMarkdown
        content={
          '**银行股** [研究文档](https://example.com)\n\n```python\nprint(123)\n```'
        }
        streaming
      />,
    )
    expect(container.querySelector('strong')?.textContent).toBe('银行股')
    expect(container.querySelector('a')?.getAttribute('href')).toBe(
      'https://example.com',
    )
    expect(container.querySelector('code')?.textContent).toBe('print(123)\n')
    expect(container.querySelector('code .chat-reveal-glyph')).toBeNull()
    expect(container.querySelector('script')).toBeNull()
  })

  it('大批文本限制排队延迟，完整保留英文单词与 emoji 字素', () => {
    const { container, rerender } = render(<StreamingMarkdown content="" streaming />)
    rerender(
      <StreamingMarkdown content={'DeepSeek 👨‍👩‍👧 ' + '银行股'.repeat(100)} streaming />,
    )
    const letters = Array.from(
      container.querySelectorAll<HTMLElement>('.chat-reveal-glyph'),
    )
    expect(letters.some((letter) => letter.textContent === '👨‍👩‍👧')).toBe(true)
    expect(container.querySelector('.chat-nowrap-word')?.textContent).toBe('DeepSeek')
    expect(
      Math.max(...letters.map((letter) => parseFloat(letter.style.animationDelay))),
    ).toBeLessThan(250)
  })
})
