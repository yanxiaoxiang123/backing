import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => {
  const instances: Array<{
    threadId: string
    start: ReturnType<typeof vi.fn>
    stop: ReturnType<typeof vi.fn>
    emit: (event: unknown) => void
  }> = []
  class MockChatEventStream {
    onEvent?: (event: unknown) => void
    onStateChange?: (state: string, error?: unknown) => void
    start: ReturnType<typeof vi.fn>
    stop: ReturnType<typeof vi.fn>

    constructor(public threadId: string) {
      this.start = vi.fn()
      this.stop = vi.fn()
      instances.push({
        threadId,
        start: this.start,
        stop: this.stop,
        emit: (event) => this.onEvent?.(event),
      })
    }
  }
  return {
    instances,
    ChatEventStream: MockChatEventStream,
    createThread: vi.fn(),
    listThreads: vi.fn().mockResolvedValue({ threads: [], total: 0 }),
    getThread: vi.fn(),
    submitTurn: vi.fn(),
    cancelTurn: vi.fn(),
    archiveThread: vi.fn(),
    getApiErrorMessage: vi.fn((e: unknown) => String(e)),
  }
})

vi.mock('../services/agentChats', () => ({
  ChatEventStream: mocks.ChatEventStream,
  createThread: mocks.createThread,
  listThreads: mocks.listThreads,
  getThread: mocks.getThread,
  submitTurn: mocks.submitTurn,
  cancelTurn: mocks.cancelTurn,
  archiveThread: mocks.archiveThread,
}))

vi.mock('../services/api', () => ({
  getApiErrorMessage: mocks.getApiErrorMessage,
}))

import { useAgentChat } from './useAgentChat'

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
  }
}

function turn(id: number, threadId: string, overrides: Record<string, unknown> = {}) {
  return {
    id,
    thread_id: threadId,
    content: '分析 sh.600000',
    status: 'queued',
    final_reply: null,
    end_reason: null,
    error: null,
    created_at: '2026-08-18T00:00:00',
    ...overrides,
  }
}

describe('useAgentChat', () => {
  beforeEach(() => {
    mocks.instances.length = 0
    mocks.listThreads.mockResolvedValue({ threads: [], total: 0 })
    mocks.getThread.mockReset()
    mocks.createThread.mockReset()
    mocks.submitTurn.mockReset()
    mocks.cancelTurn.mockReset()
    mocks.archiveThread.mockReset()
    window.history.replaceState({}, '', '/workspace')
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('newThread 创建并选择新会话，URL 持久化 thread_id', async () => {
    mocks.createThread.mockResolvedValue(thread('t-new', { title: '' }))
    mocks.getThread.mockResolvedValue({
      thread: thread('t-new', { title: '' }),
      turns: [],
    })
    const { result } = renderHook(() => useAgentChat())
    let id = ''
    await act(async () => {
      id = await result.current.newThread()
    })
    expect(id).toBe('t-new')
    expect(result.current.currentThread?.thread_id).toBe('t-new')
    expect(window.location.search).toContain('thread_id=t-new')
    expect(mocks.instances).toHaveLength(1)
    expect(mocks.instances[0].start).toHaveBeenCalledWith(0)
  })

  it('send 提交 turn（带 Idempotency-Key）并生成首条消息，标题取前 36 字符', async () => {
    mocks.createThread.mockResolvedValue(thread('t-1', { title: '' }))
    mocks.getThread.mockResolvedValue({
      thread: thread('t-1', { title: '' }),
      turns: [],
    })
    mocks.submitTurn.mockImplementation(
      (_tid: string, content: string) =>
        Promise.resolve(turn(1, 't-1', { status: 'queued', content })),
    )
    const content = '帮我分析 sh.600000 并回测 ma_cross'
    const { result } = renderHook(() => useAgentChat())
    await act(async () => {
      await result.current.newThread()
    })
    await act(async () => {
      await result.current.send(content)
    })

    expect(mocks.submitTurn).toHaveBeenCalledTimes(1)
    const args = mocks.submitTurn.mock.calls[0]
    expect(args[0]).toBe('t-1')
    expect(args[1]).toBe(content)
    expect(String(args[2]).length).toBeGreaterThan(0) // idempotency key
    expect(result.current.currentThread?.title).toBe(content.slice(0, 36))
    expect(result.current.messages).toHaveLength(2)
    expect(result.current.messages[0]).toMatchObject({ role: 'user', content })
  })

  it('SSE 事件合并进消息并触发 onRunLinked 回调', async () => {
    mocks.createThread.mockResolvedValue(thread('t-1', { title: 'x' }))
    mocks.getThread.mockResolvedValue({
      thread: thread('t-1', { title: 'x' }),
      turns: [],
    })
    mocks.submitTurn.mockResolvedValue(turn(1, 't-1', { status: 'running' }))
    const onRunLinked = vi.fn()
    const { result } = renderHook(() => useAgentChat({ onRunLinked }))
    await act(async () => {
      await result.current.newThread()
    })
    await act(async () => {
      await result.current.send('分析')
    })

    const stream = mocks.instances[0]
    act(() => {
      stream.emit({
        seq: 1,
        type: 'reasoning',
        turn_id: 1,
        payload: { content: '思考中…' },
      })
      stream.emit({
        seq: 2,
        type: 'assistant_chunk',
        turn_id: 1,
        payload: { content: '正在' },
      })
      stream.emit({
        seq: 3,
        type: 'assistant_chunk',
        turn_id: 1,
        payload: { content: '分析' },
      })
      stream.emit({
        seq: 4,
        type: 'tool_call',
        turn_id: 1,
        payload: { tool: 'quant_run_analysis' },
      })
      stream.emit({
        seq: 5,
        type: 'tool_result',
        turn_id: 1,
        payload: {
          tool: 'quant_run_analysis',
          summary: 'run 创建',
          run_id: 'run-77',
        },
      })
      stream.emit({
        seq: 6,
        type: 'run.linked',
        turn_id: 1,
        payload: { run_id: 'run-77' },
      })
      stream.emit({
        seq: 7,
        type: 'turn.done',
        turn_id: 1,
        payload: { status: 'completed', final_reply: '结论' },
      })
    })

    const assistant = result.current.messages.find((m) => m.role === 'assistant')
    expect(assistant?.content).toBe('正在分析')
    expect(assistant?.reasoning).toBe('思考中…')
    expect(assistant?.tools).toEqual([
      { tool: 'quant_run_analysis', summary: 'run 创建', runId: 'run-77' },
    ])
    expect(assistant?.runId).toBe('run-77')
    expect(assistant?.status).toBe('completed')
    expect(onRunLinked).toHaveBeenCalledWith('run-77')
  })

  it('stop 调用 cancel 并更新 turn 状态为 cancelled', async () => {
    mocks.getThread.mockResolvedValue({
      thread: thread('t-1', { title: 'x' }),
      turns: [turn(1, 't-1', { status: 'running' })],
    })
    mocks.cancelTurn.mockResolvedValue(
      turn(1, 't-1', { status: 'cancelled', end_reason: 'user_cancelled' }),
    )
    const { result } = renderHook(() => useAgentChat())
    await act(async () => {
      await result.current.selectThread('t-1')
    })
    await act(async () => {
      await result.current.stop()
    })
    expect(mocks.cancelTurn).toHaveBeenCalledWith('t-1')
    const assistant = result.current.messages.find((m) => m.role === 'assistant')
    expect(assistant?.status).toBe('cancelled')
  })

  it('archive 归档并从列表移除会话；归档当前会话时清空', async () => {
    mocks.getThread.mockResolvedValue({
      thread: thread('t-1', { title: 'x' }),
      turns: [],
    })
    mocks.archiveThread.mockResolvedValue(thread('t-1', { archived: true }))
    mocks.listThreads.mockResolvedValue({
      threads: [thread('t-2', { title: '另一会话' })],
      total: 1,
    })
    const { result } = renderHook(() => useAgentChat())
    await act(async () => {
      await result.current.selectThread('t-1')
    })
    await act(async () => {
      await result.current.archive('t-1')
    })
    expect(mocks.archiveThread).toHaveBeenCalledWith('t-1')
    expect(result.current.currentThread).toBeNull()
    expect(result.current.threads.map((t) => t.thread_id)).toEqual(['t-2'])
  })

  it('URL 中的 thread_id 恢复会话', async () => {
    window.history.replaceState({}, '', '/workspace?thread_id=t-9')
    mocks.getThread.mockResolvedValue({
      thread: thread('t-9'),
      turns: [],
    })
    const { result } = renderHook(() => useAgentChat())
    await act(async () => {})
    expect(mocks.getThread).toHaveBeenCalledWith('t-9')
    expect(result.current.currentThread?.thread_id).toBe('t-9')
  })
})
