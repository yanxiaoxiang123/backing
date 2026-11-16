import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ResearchChatInput } from './ResearchChatInput'
import { isChatSubmitting, readChatDraft } from '../../utils/chatDrafts'

describe('ResearchChatInput environment recovery', () => {
  beforeEach(() => sessionStorage.clear())
  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('supports editing, rejection and accepted retry without randomUUID', async () => {
    vi.stubGlobal('crypto', {})
    let accepted = false
    render(
      <ResearchChatInput
        threadId="http"
        running={false}
        onSend={async () => ({ accepted, threadId: 'http' })}
        onStop={() => {}}
      />,
    )
    const input = screen.getByLabelText('聊天输入')
    fireEvent.change(input, { target: { value: '普通 HTTP 下的研究问题' } })
    expect(input).toHaveValue('普通 HTTP 下的研究问题')
    await act(async () =>
      fireEvent.click(screen.getByRole('button', { name: '发送消息' })),
    )
    expect(input).toHaveValue('普通 HTTP 下的研究问题')
    expect(isChatSubmitting('thread:http')).toBe(false)
    accepted = true
    await act(async () =>
      fireEvent.click(screen.getByRole('button', { name: '发送消息' })),
    )
    expect(input).toHaveValue('')
    expect(readChatDraft('thread:http')?.value).toBe('')
  })

  it('releases the submission token when acquiring a snapshot throws', async () => {
    render(
      <ResearchChatInput
        threadId="snapshot-error"
        running={false}
        onSend={async () => ({ accepted: true, threadId: 'snapshot-error' })}
        onStop={() => {}}
      />,
    )
    const input = screen.getByLabelText('聊天输入')
    fireEvent.change(input, { target: { value: '等待重试的问题' } })
    sessionStorage.removeItem('backing.chat-draft:thread:snapshot-error')
    vi.spyOn(crypto, 'randomUUID').mockImplementation(() => {
      throw new Error('snapshot failure')
    })
    await act(async () =>
      fireEvent.click(screen.getByRole('button', { name: '发送消息' })),
    )
    expect(screen.getByRole('alert')).toHaveTextContent('输入已保留')
    expect(isChatSubmitting('thread:snapshot-error')).toBe(false)
    vi.restoreAllMocks()
    fireEvent.change(input, { target: { value: '重新输入后可重试' } })
    expect(screen.getByRole('button', { name: '发送消息' })).toBeEnabled()
    await act(async () =>
      fireEvent.click(screen.getByRole('button', { name: '发送消息' })),
    )
    expect(input).toHaveValue('')
  })
})
