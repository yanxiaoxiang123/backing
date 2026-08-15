import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AgentRunStream } from './agentRuns'

function frame(id: number, data: unknown, eventName?: string): string {
  const lines = [`id: ${id}`, `data: ${JSON.stringify(data)}`]
  if (eventName) lines.unshift(`event: ${eventName}`)
  return `${lines.join('\n')}\n\n`
}

function doneFrame(): string {
  return 'event: done\ndata: {}\n\n'
}

function sseResponse(chunks: string[]): Response {
  const body = new ReadableStream({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(new TextEncoder().encode(chunk))
      controller.close()
    },
  })
  return new Response(body, {
    status: 200,
    headers: { 'content-type': 'text/event-stream' },
  })
}

describe('AgentRunStream', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('解析 step/tool_call 事件并在 done 后关闭', async () => {
    const step = { type: 'step', seq: 1, node: 'supervisor', status: 'completed' }
    const tool = { type: 'tool_call', tool: 'market.kline', status: 'ok' }
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(sseResponse([frame(1, step), frame(2, tool), doneFrame()])),
    )

    const stream = new AgentRunStream('run-1')
    const events: unknown[] = []
    const states: string[] = []
    let done = false
    stream.onEvent = (e) => events.push(e)
    stream.onDone = () => {
      done = true
    }
    stream.onStateChange = (s) => states.push(s)
    stream.start(0)
    await vi.runAllTimersAsync()

    expect(events).toHaveLength(2)
    expect(events[0]).toMatchObject({ type: 'step', node: 'supervisor' })
    expect(events[1]).toMatchObject({ type: 'tool_call', tool: 'market.kline' })
    expect(done).toBe(true)
    expect(states).toContain('closed')
  })

  it('断线后带 Last-Event-ID 重连并续传', async () => {
    const step = { type: 'step', seq: 1, node: 'a', status: 'completed' }
    const next = { type: 'step', seq: 2, node: 'b', status: 'completed' }
    const requestHeaders: Array<Record<string, string>> = []

    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        // 第一次连接：收到 seq1 后服务端断开（无 done）
        .mockImplementationOnce((_url: string, opts?: RequestInit) => {
          requestHeaders.push((opts?.headers ?? {}) as Record<string, string>)
          return Promise.resolve(sseResponse([frame(1, step)]))
        })
        // 重连：携带 Last-Event-ID: 1，收到 seq2 + done
        .mockImplementationOnce((_url: string, opts?: RequestInit) => {
          requestHeaders.push((opts?.headers ?? {}) as Record<string, string>)
          return Promise.resolve(sseResponse([frame(2, next), doneFrame()]))
        }),
    )

    const stream = new AgentRunStream('run-2')
    const events: unknown[] = []
    stream.onEvent = (e) => events.push(e)
    stream.start(0)
    await vi.runAllTimersAsync()

    expect(events.map((e) => (e as { seq?: number }).seq)).toEqual([1, 2])
    expect(requestHeaders[1]['Last-Event-ID']).toBe('1')
  })

  it('stop 中止连接且不再重连', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(() => new Promise(() => undefined)), // 永不返回
    )
    const stream = new AgentRunStream('run-3')
    const states: string[] = []
    stream.onStateChange = (s) => states.push(s)
    stream.start(0)
    stream.stop()
    await vi.runAllTimersAsync()
    expect(states).toContain('closed')
  })
})
