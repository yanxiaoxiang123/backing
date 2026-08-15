import api from './api'
import type {
  AgentRunEvent,
  ApprovalRequest,
  ArtifactRecord,
  BacktestPanelData,
  Claim,
  RiskPanelData,
  RunDetail,
  RunRecord,
} from '../types/agent'

export type StreamState = 'idle' | 'connecting' | 'active' | 'closed' | 'error'

export interface CreateRunResult {
  run_id: string
  status: string
  events_url: string
}

// ---------------------------------------------------------------------------
// 结构化推导：run.steps（节点输出）→ 研究面板数据（纯函数，便于测试）
// ---------------------------------------------------------------------------

export function deriveResearchClaims(run: RunDetail | null): Claim[] {
  const step = run?.steps?.find((s) => s.node === 'research')
  const claims = step?.output_json?.['claims']
  return Array.isArray(claims) ? (claims as Claim[]) : []
}

export function deriveBacktestData(run: RunDetail | null): BacktestPanelData | null {
  const step = run?.steps?.find((s) => s.node === 'backtest_critic')
  return (step?.output_json as BacktestPanelData | undefined) ?? null
}

export function deriveRiskData(run: RunDetail | null): RiskPanelData | null {
  const step = run?.steps?.find((s) => s.node === 'portfolio_risk')
  return (step?.output_json as RiskPanelData | undefined) ?? null
}

// ---------------------------------------------------------------------------
// SSE 事件流客户端：Last-Event-ID 断线续传 + 自动重连 + done 收口
// ---------------------------------------------------------------------------
export class AgentRunStream {
  private abort?: AbortController
  private lastEventId = 0
  private reconnectTimer?: ReturnType<typeof setTimeout>
  private running = false

  onEvent?: (event: AgentRunEvent) => void
  onDone?: () => void
  onStateChange?: (state: StreamState, error?: unknown) => void

  constructor(private runId: string) {}

  start(lastEventId = 0): void {
    this.lastEventId = lastEventId
    this.running = true
    void this.connect()
  }

  stop(): void {
    this.running = false
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer)
    this.abort?.abort()
    this.onStateChange?.('closed')
  }

  private async connect(): Promise<void> {
    if (!this.running) return
    this.onStateChange?.('connecting')
    this.abort = new AbortController()
    try {
      const headers: Record<string, string> = {}
      if (this.lastEventId > 0) headers['Last-Event-ID'] = String(this.lastEventId)
      const resp = await fetch(`/api/v1/agent-runs/${this.runId}/events`, {
        headers,
        signal: this.abort.signal,
      })
      if (!resp.ok || !resp.body) throw new Error(`SSE 连接失败: ${resp.status}`)
      this.onStateChange?.('active')

      const reader = resp.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      while (this.running) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const frames = buffer.split('\n\n')
        buffer = frames.pop() ?? ''
        for (const frame of frames) this.handleFrame(frame)
      }
      if (this.running) this.scheduleReconnect() // 服务端断开但未 done → 续传重连
    } catch (err) {
      if (this.running && !this.abort?.signal.aborted) {
        this.onStateChange?.('error', err)
        this.scheduleReconnect()
      }
    }
  }

  private handleFrame(frame: string): void {
    let id = this.lastEventId
    let eventName = ''
    const dataLines: string[] = []
    for (const line of frame.split('\n')) {
      if (line.startsWith('id:')) id = Number(line.slice(3).trim()) || id
      else if (line.startsWith('event:')) eventName = line.slice(6).trim()
      else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
    }
    if (dataLines.length === 0) return
    const data = dataLines.join('\n')
    if (eventName === 'done') {
      this.lastEventId = id
      this.running = false
      this.onStateChange?.('closed')
      this.onDone?.()
      return
    }
    this.lastEventId = id
    try {
      this.onEvent?.(JSON.parse(data) as AgentRunEvent)
    } catch {
      // 忽略畸形帧
    }
  }

  private scheduleReconnect(): void {
    if (!this.running) return
    this.reconnectTimer = setTimeout(() => void this.connect(), 1000)
  }
}

// ---------------------------------------------------------------------------
// REST 辅助
// ---------------------------------------------------------------------------
export async function createRun(objective: string): Promise<CreateRunResult> {
  const resp = await api.post<CreateRunResult>('/agent-runs', { objective })
  return resp.data
}

export async function getRun(runId: string): Promise<RunDetail> {
  const resp = await api.get<RunDetail>(`/agent-runs/${runId}`)
  return resp.data
}

export async function cancelRun(runId: string): Promise<RunRecord> {
  const resp = await api.post<RunRecord>(`/agent-runs/${runId}/cancel`)
  return resp.data
}

export async function resumeRun(runId: string, wait = false): Promise<RunRecord> {
  const resp = await api.post<RunRecord>(`/agent-runs/${runId}/resume`, null, {
    params: { wait },
  })
  return resp.data
}

export async function listArtifacts(runId: string): Promise<ArtifactRecord[]> {
  const resp = await api.get<{ artifacts: ArtifactRecord[] }>(
    `/agent-runs/${runId}/artifacts`,
  )
  return resp.data.artifacts
}

export async function listApprovals(runId: string): Promise<ApprovalRequest[]> {
  const resp = await api.get<{ approvals: ApprovalRequest[] }>(
    `/agent-runs/${runId}/approvals`,
  )
  return resp.data.approvals
}

export async function decideApproval(
  runId: string,
  approvalId: number | string,
  decision: 'approved' | 'rejected',
): Promise<void> {
  await api.post(`/agent-runs/${runId}/approvals/${approvalId}/decide`, {
    decision,
    decided_by: 'workspace',
  })
}
