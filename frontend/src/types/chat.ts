// Agent 聊天前端类型（与 docs/specs/2026-08-18-agent-workspace-chat.md D4/D8 契约对应）

export type ChatTurnStatus =
  'queued' | 'running' | 'completed' | 'failed' | 'cancelled' | 'interrupted'

export interface ChatThread {
  thread_id: string
  title: string
  status: string
  last_run_id: string | null
  archived: boolean
  created_at: string | null
  updated_at: string | null
}

export interface ChatTurn {
  id: number
  thread_id: string
  content: string
  status: ChatTurnStatus
  final_reply: string | null
  end_reason: string | null
  error: string | null
  created_at: string | null
}

export type ChatEventType =
  | 'reasoning'
  | 'assistant_chunk'
  | 'tool_call'
  | 'tool_result'
  | 'run.linked'
  | 'turn.done'
  | 'error'

export interface ChatEvent {
  seq: number
  type: ChatEventType
  turn_id: number
  payload: Record<string, unknown>
}

export interface ChatThreadList {
  threads: ChatThread[]
  total: number
}

export interface ChatThreadDetail {
  thread: ChatThread
  turns: ChatTurn[]
}

export interface ChatRuntimeStatus {
  backend: 'native' | 'fake' | string
  available: boolean
  reason: string | null
}

export interface PageContext {
  route: string
  entity_type?: string
  entity_id?: string
}

// 归一化后的聊天消息（供聊天组件渲染）
export interface ToolRow {
  tool: string
  summary: string
  callId?: string | null
  runId?: string | null
}

export interface ChatMessage {
  turnId: number
  role: 'user' | 'assistant'
  content: string
  reasoning: string | null
  tools: ToolRow[]
  status: ChatTurnStatus
  runId: string | null
  error: string | null
}
