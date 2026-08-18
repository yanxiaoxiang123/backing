import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ChatSidebar } from '../ChatSidebar'
import type { ChatThread } from '../../../types/chat'

function thread(threadId: string, overrides: Record<string, unknown> = {}) {
  return {
    thread_id: threadId,
    title: '会话',
    status: 'active',
    last_run_id: null,
    archived: false,
    created_at: '2026-08-18T00:00:00',
    updated_at: '2026-08-18T00:00:00',
    ...overrides,
  } as ChatThread
}

describe('ChatSidebar', () => {
  it('渲染会话列表并点击选择', async () => {
    const user = userEvent.setup()
    const onSelect = vi.fn()
    render(
      <ChatSidebar
        threads={[thread('t-1', { title: '第一会话' }), thread('t-2', { title: '第二会话' })]}
        currentThreadId="t-1"
        onSelect={onSelect}
        onNew={vi.fn()}
        onArchive={vi.fn()}
      />,
    )
    expect(screen.getByText('第一会话')).toBeInTheDocument()
    await user.click(screen.getByText('第二会话'))
    expect(onSelect).toHaveBeenCalledWith('t-2')
  })

  it('新对话按钮触发 onNew', async () => {
    const user = userEvent.setup()
    const onNew = vi.fn()
    render(
      <ChatSidebar
        threads={[]}
        currentThreadId={null}
        onSelect={vi.fn()}
        onNew={onNew}
        onArchive={vi.fn()}
      />,
    )
    await user.click(screen.getByRole('button', { name: /新对话/ }))
    expect(onNew).toHaveBeenCalled()
  })

  it('归档按钮触发 onArchive 且不触发选择', async () => {
    const user = userEvent.setup()
    const onSelect = vi.fn()
    const onArchive = vi.fn()
    render(
      <ChatSidebar
        threads={[thread('t-1', { title: '第一会话' })]}
        currentThreadId={null}
        onSelect={onSelect}
        onNew={vi.fn()}
        onArchive={onArchive}
      />,
    )
    await user.click(screen.getByRole('button', { name: /归档 第一会话/ }))
    expect(onArchive).toHaveBeenCalledWith('t-1')
    expect(onSelect).not.toHaveBeenCalled()
  })

  it('运行中的会话显示状态点', () => {
    render(
      <ChatSidebar
        threads={[thread('t-1', { status: 'running' })]}
        currentThreadId={null}
        onSelect={vi.fn()}
        onNew={vi.fn()}
        onArchive={vi.fn()}
      />,
    )
    expect(screen.getByLabelText('运行中')).toBeInTheDocument()
  })
})
