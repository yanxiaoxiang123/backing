import { act, fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { ChatInput } from './ChatInput'

function pending<T>() {
  let resolve!: (value: T) => void
  let reject!: (error: Error) => void
  const promise = new Promise<T>((yes, no) => {
    resolve = yes
    reject = no
  })
  return { promise, resolve, reject }
}

describe('ChatInput submission', () => {
  it('keeps the text until acceptance and blocks rapid repeated submits', async () => {
    const request = pending<boolean>()
    const send = vi.fn(() => request.promise)
    render(<ChatInput running={false} onSend={send} onStop={() => {}} />)
    const input = screen.getByRole('textbox')
    fireEvent.change(input, { target: { value: '核对数据覆盖' } })
    fireEvent.keyDown(input, { key: 'Enter' })
    fireEvent.keyDown(input, { key: 'Enter' })
    expect(input).toHaveValue('核对数据覆盖')
    expect(input).toBeDisabled()
    expect(send).toHaveBeenCalledTimes(1)
    await act(async () => request.resolve(true))
    expect(input).toHaveValue('')
    expect(input).toBeEnabled()
  })

  it.each(['false', 'reject'])(
    'retains text after %s and permits retry',
    async (kind) => {
      const request = pending<boolean>()
      render(
        <ChatInput running={false} onSend={() => request.promise} onStop={() => {}} />,
      )
      const input = screen.getByRole('textbox')
      fireEvent.change(input, { target: { value: '请保留我的问题' } })
      fireEvent.click(screen.getByRole('button', { name: '发送消息' }))
      await act(async () => {
        if (kind === 'false') request.resolve(false)
        else request.reject(new Error('network failed'))
      })
      expect(input).toHaveValue('请保留我的问题')
      expect(screen.getByRole('button', { name: '发送消息' })).toBeEnabled()
    },
  )

  it('does not send Enter during IME composition or Shift+Enter', () => {
    const send = vi.fn()
    render(<ChatInput running={false} onSend={send} onStop={() => {}} />)
    const input = screen.getByRole('textbox')
    fireEvent.change(input, { target: { value: '研究问题' } })
    fireEvent.keyDown(input, { key: 'Enter', isComposing: true })
    fireEvent.keyDown(input, { key: 'Enter', shiftKey: true })
    expect(send).not.toHaveBeenCalled()
    expect(input).toHaveValue('研究问题')
  })

  it('leaves controlled edits intact when presets arrive later', () => {
    const props = {
      running: false,
      onSend: vi.fn(),
      onStop: vi.fn(),
      onChange: vi.fn(),
    }
    const { rerender } = render(<ChatInput {...props} value="我的草稿" />)
    rerender(
      <ChatInput {...props} value="我的草稿" initialValue="分析一下 sh.600000" />,
    )
    expect(screen.getByRole('textbox')).toHaveValue('我的草稿')
    fireEvent.change(screen.getByRole('textbox'), { target: { value: '' } })
    expect(props.onChange).toHaveBeenCalledWith('')
  })
})
