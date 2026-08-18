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
  decideApproval,
  deriveBacktestData,
  deriveResearchClaims,
  deriveRiskData,
  getRun,
  listApprovals,
  listArtifacts,
  resumeRun,
  type StreamState,
} from '../services/agentRuns'
import { getApiErrorMessage } from '../services/api'

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
  start: (
    objective: string,
    strategyParams?: Record<string, number> | null,
  ) => Promise<string>
  attach: (runId: string) => Promise<void>
  cancel: () => Promise<void>
  resume: () => Promise<void>
  decide: (
    approvalId: number | string,
    decision: 'approved' | 'rejected',
  ) => Promise<void>
}

/**
 * 一次 Agent run 的生命周期：创建 → SSE 事件流（断线续传）→ 取消/恢复。
 * 页面刷新后由 run_id 恢复（任务 06 端点 + Last-Event-ID）。
 */
export function useAgentRun(): UseAgentRunResult {
  const initialRunId = useRef<string | null>(
    typeof window === 'undefined'
      ? null
      : new URLSearchParams(window.location.search).get('run_id'),
  )
  const [runId, setRunId] = useState<string | null>(() => initialRunId.current)
  const [run, setRun] = useState<RunDetail | null>(null)
  const [events, setEvents] = useState<AgentRunEvent[]>([])
  const [streamState, setStreamState] = useState<StreamState>('idle')
  const [artifacts, setArtifacts] = useState<ArtifactRecord[]>([])
  const [approvals, setApprovals] = useState<ApprovalRequest[]>([])
  const [error, setError] = useState<string | null>(null)
  const streamRef = useRef<AgentRunStream | null>(null)

  const persistRunId = useCallback((id: string | null) => {
    if (typeof window === 'undefined') return
    const url = new URL(window.location.href)
    if (id) url.searchParams.set('run_id', id)
    else url.searchParams.delete('run_id')
    window.history.replaceState({}, '', `${url.pathname}${url.search}${url.hash}`)
  }, [])

  const refresh = useCallback(async (id: string) => {
    try {
      const record = await getRun(id)
      setRun(record)
    } catch {
      // 状态刷新失败不阻塞事件流
    }
  }, [])

  const connectStream = useCallback(
    (id: string, lastEventId: number) => {
      streamRef.current?.stop()
      const stream = new AgentRunStream(id)
      streamRef.current = stream
      stream.onEvent = (event) => setEvents((prev) => [...prev, event])
      stream.onDone = () => void refresh(id)
      stream.onStateChange = (state, err) => {
        setStreamState(state)
        if (state === 'error')
          setError(err instanceof Error ? err.message : String(err))
      }
      stream.start(lastEventId)
    },
    [refresh],
  )

  const start = useCallback(
    async (
      objective: string,
      strategyParams?: Record<string, number> | null,
    ): Promise<string> => {
      const result = await createRun(objective, strategyParams)
      setRunId(result.run_id)
      persistRunId(result.run_id)
      setEvents([])
      setArtifacts([])
      setApprovals([])
      setError(null)

      connectStream(result.run_id, 0)
      void refresh(result.run_id)
      return result.run_id
    },
    [connectStream, persistRunId, refresh],
  )

  const attach = useCallback(
    async (id: string): Promise<void> => {
      setRunId(id)
      persistRunId(id)
      setEvents([])
      setArtifacts([])
      setApprovals([])
      setError(null)

      connectStream(id, 0)
      void refresh(id)
    },
    [connectStream, persistRunId, refresh],
  )

  const cancel = useCallback(async () => {
    if (!runId) return
    await cancelRun(runId)
    void refresh(runId)
  }, [runId, refresh])

  const resume = useCallback(async () => {
    if (!runId) return
    const record = await resumeRun(runId)
    setRun(record)
    connectStream(runId, events.length)
  }, [connectStream, events.length, runId])

  // 刷新页面后从 URL 中的 run_id 恢复状态与 SSE；只消费一次，避免 start 后重复建流。
  useEffect(() => {
    const id = initialRunId.current
    if (!id) return
    initialRunId.current = null
    void refresh(id)
    connectStream(id, 0)
  }, [connectStream, refresh])

  useEffect(() => {
    if (!runId) return
    void listArtifacts(runId)
      .then(setArtifacts)
      .catch(() => undefined)
    void listApprovals(runId)
      .then(setApprovals)
      .catch(() => undefined)
  }, [runId, run?.status])

  const decide = useCallback(
    async (approvalId: number | string, decision: 'approved' | 'rejected') => {
      if (!runId) return
      try {
        await decideApproval(runId, approvalId, decision)
      } catch (exc) {
        setError(getApiErrorMessage(exc))
      }
      const fresh = await listApprovals(runId).catch(() => [])
      setApprovals(fresh)
    },
    [runId],
  )

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
    attach,
    cancel,
    resume,
    decide,
  }
}
