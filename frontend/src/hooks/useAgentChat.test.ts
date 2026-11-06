import { StrictMode } from 'react'
import { act, renderHook, waitFor } from '@testing-library/react'
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
    getChatStatus: vi
      .fn()
      .mockResolvedValue({ backend: 'fake', available: true, reason: null }),
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
  getChatStatus: mocks.getChatStatus,
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

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => {
    resolve = done
  })
  return { promise, resolve }
}

function selection(seq: number, turnId: number, stockCode: string) {
  return {
    seq,
    type: 'stock.selected',
    turn_id: turnId,
    payload: { stock_code: stockCode },
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
    mocks.getChatStatus.mockResolvedValue({
      backend: 'fake',
      available: true,
      reason: null,
    })
    window.history.replaceState({}, '', '/workspace')
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.useRealTimers()
  })

  it('StrictMode 重复挂载后仍从 URL 恢复会话与消息', async () => {
    window.history.replaceState({}, '', '/workspace?thread_id=t-restored')
    mocks.getThread.mockResolvedValue({
      thread: thread('t-restored'),
      turns: [
        turn(1, 't-restored', { status: 'completed', final_reply: '已保存的研究结论' }),
      ],
    })
    const { result } = renderHook(() => useAgentChat(), { wrapper: StrictMode })
    await waitFor(() => {
      expect(result.current.currentThread?.thread_id).toBe('t-restored')
      expect(
        result.current.messages.some(
          (message) => message.content === '已保存的研究结论',
        ),
      ).toBe(true)
    })
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

  it('send 提交 turn（带 Idempotency-Key），标题采用后端 AI 结果', async () => {
    mocks.createThread.mockResolvedValue(thread('t-1', { title: '' }))
    mocks.getThread.mockResolvedValue({
      thread: thread('t-1', { title: '' }),
      turns: [],
    })
    mocks.submitTurn.mockImplementation((_tid: string, content: string) =>
      Promise.resolve(turn(1, 't-1', { status: 'queued', content })),
    )
    const content = '帮我分析 sh.600000 并回测 ma_cross'
    const { result } = renderHook(() => useAgentChat())
    await act(async () => {
      await result.current.newThread()
    })
    mocks.listThreads.mockResolvedValue({
      threads: [thread('t-1', { title: '浦发银行均线策略回测' })],
      total: 1,
    })
    await act(async () => {
      await result.current.send(content)
    })

    expect(mocks.submitTurn).toHaveBeenCalledTimes(1)
    const args = mocks.submitTurn.mock.calls[0]
    expect(args[0]).toBe('t-1')
    expect(args[1]).toBe(content)
    expect(String(args[2]).length).toBeGreaterThan(0) // idempotency key
    expect(result.current.currentThread?.title).toBe('浦发银行均线策略回测')
    expect(result.current.threads[0]?.title).toBe('浦发银行均线策略回测')
    expect(result.current.messages).toHaveLength(2)
    expect(result.current.messages[0]).toMatchObject({ role: 'user', content })
  })

  it('后台命名完成后同步最近会话与当前标题，并停止轮询', async () => {
    vi.useFakeTimers()
    const pending = thread('t-naming', { title: null, title_pending: true })
    mocks.listThreads.mockResolvedValue({ threads: [pending], total: 1 })
    mocks.getThread.mockResolvedValue({ thread: pending, turns: [] })
    const { result } = renderHook(() => useAgentChat())
    await act(async () => {
      await result.current.selectThread('t-naming')
    })
    const named = thread('t-naming', {
      title: '银行股估值比较',
      title_pending: false,
    })
    mocks.listThreads.mockResolvedValue({ threads: [named], total: 1 })
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000)
    })
    expect(result.current.currentThread?.title).toBe('银行股估值比较')
    expect(result.current.threads[0]?.title).toBe('银行股估值比较')
    const calls = mocks.listThreads.mock.calls.length
    await act(async () => {
      await vi.advanceTimersByTimeAsync(6000)
    })
    expect(mocks.listThreads).toHaveBeenCalledTimes(calls)
  })

  it('命名中的旧会话不在最近列表第一页时仍刷新当前标题', async () => {
    vi.useFakeTimers()
    mocks.getThread.mockResolvedValue({
      thread: thread('old', { title: null, title_pending: true }),
      turns: [],
    })
    const { result } = renderHook(() => useAgentChat())
    await act(async () => {
      await result.current.selectThread('old')
    })
    mocks.getThread.mockResolvedValue({
      thread: thread('old', { title: '历史回测复盘', title_pending: false }),
      turns: [],
    })
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000)
    })
    expect(mocks.getThread).toHaveBeenCalledWith('old', 1)
    expect(result.current.currentThread?.title).toBe('历史回测复盘')
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
      {
        tool: 'quant_run_analysis',
        summary: 'run 创建',
        callId: null,
        runId: 'run-77',
      },
    ])
    expect(assistant?.runId).toBe('run-77')
    expect(assistant?.status).toBe('completed')
    expect(onRunLinked).toHaveBeenCalledWith('run-77')
  })

  it('turn.done 早于 submitTurn 响应到达时保留终态', async () => {
    mocks.createThread.mockResolvedValue(thread('t-fast', { title: '' }))
    mocks.getThread.mockResolvedValue({
      thread: thread('t-fast', { title: '' }),
      turns: [],
    })
    let resolveSubmit!: (value: ReturnType<typeof turn>) => void
    mocks.submitTurn.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveSubmit = resolve
        }),
    )
    const { result } = renderHook(() => useAgentChat())
    await act(async () => {
      await result.current.newThread()
    })

    let sending!: Promise<void>
    act(() => {
      sending = result.current.send('你好')
    })
    act(() => {
      mocks.instances[0].emit({
        seq: 1,
        type: 'assistant_chunk',
        turn_id: 1,
        payload: { content: '你好，我是量化助手。' },
      })
      mocks.instances[0].emit({
        seq: 2,
        type: 'turn.done',
        turn_id: 1,
        payload: {
          status: 'completed',
          final_reply: '你好，我是量化助手。',
          end_reason: 'completed',
        },
      })
    })
    await act(async () => {
      resolveSubmit(turn(1, 't-fast', { content: '你好', status: 'queued' }))
      await sending
    })

    expect(result.current.running).toBe(false)
    expect(result.current.messages[1]).toMatchObject({
      role: 'assistant',
      status: 'completed',
      content: '你好，我是量化助手。',
    })
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

  it('最新 turn 状态变化时刷新会话列表（左栏运行状态）', async () => {
    mocks.createThread.mockResolvedValue(thread('t-1', { title: 'x' }))
    mocks.getThread.mockResolvedValue({
      thread: thread('t-1', { title: 'x' }),
      turns: [],
    })
    mocks.submitTurn.mockResolvedValue(turn(1, 't-1', { status: 'queued' }))
    const { result } = renderHook(() => useAgentChat())
    const before = mocks.listThreads.mock.calls.length
    await act(async () => {
      await result.current.newThread()
    })
    await act(async () => {
      await result.current.send('分析')
    })
    act(() => {
      mocks.instances[0].emit({
        seq: 1,
        type: 'turn.done',
        turn_id: 1,
        payload: { status: 'completed', final_reply: 'ok' },
      })
    })
    expect(mocks.listThreads.mock.calls.length).toBeGreaterThan(before)
  })

  it('keeps confirmed stock before submit returns and ignores older replay', async () => {
    mocks.getThread.mockResolvedValue({ thread: thread('t-stock'), turns: [] })
    const submit = deferred<ReturnType<typeof turn>>()
    mocks.submitTurn.mockReturnValue(submit.promise)
    const { result } = renderHook(() => useAgentChat())
    await act(async () => {
      await result.current.selectThread('t-stock')
    })
    let sending!: Promise<void>
    act(() => {
      sending = result.current.send('000001.sz')
    })
    act(() => {
      mocks.instances[0].emit(selection(4, 2, '000001.sz'))
      mocks.instances[0].emit(selection(1, 1, 'sh.600000'))
      mocks.instances[0].emit(selection(3, 2, 'sh.600000'))
    })
    expect(result.current.stockCode).toBe('sz.000001')
    await act(async () => {
      submit.resolve(turn(2, 't-stock'))
      await sending
    })
    expect(result.current.stockCode).toBe('sz.000001')
  })

  it('clears selection immediately and ignores late events and submit on thread switch', async () => {
    mocks.getThread.mockResolvedValueOnce({ thread: thread('a'), turns: [] })
    const { result } = renderHook(() => useAgentChat())
    await act(async () => {
      await result.current.selectThread('a')
    })
    act(() => {
      mocks.instances[0].emit(selection(1, 1, 'sz.000001'))
    })
    const submit = deferred<ReturnType<typeof turn>>()
    mocks.submitTurn.mockReturnValue(submit.promise)
    let sending!: Promise<void>
    act(() => {
      sending = result.current.send('消息')
    })
    const loading = deferred<{
      thread: ReturnType<typeof thread>
      turns: ReturnType<typeof turn>[]
    }>()
    mocks.getThread.mockReturnValueOnce(loading.promise)
    let switching!: Promise<void>
    act(() => {
      switching = result.current.selectThread('b')
    })
    expect(result.current.stockCode).toBeNull()
    act(() => {
      mocks.instances[0].emit(selection(9, 1, 'sh.600000'))
    })
    await act(async () => {
      submit.resolve(turn(2, 'a'))
      await sending
      loading.resolve({ thread: thread('b'), turns: [] })
      await switching
    })
    expect(result.current.currentThread?.thread_id).toBe('b')
    expect(result.current.messages).toEqual([])
    expect(result.current.stockCode).toBeNull()
  })

  it('older history and replay cannot replace the latest confirmed stock', async () => {
    mocks.getThread.mockResolvedValueOnce({
      thread: thread('a'),
      turns: [turn(20, 'a')],
      has_more: true,
    })
    const { result } = renderHook(() => useAgentChat())
    await act(async () => {
      await result.current.selectThread('a')
    })
    act(() => {
      mocks.instances[0].emit(selection(20, 20, 'sz.000001'))
    })
    mocks.getThread.mockResolvedValueOnce({
      thread: thread('a'),
      turns: [turn(1, 'a')],
      has_more: false,
    })
    await act(async () => {
      await result.current.loadOlder()
    })
    act(() => {
      mocks.instances[0].emit(selection(1, 1, 'sh.600000'))
    })
    expect(result.current.stockCode).toBe('sz.000001')
  })

  it('a slower thread response cannot replace a newer selection', async () => {
    const first = deferred<{
      thread: ReturnType<typeof thread>
      turns: ReturnType<typeof turn>[]
    }>()
    mocks.getThread
      .mockReturnValueOnce(first.promise)
      .mockResolvedValueOnce({ thread: thread('b'), turns: [] })
    const { result } = renderHook(() => useAgentChat())
    let oldSelection!: Promise<void>
    act(() => {
      oldSelection = result.current.selectThread('a')
    })
    await act(async () => {
      await result.current.selectThread('b')
    })
    await act(async () => {
      first.resolve({ thread: thread('a'), turns: [] })
      await oldSelection
    })
    expect(result.current.currentThread?.thread_id).toBe('b')
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
