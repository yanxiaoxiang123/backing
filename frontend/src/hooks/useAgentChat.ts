import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type {
  ChatEvent,
  ChatMessage,
  ChatThread,
  ChatTurn,
  ToolRow,
} from '../types/chat'
import {
  ChatEventStream,
  archiveThread,
  cancelTurn,
  createThread,
  getThread,
  listThreads,
  submitTurn,
  type ChatStreamState,
} from '../services/agentChats'
import { getApiErrorMessage } from '../services/api'

interface TurnParts {
  reasoning: string
  chunks: string[]
  tools: ToolRow[]
  runId: string | null
}

export interface UseAgentChatOptions {
  onRunLinked?: (runId: string) => void
}

export interface UseAgentChatResult {
  threads: ChatThread[]
  currentThread: ChatThread | null
  messages: ChatMessage[]
  streamState: ChatStreamState
  running: boolean
  error: string | null
  selectThread: (threadId: string) => Promise<void>
  newThread: () => Promise<string>
  send: (content: string) => Promise<void>
  stop: () => Promise<void>
  archive: (threadId: string) => Promise<void>
}

function newIdempotencyKey(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`
}

/**
 * Agent 聊天会话生命周期：会话列表 → 切换/新建 → 提交 turn → SSE 事件合并
 * （reasoning/assistant_chunk/tool_call/tool_result/run.linked/turn.done）→ 队列/停止。
 * 刷新后由 URL 中的 thread_id 恢复（聊天历史 + SSE 游标从 0 重放）。
 */
export function useAgentChat(
  options: UseAgentChatOptions = {},
): UseAgentChatResult {
  const onRunLinkedRef = useRef(options.onRunLinked)
  onRunLinkedRef.current = options.onRunLinked

  const initialThreadId = useRef<string | null>(
    typeof window === 'undefined'
      ? null
      : new URLSearchParams(window.location.search).get('thread_id'),
  )
  const [threads, setThreads] = useState<ChatThread[]>([])
  const [currentThread, setCurrentThread] = useState<ChatThread | null>(null)
  const [turns, setTurns] = useState<ChatTurn[]>([])
  const [parts, setParts] = useState<Record<number, TurnParts>>({})
  const [streamState, setStreamState] = useState<ChatStreamState>('idle')
  const [error, setError] = useState<string | null>(null)
  const streamRef = useRef<ChatEventStream | null>(null)

  const persistThreadId = useCallback((id: string | null) => {
    if (typeof window === 'undefined') return
    const url = new URL(window.location.href)
    if (id) url.searchParams.set('thread_id', id)
    else url.searchParams.delete('thread_id')
    window.history.replaceState({}, '', `${url.pathname}${url.search}${url.hash}`)
  }, [])

  const applyEvent = useCallback((event: ChatEvent) => {
    const turnId = event.turn_id
    const payload = event.payload
    if (event.type === 'reasoning') {
      setParts((prev) => ({
        ...prev,
        [turnId]: {
          reasoning: (prev[turnId]?.reasoning ?? '') + String(payload['content'] ?? ''),
          chunks: prev[turnId]?.chunks ?? [],
          tools: prev[turnId]?.tools ?? [],
          runId: prev[turnId]?.runId ?? null,
        },
      }))
    } else if (event.type === 'assistant_chunk') {
      setParts((prev) => ({
        ...prev,
        [turnId]: {
          reasoning: prev[turnId]?.reasoning ?? '',
          chunks: [...(prev[turnId]?.chunks ?? []), String(payload['content'] ?? '')],
          tools: prev[turnId]?.tools ?? [],
          runId: prev[turnId]?.runId ?? null,
        },
      }))
    } else if (event.type === 'tool_call') {
      setParts((prev) => ({
        ...prev,
        [turnId]: {
          reasoning: prev[turnId]?.reasoning ?? '',
          chunks: prev[turnId]?.chunks ?? [],
          tools: [
            ...(prev[turnId]?.tools ?? []),
            { tool: String(payload['tool'] ?? ''), summary: '', runId: null },
          ],
          runId: prev[turnId]?.runId ?? null,
        },
      }))
    } else if (event.type === 'tool_result') {
      setParts((prev) => {
        const tools = [...(prev[turnId]?.tools ?? [])]
        const idx = tools
          .map((t) => t.tool)
          .lastIndexOf(String(payload['tool'] ?? ''))
        const summary = String(payload['summary'] ?? payload['result'] ?? '')
        if (idx >= 0) {
          tools[idx] = { ...tools[idx], summary }
          if (payload['run_id']) tools[idx] = { ...tools[idx], runId: String(payload['run_id']) }
        }
        return {
          ...prev,
          [turnId]: {
            reasoning: prev[turnId]?.reasoning ?? '',
            chunks: prev[turnId]?.chunks ?? [],
            tools,
            runId: prev[turnId]?.runId ?? null,
          },
        }
      })
    } else if (event.type === 'run.linked') {
      const runId = String(payload['run_id'] ?? '')
      setParts((prev) => ({
        ...prev,
        [turnId]: {
          reasoning: prev[turnId]?.reasoning ?? '',
          chunks: prev[turnId]?.chunks ?? [],
          tools: prev[turnId]?.tools ?? [],
          runId,
        },
      }))
      if (runId) onRunLinkedRef.current?.(runId)
    } else if (event.type === 'turn.done') {
      setTurns((prev) =>
        prev.map((turn) =>
          turn.id === turnId
            ? {
                ...turn,
                status: (payload['status'] as ChatTurn['status']) ?? turn.status,
                final_reply:
                  String(payload['final_reply'] ?? turn.final_reply ?? '') || null,
                end_reason: String(payload['end_reason'] ?? '') || null,
                error: String(payload['error'] ?? '') || null,
              }
            : turn,
        ),
      )
    }
  }, [])

  const connectStream = useCallback(
    (threadId: string, lastEventId: number) => {
      streamRef.current?.stop()
      const stream = new ChatEventStream(threadId)
      streamRef.current = stream
      stream.onEvent = applyEvent
      stream.onStateChange = (state, err) => {
        setStreamState(state)
        if (state === 'error')
          setError(err instanceof Error ? err.message : String(err))
      }
      stream.start(lastEventId)
    },
    [applyEvent],
  )

  const refreshThreads = useCallback(async () => {
    try {
      const data = await listThreads()
      setThreads(data.threads)
    } catch {
      // 列表失败不阻塞当前会话
    }
  }, [])

  const selectThread = useCallback(
    async (threadId: string): Promise<void> => {
      try {
        const detail = await getThread(threadId)
        setCurrentThread(detail.thread)
        setTurns(detail.turns)
        setParts({})
        setError(null)
        persistThreadId(threadId)
        connectStream(threadId, 0)
      } catch (exc) {
        setError(getApiErrorMessage(exc))
      }
    },
    [connectStream, persistThreadId],
  )

  const newThread = useCallback(async (): Promise<string> => {
    const thread = await createThread()
    setThreads((prev) => [thread, ...prev])
    await selectThread(thread.thread_id)
    return thread.thread_id
  }, [selectThread])

  const send = useCallback(
    async (content: string): Promise<void> => {
      const text = content.trim()
      if (!text) return
      try {
        let thread = currentThread
        if (!thread) {
          const created = await createThread()
          setThreads((prev) => [created, ...prev])
          setCurrentThread(created)
          thread = created
          persistThreadId(created.thread_id)
          connectStream(created.thread_id, 0)
        }
        const turn = await submitTurn(thread.thread_id, text, newIdempotencyKey())
        setTurns((prev) => [...prev, turn])
        if (thread.title === '' || thread.title == null) {
          setCurrentThread((prev) =>
            prev ? { ...prev, title: text.slice(0, 36) } : prev,
          )
          setThreads((prev) =>
            prev.map((t) =>
              t.thread_id === thread!.thread_id
                ? { ...t, title: text.slice(0, 36) }
                : t,
            ),
          )
        }
      } catch (exc) {
        setError(getApiErrorMessage(exc))
      }
    },
    [connectStream, currentThread, persistThreadId],
  )

  const stop = useCallback(async (): Promise<void> => {
    if (!currentThread) return
    try {
      const turn = await cancelTurn(currentThread.thread_id)
      setTurns((prev) =>
        prev.map((t) => (t.id === turn.id ? { ...t, ...turn } : t)),
      )
    } catch (exc) {
      setError(getApiErrorMessage(exc))
    }
  }, [currentThread])

  const archive = useCallback(
    async (threadId: string): Promise<void> => {
      try {
        await archiveThread(threadId)
        setThreads((prev) => prev.filter((t) => t.thread_id !== threadId))
        if (currentThread?.thread_id === threadId) {
          setCurrentThread(null)
          setTurns([])
          setParts({})
          persistThreadId(null)
        }
      } catch (exc) {
        setError(getApiErrorMessage(exc))
      }
    },
    [currentThread, persistThreadId],
  )

  // 刷新后从 URL 中的 thread_id 恢复；只消费一次。
  useEffect(() => {
    const id = initialThreadId.current
    if (id) {
      initialThreadId.current = null
      void selectThread(id)
    } else {
      void refreshThreads()
    }
  }, [refreshThreads, selectThread])

  useEffect(() => {
    return () => streamRef.current?.stop()
  }, [])

  const messages = useMemo<ChatMessage[]>(() => {
    const msgs: ChatMessage[] = []
    for (const turn of turns) {
      msgs.push({
        turnId: turn.id,
        role: 'user',
        content: turn.content,
        reasoning: null,
        tools: [],
        status: turn.status,
        runId: null,
        error: null,
      })
      const p = parts[turn.id]
      msgs.push({
        turnId: turn.id,
        role: 'assistant',
        content:
          p && p.chunks.length > 0 ? p.chunks.join('') : (turn.final_reply ?? ''),
        reasoning: p?.reasoning ?? null,
        tools: p?.tools ?? [],
        status: turn.status,
        runId: p?.runId ?? null,
        error: turn.error,
      })
    }
    return msgs
  }, [parts, turns])

  const running = useMemo(
    () => turns.some((t) => t.status === 'queued' || t.status === 'running'),
    [turns],
  )

  return {
    threads,
    currentThread,
    messages,
    streamState,
    running,
    error,
    selectThread,
    newThread,
    send,
    stop,
    archive,
  }
}
