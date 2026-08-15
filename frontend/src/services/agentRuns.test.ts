import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  AgentRunStream,
  deriveBacktestData,
  deriveResearchClaims,
  deriveRiskData,
} from './agentRuns'
import type { RunDetail } from '../types/agent'

describe('derive* panel data from run steps', () => {
  const run: RunDetail = {
    run_id: 'r1',
    objective: '生成策略并回测验证 sh.600000',
    status: 'completed',
    steps: [
      {
        id: 1,
        seq: 1,
        node: 'supervisor',
        status: 'completed',
        output_schema: 'RunPlan',
      },
      {
        id: 2,
        seq: 3,
        node: 'research',
        status: 'completed',
        output_schema: 'ResearchClaim[]',
        output_json: { claims: [{ claim: '看多', category: 'technical' }] },
      },
      {
        id: 3,
        seq: 5,
        node: 'backtest_critic',
        status: 'completed',
        output_schema: 'BacktestVerdict',
        output_json: { passed: true, total_return: 0.12, reasons: ['达标'] },
      },
      {
        id: 4,
        seq: 6,
        node: 'portfolio_risk',
        status: 'completed',
        output_schema: 'PortfolioProposal',
        output_json: { positions: [{ code: 'sh.600000' }], rejected: false },
      },
    ],
  }

  it('deriveResearchClaims 提取 research 节点 claims', () => {
    expect(deriveResearchClaims(run)).toEqual([
      { claim: '看多', category: 'technical' },
    ])
    expect(deriveResearchClaims(null)).toEqual([])
  })

  it('deriveBacktestData 提取回测审计输出', () => {
    const data = deriveBacktestData(run)
    expect(data?.passed).toBe(true)
    expect(data?.total_return).toBe(0.12)
    expect(deriveBacktestData(null)).toBeNull()
  })

  it('deriveRiskData 提取组合风险输出', () => {
    const data = deriveRiskData(run)
    expect(data?.rejected).toBe(false)
    expect(data?.positions?.[0].code).toBe('sh.600000')
    expect(deriveRiskData(null)).toBeNull()
  })
})

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
