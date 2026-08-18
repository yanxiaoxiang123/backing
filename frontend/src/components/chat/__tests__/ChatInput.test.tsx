import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { fireEvent } from '@testing-library/react'
import { ChatInput } from '../ChatInput'

describe('ChatInput', () => {
  it('Enter 发送并清空输入框', async () => {
    const user = userEvent.setup()
    const onSend = vi.fn()
    render(<ChatInput running={false} onSend={onSend} onStop={vi.fn()} />)
    const textarea = screen.getByLabelText('聊天输入')
    await user.type(textarea, '分析 sh.600000')
    fireEvent.keyDown(textarea, { key: 'Enter' })
    expect(onSend).toHaveBeenCalledWith('分析 sh.600000')
    expect((textarea as HTMLTextAreaElement).value).toBe('')
  })

  it('Shift+Enter 换行不发送', async () => {
    const user = userEvent.setup()
    const onSend = vi.fn()
    render(<ChatInput running={false} onSend={onSend} onStop={vi.fn()} />)
    const textarea = screen.getByLabelText('聊天输入')
    await user.type(textarea, '第一行')
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: true })
    expect(onSend).not.toHaveBeenCalled()
    expect((textarea as HTMLTextAreaElement).value).toContain('第一行')
  })

  it('空内容发送按钮禁用', () => {
    render(<ChatInput running={false} onSend={vi.fn()} onStop={vi.fn()} />)
    expect(screen.getByRole('button', { name: /发送/ })).toBeDisabled()
  })

  it('running 时显示停止按钮并禁用输入', async () => {
    const user = userEvent.setup()
    const onStop = vi.fn()
    render(<ChatInput running onSend={vi.fn()} onStop={onStop} />)
    const textarea = screen.getByLabelText('聊天输入') as HTMLTextAreaElement
    expect(textarea.disabled).toBe(true)
    await user.click(screen.getByRole('button', { name: /停止/ }))
    expect(onStop).toHaveBeenCalled()
  })
})
