import { fireEvent, render, screen } from '@testing-library/react'
import { BrowserRouter, useLocation } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ResearchCopilot } from './ResearchCopilot'

vi.mock('../../services/agentChats', () => ({
  getThread: vi.fn(() => new Promise(() => {})),
  listThreads: vi.fn().mockResolvedValue({ threads: [], total: 0 }),
  getChatStatus: vi.fn().mockResolvedValue({
    backend: 'fake',
    available: true,
    reason: null,
  }),
  createThread: vi.fn(),
  submitTurn: vi.fn(),
  cancelTurn: vi.fn(),
  archiveThread: vi.fn(),
  ChatEventStream: vi.fn(),
}))

function LocationProbe() {
  const location = useLocation()
  return (
    <output aria-label="current route">{location.pathname + location.search}</output>
  )
}

describe('ResearchCopilot workspace handoff', () => {
  beforeEach(() => {
    sessionStorage.clear()
    window.history.replaceState({}, '', '/strategies?thread_id=bank&stock=sh.600000')
  })

  afterEach(() => window.history.replaceState({}, '', '/'))

  it('keeps the restoring conversation identity when opening the workspace', () => {
    render(
      <BrowserRouter>
        <ResearchCopilot
          open
          context={{
            route: '/strategies',
            entity_type: 'stock',
            entity_id: 'sh.600000',
          }}
        />
        <LocationProbe />
      </BrowserRouter>,
    )
    fireEvent.change(screen.getByLabelText('聊天输入'), {
      target: { value: '等会话加载后继续的问题' },
    })
    expect(screen.getByRole('button', { name: '发送消息' })).toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: '打开完整工作台' }))
    expect(screen.getByLabelText('current route')).toHaveTextContent(
      '/workspace?thread_id=bank&stock=sh.600000',
    )
    expect(
      JSON.parse(sessionStorage.getItem('backing.chat-draft:thread:bank') ?? 'null'),
    ).toMatchObject({ value: '等会话加载后继续的问题' })
  })
})
