import api from './api'
import type {
  ChatEvent,
  ChatThread,
  ChatThreadDetail,
  ChatThreadList,
  ChatTurn,
  ChatRuntimeStatus,
} from '../types/chat'

export type ChatStreamState = 'idle' | 'connecting' | 'active' | 'closed' | 'error'

export interface SubmitTurnResult {
  turn: ChatTurn
}

// ---------------------------------------------------------------------------
// REST 客户端（契约见 docs/specs/2026-08-18-agent-workspace-chat.md D8）
// ---------------------------------------------------------------------------
export async function createThread(): Promise<ChatThread> {
  const resp = await api.post<ChatThread>('/agent-chats', {})
  return resp.data
}

export async function listThreads(
  limit = 50,
  offset = 0,
): Promise<ChatThreadList> {
  const resp = await api.get<ChatThreadList>('/agent-chats', {
    params: { limit, offset },
  })
  return resp.data
}

export async function getChatStatus(): Promise<ChatRuntimeStatus> {
  const resp = await api.get<ChatRuntimeStatus>('/agent-chats/status')
  return resp.data
}

export async function getThread(threadId: string): Promise<ChatThreadDetail> {
  const resp = await api.get<ChatThreadDetail>(`/agent-chats/${threadId}`)
  return resp.data
}

export async function submitTurn(
  threadId: string,
  content: string,
  idempotencyKey: string,
): Promise<ChatTurn> {
  const resp = await api.post<SubmitTurnResult>(
    `/agent-chats/${threadId}/turns`,
    { content },
    { headers: { 'Idempotency-Key': idempotencyKey } },
  )
  return resp.data.turn
}

export async function cancelTurn(threadId: string): Promise<ChatTurn> {
  const resp = await api.post<{ turn: ChatTurn }>(
    `/agent-chats/${threadId}/cancel`,
  )
  return resp.data.turn
}

export async function archiveThread(threadId: string): Promise<ChatThread> {
  const resp = await api.post<ChatThread>(`/agent-chats/${threadId}/archive`)
  return resp.data
}

// ---------------------------------------------------------------------------
// 线程事件流 SSE：Last-Event-ID 断线续传 + 自动重连（长生命周期，无 done 终止）
// ---------------------------------------------------------------------------
export class ChatEventStream {
  private abort?: AbortController
  private lastEventId = 0
  private reconnectTimer?: ReturnType<typeof setTimeout>
  private running = false

  onEvent?: (event: ChatEvent) => void
  onStateChange?: (state: ChatStreamState, error?: unknown) => void

  constructor(private threadId: string) {}

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
      const resp = await fetch(`/api/v1/agent-chats/${this.threadId}/events`, {
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
      if (this.running) this.scheduleReconnect()
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
    this.lastEventId = id
    try {
      const payload = JSON.parse(dataLines.join('\n')) as Record<string, unknown>
      const event: ChatEvent = {
        seq: id,
        type: (eventName || 'assistant_chunk') as ChatEvent['type'],
        turn_id: Number(payload['turn_id'] ?? 0),
        payload,
      }
      this.onEvent?.(event)
    } catch {
      // 忽略畸形帧
    }
  }

  private scheduleReconnect(): void {
    if (!this.running) return
    this.reconnectTimer = setTimeout(() => void this.connect(), 1000)
  }
}
