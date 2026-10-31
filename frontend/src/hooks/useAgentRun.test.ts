import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => {
  const instances: Array<{
    runId: string
    start: ReturnType<typeof vi.fn>
    stop: ReturnType<typeof vi.fn>
    emit: (event: unknown) => void
  }> = []
  class MockAgentRunStream {
    onEvent?: (event: unknown) => void
    onDone?: () => void
    onStateChange?: (state: string, error?: unknown) => void
    start: ReturnType<typeof vi.fn>
    stop: ReturnType<typeof vi.fn>

    constructor(public runId: string) {
      this.start = vi.fn()
      this.stop = vi.fn()
      instances.push({
        runId,
        start: this.start,
        stop: this.stop,
        emit: (event) => this.onEvent?.(event),
      })
    }
  }
  return {
    instances,
    AgentRunStream: MockAgentRunStream,
    createRun: vi.fn(),
    getRun: vi.fn().mockResolvedValue({}),
    cancelRun: vi.fn(),
    resumeRun: vi.fn(),
    decideApproval: vi.fn(),
    listArtifacts: vi.fn().mockResolvedValue([]),
    listApprovals: vi.fn().mockResolvedValue([]),
    deriveResearchClaims: vi.fn(() => []),
    deriveBacktestData: vi.fn(() => null),
    deriveRiskData: vi.fn(() => null),
    getApiErrorMessage: vi.fn((err: unknown) => String(err)),
  }
})

vi.mock('../services/agentRuns', () => ({
  AgentRunStream: mocks.AgentRunStream,
  createRun: mocks.createRun,
  getRun: mocks.getRun,
  cancelRun: mocks.cancelRun,
  resumeRun: mocks.resumeRun,
  decideApproval: mocks.decideApproval,
  listArtifacts: mocks.listArtifacts,
  listApprovals: mocks.listApprovals,
  deriveResearchClaims: mocks.deriveResearchClaims,
  deriveBacktestData: mocks.deriveBacktestData,
  deriveRiskData: mocks.deriveRiskData,
}))

vi.mock('../services/api', () => ({
  getApiErrorMessage: mocks.getApiErrorMessage,
}))

import { useAgentRun } from './useAgentRun'

describe('useAgentRun.attach', () => {
  beforeEach(() => {
    window.history.replaceState({}, '', '/workspace')
    mocks.instances.length = 0
    mocks.createRun.mockReset()
    mocks.getRun.mockReset()
    mocks.getRun.mockResolvedValue({
      run_id: 'run-9',
      objective: '观察已有 run',
      status: 'running',
      steps: [],
    })
    mocks.listArtifacts.mockResolvedValue([])
    mocks.listApprovals.mockResolvedValue([])
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('attach 观察已有 run：连接 SSE 且不创建任务', async () => {
    const { result } = renderHook(() => useAgentRun())
    let promise: Promise<void>
    act(() => {
      promise = result.current.attach('run-9')
    })
    await act(async () => {
      await promise
    })

    expect(mocks.createRun).not.toHaveBeenCalled()
    expect(mocks.getRun).toHaveBeenCalledWith('run-9')
    expect(result.current.runId).toBe('run-9')
    expect(result.current.run?.status).toBe('running')
    expect(mocks.instances).toHaveLength(1)
    expect(mocks.instances[0].start).toHaveBeenCalledWith(0)
  })

  it('detach clears run state and rejects late HTTP and SSE results', async () => {
    let resolveRun!: (value: unknown) => void
    let resolveArtifacts!: (value: unknown[]) => void
    mocks.getRun.mockReturnValue(
      new Promise((resolve) => {
        resolveRun = resolve
      }),
    )
    mocks.listArtifacts.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveArtifacts = resolve
      }),
    )
    const { result } = renderHook(() => useAgentRun())
    await act(async () => {
      await result.current.attach('old-run')
    })
    act(() => {
      result.current.detach()
    })
    await act(async () => {
      resolveRun({
        run_id: 'old-run',
        objective: 'old',
        status: 'completed',
        steps: [],
      })
      resolveArtifacts([{ id: 'old-artifact' }])
    })
    act(() => {
      mocks.instances[0].emit({ type: 'step', seq: 99 })
    })
    expect(result.current.runId).toBeNull()
    expect(result.current.run).toBeNull()
    expect(result.current.events).toEqual([])
    expect(result.current.artifacts).toEqual([])
    expect(window.location.search).not.toContain('run_id')
  })

  it('a previous run response cannot overwrite a newly attached run', async () => {
    let resolveOld!: (value: unknown) => void
    mocks.getRun
      .mockReturnValueOnce(
        new Promise((resolve) => {
          resolveOld = resolve
        }),
      )
      .mockResolvedValueOnce({ run_id: 'new-run', status: 'running', steps: [] })
    const { result } = renderHook(() => useAgentRun())
    await act(async () => {
      await result.current.attach('old-run')
    })
    await act(async () => {
      await result.current.attach('new-run')
    })
    await act(async () => {
      resolveOld({ run_id: 'old-run', status: 'completed', steps: [] })
    })
    expect(result.current.run?.run_id).toBe('new-run')
  })

  it('detach prevents a pending create from reattaching', async () => {
    let resolveCreate!: (value: { run_id: string }) => void
    mocks.createRun.mockReturnValue(
      new Promise((resolve) => {
        resolveCreate = resolve
      }),
    )
    const { result } = renderHook(() => useAgentRun())
    let starting!: Promise<string>
    act(() => {
      starting = result.current.start('old objective')
    })
    act(() => {
      result.current.detach()
    })
    await act(async () => {
      resolveCreate({ run_id: 'late-run' })
      await starting
    })
    expect(result.current.runId).toBeNull()
    expect(mocks.instances).toHaveLength(0)
  })

  it('attach 后流式事件合并进 events', async () => {
    const { result } = renderHook(() => useAgentRun())
    let promise: Promise<void>
    act(() => {
      promise = result.current.attach('run-9')
    })
    await act(async () => {
      await promise
    })
    act(() => {
      mocks.instances[0].emit({
        type: 'step',
        seq: 1,
        node: 'supervisor',
        status: 'completed',
      })
    })
    expect(result.current.events).toHaveLength(1)
    expect(result.current.events[0]).toMatchObject({ type: 'step', seq: 1 })
  })
})
