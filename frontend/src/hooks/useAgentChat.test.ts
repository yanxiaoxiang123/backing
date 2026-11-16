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

  it.each([false, true])(
    'StrictMode 重复挂载后仍恢复会话与消息（路由托管 %s）',
    async (controlled) => {
      window.history.replaceState({}, '', '/workspace?thread_id=t-restored')
      mocks.getThread.mockResolvedValue({
        thread: thread('t-restored'),
        turns: [
          turn(1, 't-restored', {
            status: 'completed',
            final_reply: '已保存的研究结论',
          }),
        ],
      })
      const { result } = renderHook(
        () => useAgentChat(controlled ? { threadId: 't-restored' } : {}),
        { wrapper: StrictMode },
      )
      await waitFor(() => {
        expect(result.current.currentThread?.thread_id).toBe('t-restored')
        expect(
          result.current.messages.some(
            (message) => message.content === '已保存的研究结论',
          ),
        ).toBe(true)
      })
    },
  )

  it('路由切换会话时忽略旧响应，并可返回空会话', async () => {
    const old = deferred<{
      thread: ReturnType<typeof thread>
      turns: ReturnType<typeof turn>[]
    }>()
    mocks.getThread.mockImplementation((id: string) =>
      id === 'old'
        ? old.promise
        : Promise.resolve({
            thread: thread(id),
            turns: [turn(2, id, { status: 'completed', final_reply: `reply ${id}` })],
          }),
    )
    const { result, rerender } = renderHook(
      ({ id }: { id: string | null }) => useAgentChat({ threadId: id }),
      { initialProps: { id: 'old' as string | null } },
    )
    rerender({ id: 'new' })
    await waitFor(() => expect(result.current.currentThread?.thread_id).toBe('new'))
    await act(async () => {
      old.resolve({ thread: thread('old'), turns: [] })
    })
    expect(
      result.current.messages.some((message) => message.content === 'reply new'),
    ).toBe(true)
    rerender({ id: null })
    await waitFor(() => expect(result.current.currentThread).toBeNull())
    expect(result.current.messages).toEqual([])
  })

  it('会话选择通知路由宿主并保留浏览器历史状态', async () => {
    window.history.replaceState(
      { key: 'router-key', idx: 4 },
      '',
      '/workspace?panel=alerts&stock=sh.600000',
    )
    mocks.getThread.mockResolvedValue({ thread: thread('t-new'), turns: [] })
    const changes: Array<string | null> = []
    const { result } = renderHook(() =>
      useAgentChat({ onThreadChange: (id) => changes.push(id) }),
    )
    await act(async () => {
      await result.current.selectThread('t-new')
    })
    expect(changes).toEqual(['t-new'])
    expect(window.history.state).toEqual({ key: 'router-key', idx: 4 })
    expect(window.location.search).toBe('?panel=alerts&stock=sh.600000')
  })

  it('默认会话 URL 写入保留 React Router 历史状态和参数', async () => {
    window.history.replaceState(
      { key: 'existing-key', idx: 2 },
      '',
      '/workspace?panel=risk',
    )
    mocks.getThread.mockResolvedValue({ thread: thread('t-legacy'), turns: [] })
    const { result } = renderHook(() => useAgentChat())
    await act(async () => {
      await result.current.selectThread('t-legacy')
    })
    expect(window.history.state).toEqual({ key: 'existing-key', idx: 2 })
    expect(new URLSearchParams(window.location.search).get('panel')).toBe('risk')
    expect(new URLSearchParams(window.location.search).get('thread_id')).toBe(
      't-legacy',
    )
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

  it('reports accepted submissions independently of a later session switch', async () => {
    mocks.getThread.mockResolvedValue({ thread: thread('source'), turns: [] })
    const request = deferred<ReturnType<typeof turn>>()
    mocks.submitTurn.mockReturnValue(request.promise)
    const { result } = renderHook(() => useAgentChat())
    await act(async () => result.current.selectThread('source'))
    let sending!: ReturnType<typeof result.current.send>
    act(() => {
      sending = result.current.send('核验证据')
    })
    mocks.getThread.mockResolvedValue({ thread: thread('other'), turns: [] })
    await act(async () => result.current.selectThread('other'))
    let receipt: unknown
    await act(async () => {
      request.resolve(turn(8, 'source'))
      receipt = await sending
    })
    expect(receipt).toEqual({ accepted: true, threadId: 'source' })
    expect(result.current.currentThread?.thread_id).toBe('other')
    expect(result.current.messages).toEqual([])
  })

  it('announces first thread before submission and reports a rejection with its identity', async () => {
    mocks.createThread.mockResolvedValue(thread('created'))
    mocks.submitTurn.mockRejectedValue(new Error('rejected'))
    const created = vi.fn()
    const { result } = renderHook(() => useAgentChat())
    let receipt: unknown
    await act(async () => {
      receipt = await result.current.send('保留问题', undefined, created)
    })
    expect(receipt).toEqual({ accepted: false, threadId: 'created' })
    expect(created).toHaveBeenCalledWith('created')
    expect(created.mock.invocationCallOrder[0]).toBeLessThan(
      mocks.submitTurn.mock.invocationCallOrder[
        mocks.submitTurn.mock.invocationCallOrder.length - 1
      ],
    )
    expect(result.current.error).toContain('rejected')
  })

  it('captures the original page context before waiting for thread creation', async () => {
    const creation = deferred<ReturnType<typeof thread>>()
    mocks.createThread.mockReturnValue(creation.promise)
    mocks.submitTurn.mockResolvedValue(turn(3, 'created'))
    const { result, rerender } = renderHook(
      ({ stock }) =>
        useAgentChat({
          context: { route: '/strategies', entity_type: 'stock', entity_id: stock },
        }),
      { initialProps: { stock: 'sh.600000' } },
    )
    let sending!: ReturnType<typeof result.current.send>
    act(() => {
      sending = result.current.send('核验这只股票')
    })
    rerender({ stock: 'sz.000002' })
    await act(async () => {
      creation.resolve(thread('created'))
      await sending
    })
    expect(
      mocks.submitTurn.mock.calls[mocks.submitTurn.mock.calls.length - 1]?.[3],
    ).toEqual({
      route: '/strategies',
      entity_type: 'stock',
      entity_id: 'sh.600000',
    })
  })

  it('returns a failed receipt when no thread could be created', async () => {
    mocks.createThread.mockRejectedValue(new Error('creation failed'))
    const { result } = renderHook(() => useAgentChat())
    let receipt: unknown
    await act(async () => {
      receipt = await result.current.send('保留问题')
    })
    expect(receipt).toEqual({ accepted: false, threadId: null })
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

    let sending!: ReturnType<typeof result.current.send>
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
    let sending!: ReturnType<typeof result.current.send>
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
    let sending!: ReturnType<typeof result.current.send>
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
