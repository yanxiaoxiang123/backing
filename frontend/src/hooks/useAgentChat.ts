import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type {
  ChatEvent,
  ChatMessage,
  ChatThread,
  ChatTurn,
  ToolRow,
  ChatRuntimeStatus,
} from '../types/chat'
import {
  ChatEventStream,
  archiveThread,
  cancelTurn,
  createThread,
  getThread,
  getChatStatus,
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
  runtimeStatus: ChatRuntimeStatus | null
  selectThread: (threadId: string) => Promise<void>
  newThread: () => Promise<string>
  send: (content: string) => Promise<void>
  stop: () => Promise<void>
  archive: (threadId: string) => Promise<void>
  refreshStatus: () => Promise<void>
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
  const [runtimeStatus, setRuntimeStatus] = useState<ChatRuntimeStatus | null>(null)
  const streamRef = useRef<ChatEventStream | null>(null)
  // Fake/本地 Harness 可能在 submitTurn 的 202 响应返回前就完成整轮。
  // 终态事件先到时 turns 中尚无对应行，先暂存补丁，REST 返回后再合并，
  // 避免 completed 被随后到达的 queued 快照覆盖。
  const terminalTurnPatchesRef = useRef<
    Map<number, Partial<ChatTurn>>
  >(new Map())

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
            {
              tool: String(payload['tool'] ?? ''),
              summary: '',
              callId: String(payload['call_id'] ?? '') || null,
              runId: null,
            },
          ],
          runId: prev[turnId]?.runId ?? null,
        },
      }))
    } else if (event.type === 'tool_result') {
      setParts((prev) => {
        const tools = [...(prev[turnId]?.tools ?? [])]
        const callId = String(payload['call_id'] ?? '')
        const idx = callId
          ? tools.map((t) => t.callId).lastIndexOf(callId)
          : tools.map((t) => t.tool).lastIndexOf(String(payload['tool'] ?? ''))
        const rawSummary = payload['summary'] ?? payload['result'] ?? ''
        const summary = typeof rawSummary === 'string'
          ? rawSummary
          : JSON.stringify(rawSummary)
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
      if (runId) {
        setCurrentThread((prev) =>
          prev ? { ...prev, last_run_id: runId } : prev,
        )
        setThreads((prev) =>
          prev.map((thread) =>
            thread.thread_id === currentThread?.thread_id
              ? { ...thread, last_run_id: runId }
              : thread,
          ),
        )
        onRunLinkedRef.current?.(runId)
      }
    } else if (event.type === 'turn.done') {
      const patch: Partial<ChatTurn> = {
        status: (payload['status'] as ChatTurn['status']) ?? 'completed',
        final_reply: String(payload['final_reply'] ?? '') || null,
        end_reason: String(payload['end_reason'] ?? '') || null,
        error: String(payload['error'] ?? '') || null,
      }
      terminalTurnPatchesRef.current.set(turnId, patch)
      setTurns((prev) =>
        prev.map((turn) =>
          turn.id === turnId ? { ...turn, ...patch } : turn,
        ),
      )
      setCurrentThread((prev) => (prev ? { ...prev, status: 'idle' } : prev))
    }
  }, [currentThread?.thread_id])

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
        terminalTurnPatchesRef.current.clear()
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
        if (runtimeStatus && !runtimeStatus.available) {
          setError('Agent 聊天当前不可用，请检查模型配置后重试')
          return
        }
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
        const terminalPatch = terminalTurnPatchesRef.current.get(turn.id)
        const mergedTurn = terminalPatch ? { ...turn, ...terminalPatch } : turn
        setTurns((prev) => {
          const index = prev.findIndex((item) => item.id === mergedTurn.id)
          if (index < 0) return [...prev, mergedTurn]
          const next = [...prev]
          next[index] = { ...next[index], ...mergedTurn }
          return next
        })
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
    [connectStream, currentThread, persistThreadId, runtimeStatus],
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

  const refreshStatus = useCallback(async (): Promise<void> => {
    try {
      setRuntimeStatus(await getChatStatus())
    } catch {
      setRuntimeStatus(null)
    }
  }, [])

  // 刷新后从 URL 中的 thread_id 恢复；只消费一次。
  useEffect(() => {
    void refreshStatus()
  }, [refreshStatus])

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

  // 左栏运行状态跟随最新 turn 生命周期刷新（queued/running → 完成/取消）
  const latestTurnStatus = turns.length > 0 ? turns[turns.length - 1].status : null
  useEffect(() => {
    if (!latestTurnStatus) return
    void refreshThreads()
  }, [latestTurnStatus, refreshThreads])

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
    runtimeStatus,
    selectThread,
    newThread,
    send,
    stop,
    archive,
    refreshStatus,
  }
}
