import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { CopyReplyButton } from '../CopyReplyButton'

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

function clipboard(writeText = vi.fn().mockResolvedValue(undefined)) {
  vi.stubGlobal('navigator', { clipboard: { writeText } })
  return writeText
}

describe('CopyReplyButton', () => {
  it('复制原始 Markdown，成功对勾在 2.5 秒后消失', async () => {
    vi.useFakeTimers()
    const write = clipboard()
    const text = '**银行股**\n\n收益 12.34%，回撤 5.67%。'
    const { container } = render(<CopyReplyButton content={text} />)
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '复制回复' }))
    })
    expect(write).toHaveBeenCalledWith(text)
    expect(screen.getByRole('status')).toHaveTextContent('已复制')
    expect(container.querySelector('.chat-copy-check')).not.toBeNull()
    act(() => {
      vi.advanceTimersByTime(2499)
    })
    expect(container.querySelector('.chat-copy-check')).not.toBeNull()
    act(() => {
      vi.advanceTimersByTime(1)
    })
    expect(container.querySelector('.chat-copy-check')).toBeNull()
    expect(screen.getByRole('status')).toBeEmptyDOMElement()
  })

  it('连续复制重新计时，复制最新文本', async () => {
    vi.useFakeTimers()
    const write = clipboard()
    const { container, rerender } = render(<CopyReplyButton content="第一段" />)
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '复制回复' }))
    })
    act(() => {
      vi.advanceTimersByTime(2000)
    })
    rerender(<CopyReplyButton content="第一段和第二段" />)
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '复制回复' }))
    })
    expect(write).toHaveBeenLastCalledWith('第一段和第二段')
    act(() => {
      vi.advanceTimersByTime(501)
    })
    expect(container.querySelector('.chat-copy-check')).not.toBeNull()
    act(() => {
      vi.advanceTimersByTime(1999)
    })
    expect(container.querySelector('.chat-copy-check')).toBeNull()
  })

  it('权限拒绝显示失败，不误报复制成功', async () => {
    clipboard(vi.fn().mockRejectedValue(new Error('denied')))
    const { container } = render(<CopyReplyButton content="银行股分析" />)
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '复制回复' }))
    })
    expect(screen.getByRole('status')).toHaveTextContent('复制失败，请重试')
    expect(container.querySelector('.chat-copy-check')).toBeNull()
  })

  it('空回复不显示按钮，卸载时清理成功提示计时器', async () => {
    vi.useFakeTimers()
    clipboard()
    const { rerender, unmount } = render(<CopyReplyButton content="" />)
    expect(screen.queryByRole('button')).toBeNull()
    rerender(<CopyReplyButton content="研究内容" />)
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '复制回复' }))
    })
    expect(vi.getTimerCount()).toBe(1)
    unmount()
    expect(vi.getTimerCount()).toBe(0)
  })
})
