// Agent 运行时前端类型（与 backend/app/agent_api + domain 契约对应）

export type RunStatus =
  'planned' | 'running' | 'completed' | 'failed' | 'cancelled' | 'superseded'

export interface RunRecord {
  run_id: string
  objective: string
  status: RunStatus
  budget_json?: Record<string, unknown> | null
  thread_id?: string | null
  snapshot_id?: string | null
  error?: string | null
  created_at?: string | null
  started_at?: string | null
  finished_at?: string | null
}

export interface StepOutput {
  id: number
  seq: number
  node: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  output_schema?: string | null
  output_json?: Record<string, unknown> | null
  tokens_used?: number | null
  duration_s?: number | null
  error?: string | null
  started_at?: string | null
  finished_at?: string | null
}

export interface RunDetail extends RunRecord {
  steps?: StepOutput[]
}

export interface StepEvent {
  type: 'step'
  seq: number
  node: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  output_schema?: string | null
  tokens_used?: number | null
  duration_s?: number | null
  error?: string | null
  started_at?: string | null
  finished_at?: string | null
}

export interface ToolCallEvent {
  type: 'tool_call'
  tool: string
  permission?: string | null
  status?: string | null
  params_hash?: string | null
  result_ref?: string | null
  duration_s?: number | null
  error?: string | null
  created_at?: string | null
}

export type AgentRunEvent = StepEvent | ToolCallEvent

export interface EvidenceItem {
  source_id: string
  as_of: string
  vendor: string
  data_version: string
  summary: string
  reference?: string | null
}

export interface Claim {
  claim: string
  category: string
  direction?: 'bullish' | 'bearish' | 'neutral' | null
  confidence: number
  evidence: EvidenceItem[]
  hypothesis: boolean
}

export interface BacktestPanelData {
  strategy_name?: string
  total_return?: number
  annual_return?: number
  max_drawdown_pct?: number
  sharpe_out_of_sample?: number
  passed?: boolean
  reasons?: string[]
  snapshot_id?: string
}

export interface RiskPanelData {
  positions?: Array<{
    code: string
    action: string
    weight: number
    confidence: number
  }>
  constraints?: Array<{ rule: string; passed: boolean; detail: string }>
  rejected?: boolean
  rejection_reasons?: string[]
}

export interface ApprovalRequest {
  id: number | string
  action: string
  summary: string
  direction?: string | null
  target_position_pct?: number | null
  risk_summary?: string | null
  expires_at?: string | null
  status: 'pending' | 'approved' | 'rejected' | 'expired'
}

export interface ArtifactRecord {
  id: number
  run_id: string
  artifact_type: string
  uri: string
  checksum?: string | null
  source_id?: string | null
  as_of?: string | null
  schema_version?: string | null
}

export interface AttributionData {
  run_id?: string | null
  start_date: string
  end_date: string
  total_portfolio_return: number
  total_benchmark_return: number
  alpha: number
  beta: number
  exposure_effect: number
  selection_effect: number
  cost_drag: number
  benchmark_available: boolean
}
