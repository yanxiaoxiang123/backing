import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type {
  AgentRunEvent,
  ApprovalRequest,
  ArtifactRecord,
  BacktestPanelData,
  Claim,
  RiskPanelData,
  RunDetail,
  StepEvent,
} from '../types/agent'
import {
  AgentRunStream,
  cancelRun,
  createRun,
  deriveBacktestData,
  deriveResearchClaims,
  deriveRiskData,
  getRun,
  listArtifacts,
  resumeRun,
  type StreamState,
} from '../services/agentRuns'

export interface UseAgentRunResult {
  runId: string | null
  run: RunDetail | null
  events: AgentRunEvent[]
  streamState: StreamState
  artifacts: ArtifactRecord[]
  approvals: ApprovalRequest[]
  researchClaims: Claim[]
  backtestData: BacktestPanelData | null
  riskData: RiskPanelData | null
  error: string | null
  start: (objective: string) => Promise<string>
  cancel: () => Promise<void>
  resume: () => Promise<void>
}

/**
 * 一次 Agent run 的生命周期：创建 → SSE 事件流（断线续传）→ 取消/恢复。
 * 页面刷新后由 run_id 恢复（任务 06 端点 + Last-Event-ID）。
 */
export function useAgentRun(): UseAgentRunResult {
  const [runId, setRunId] = useState<string | null>(null)
  const [run, setRun] = useState<RunDetail | null>(null)
  const [events, setEvents] = useState<AgentRunEvent[]>([])
  const [streamState, setStreamState] = useState<StreamState>('idle')
  const [artifacts, setArtifacts] = useState<ArtifactRecord[]>([])
  const [approvals, setApprovals] = useState<ApprovalRequest[]>([])
  const [error, setError] = useState<string | null>(null)
  const streamRef = useRef<AgentRunStream | null>(null)

  const refresh = useCallback(async (id: string) => {
    try {
      const record = await getRun(id)
      setRun(record)
    } catch {
      // 状态刷新失败不阻塞事件流
    }
  }, [])

  const start = useCallback(
    async (objective: string): Promise<string> => {
      const result = await createRun(objective)
      setRunId(result.run_id)
      setEvents([])
      setArtifacts([])
      setApprovals([])
      setError(null)

      streamRef.current?.stop()
      const stream = new AgentRunStream(result.run_id)
      streamRef.current = stream
      stream.onEvent = (event) => setEvents((prev) => [...prev, event])
      stream.onDone = () => void refresh(result.run_id)
      stream.onStateChange = (state, err) => {
        setStreamState(state)
        if (state === 'error')
          setError(err instanceof Error ? err.message : String(err))
      }
      stream.start(0)
      void refresh(result.run_id)
      return result.run_id
    },
    [refresh],
  )

  const cancel = useCallback(async () => {
    if (!runId) return
    await cancelRun(runId)
    void refresh(runId)
  }, [runId, refresh])

  const resume = useCallback(async () => {
    if (!runId) return
    streamRef.current?.stop()
    const record = await resumeRun(runId)
    setRun(record)
    const stream = new AgentRunStream(runId)
    streamRef.current = stream
    stream.onEvent = (event) => setEvents((prev) => [...prev, event])
    stream.onDone = () => void refresh(runId)
    stream.onStateChange = setStreamState
    stream.start(events.length)
  }, [runId, refresh, events.length])

  useEffect(() => {
    if (!runId) return
    void listArtifacts(runId)
      .then(setArtifacts)
      .catch(() => undefined)
  }, [runId, run?.status])

  useEffect(() => {
    return () => streamRef.current?.stop()
  }, [])

  const researchClaims = useMemo(() => deriveResearchClaims(run), [run])
  const backtestData = useMemo(() => deriveBacktestData(run), [run])
  const riskData = useMemo(() => deriveRiskData(run), [run])

  // run 终态时用 run.steps（权威事实）收敛事件列表：step 事件按 seq 替换为终态，
  // 保证即使 SSE 丢失部分事件，时间线也不会停留在瞬态"执行中"。
  useEffect(() => {
    if (!run?.steps || run.status === 'running' || run.status === 'planned') return
    setEvents((prev) => {
      const next = [...prev]
      for (const step of run.steps ?? []) {
        const final: StepEvent = {
          type: 'step',
          seq: step.seq,
          node: step.node,
          status: step.status,
          output_schema: step.output_schema,
          tokens_used: step.tokens_used,
          duration_s: step.duration_s,
          error: step.error,
          started_at: step.started_at,
          finished_at: step.finished_at,
        }
        const index = next.findIndex((e) => e.type === 'step' && e.seq === step.seq)
        if (index >= 0) next[index] = final
        else next.push(final)
      }
      return next
    })
  }, [run])

  // SSE 断开/出错时兜底拉取终态，避免界面卡在中间状态
  useEffect(() => {
    if (runId && (streamState === 'closed' || streamState === 'error')) {
      void refresh(runId)
    }
  }, [streamState, runId, refresh])

  return {
    runId,
    run,
    events,
    streamState,
    artifacts,
    approvals,
    researchClaims,
    backtestData,
    riskData,
    error,
    start,
    cancel,
    resume,
  }
}
