import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type {
  ChatEvent,
  ChatMessage,
  ChatThread,
  ChatTurn,
  ToolRow,
  ChatRuntimeStatus,
  PageContext,
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
import { normalizeStockCode } from '../utils/stockIdentity'

interface TurnParts {
  reasoning: string
  content: string
  tools: ToolRow[]
  runId: string | null
  stockCode: string | null
}

export interface UseAgentChatOptions {
  onRunLinked?: (runId: string) => void
  context?: PageContext
}

export interface UseAgentChatResult {
  threads: ChatThread[]
  currentThread: ChatThread | null
  messages: ChatMessage[]
  stockCode: string | null
  streamState: ChatStreamState
  running: boolean
  error: string | null
  runtimeStatus: ChatRuntimeStatus | null
  selectThread: (threadId: string) => Promise<void>
  newThread: () => Promise<string>
  send: (content: string, context?: PageContext) => Promise<void>
  stop: () => Promise<void>
  archive: (threadId: string) => Promise<void>
  refreshStatus: () => Promise<void>
  loadOlder: () => Promise<void>
  hasMoreHistory: boolean
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
export function useAgentChat(options: UseAgentChatOptions = {}): UseAgentChatResult {
  const onRunLinkedRef = useRef(options.onRunLinked)
  onRunLinkedRef.current = options.onRunLinked
  const contextRef = useRef(options.context)
  contextRef.current = options.context

  const initialThreadId = useRef<string | null>(
    typeof window === 'undefined'
      ? null
      : new URLSearchParams(window.location.search).get('thread_id'),
  )
  const [threads, setThreads] = useState<ChatThread[]>([])
  const [currentThread, setCurrentThread] = useState<ChatThread | null>(null)
  const currentThreadRef = useRef(currentThread)
  currentThreadRef.current = currentThread
  const [turns, setTurns] = useState<ChatTurn[]>([])
  const [parts, setParts] = useState<Record<number, TurnParts>>({})
  const [streamState, setStreamState] = useState<ChatStreamState>('idle')
  const [error, setError] = useState<string | null>(null)
  const [runtimeStatus, setRuntimeStatus] = useState<ChatRuntimeStatus | null>(null)
  const [hasMoreHistory, setHasMoreHistory] = useState(false)
  const historyOffsetRef = useRef(0)
  const streamRef = useRef<ChatEventStream | null>(null)
  const sessionVersionRef = useRef(0)
  const activeThreadRef = useRef<string | null>(null)
  const seenEventIdsRef = useRef<Set<number>>(new Set())
  const selectionSeqRef = useRef<Map<number, number>>(new Map())
  // The SSE endpoint replays from the supplied cursor. Keep the replay bounded
  // to the paged turn window so old events do not recreate an unbounded parts
  // map in the browser.
  const minLoadedTurnIdRef = useRef<number | null>(null)
  const loadedTurnIdsRef = useRef<Set<number>>(new Set())
  // Fake/本地 Harness 可能在 submitTurn 的 202 响应返回前就完成整轮。
  // 终态事件先到时 turns 中尚无对应行，先暂存补丁，REST 返回后再合并，
  // 避免 completed 被随后到达的 queued 快照覆盖。
  const terminalTurnPatchesRef = useRef<Map<number, Partial<ChatTurn>>>(new Map())
  const titleRefreshSeqRef = useRef(0)

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
    const minLoadedTurnId = minLoadedTurnIdRef.current
    if (minLoadedTurnId !== null && turnId < minLoadedTurnId) return
    if (seenEventIdsRef.current.has(event.seq)) return
    seenEventIdsRef.current.add(event.seq)
    if (event.type === 'stock.selected') {
      if ((selectionSeqRef.current.get(turnId) ?? -1) >= event.seq) return
      selectionSeqRef.current.set(turnId, event.seq)
      const stockCode = normalizeStockCode(String(payload['stock_code'] ?? ''))
      if (!stockCode) return
      setParts((prev) => ({
        ...prev,
        [turnId]: {
          reasoning: prev[turnId]?.reasoning ?? '',
          content: prev[turnId]?.content ?? '',
          tools: prev[turnId]?.tools ?? [],
          runId: prev[turnId]?.runId ?? null,
          stockCode,
        },
      }))
      return
    }
    if (event.type === 'reasoning') {
      setParts((prev) => ({
        ...prev,
        [turnId]: {
          reasoning: (prev[turnId]?.reasoning ?? '') + String(payload['content'] ?? ''),
          content: prev[turnId]?.content ?? '',
          tools: prev[turnId]?.tools ?? [],
          runId: prev[turnId]?.runId ?? null,
          stockCode: prev[turnId]?.stockCode ?? null,
        },
      }))
    } else if (event.type === 'assistant_chunk') {
      setParts((prev) => ({
        ...prev,
        [turnId]: {
          reasoning: prev[turnId]?.reasoning ?? '',
          content: (prev[turnId]?.content ?? '') + String(payload['content'] ?? ''),
          tools: prev[turnId]?.tools ?? [],
          runId: prev[turnId]?.runId ?? null,
          stockCode: prev[turnId]?.stockCode ?? null,
        },
      }))
    } else if (event.type === 'tool_call') {
      setParts((prev) => ({
        ...prev,
        [turnId]: {
          reasoning: prev[turnId]?.reasoning ?? '',
          content: prev[turnId]?.content ?? '',
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
          stockCode: prev[turnId]?.stockCode ?? null,
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
        const summary =
          typeof rawSummary === 'string' ? rawSummary : JSON.stringify(rawSummary)
        if (idx >= 0) {
          tools[idx] = { ...tools[idx], summary }
          if (payload['run_id'])
            tools[idx] = { ...tools[idx], runId: String(payload['run_id']) }
        }
        return {
          ...prev,
          [turnId]: {
            reasoning: prev[turnId]?.reasoning ?? '',
            content: prev[turnId]?.content ?? '',
            tools,
            runId: prev[turnId]?.runId ?? null,
            stockCode: prev[turnId]?.stockCode ?? null,
          },
        }
      })
    } else if (event.type === 'run.linked') {
      const runId = String(payload['run_id'] ?? '')
      setParts((prev) => ({
        ...prev,
        [turnId]: {
          reasoning: prev[turnId]?.reasoning ?? '',
          content: prev[turnId]?.content ?? '',
          tools: prev[turnId]?.tools ?? [],
          runId,
          stockCode: prev[turnId]?.stockCode ?? null,
        },
      }))
      if (runId) {
        setCurrentThread((prev) => (prev ? { ...prev, last_run_id: runId } : prev))
        setThreads((prev) =>
          prev.map((thread) =>
            thread.thread_id === activeThreadRef.current
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
      if (!loadedTurnIdsRef.current.has(turnId)) {
        terminalTurnPatchesRef.current.set(turnId, patch)
      }
      setTurns((prev) =>
        prev.map((turn) => (turn.id === turnId ? { ...turn, ...patch } : turn)),
      )
      setCurrentThread((prev) => (prev ? { ...prev, status: 'idle' } : prev))
    }
  }, [])

  const connectStream = useCallback(
    (threadId: string, lastEventId: number) => {
      streamRef.current?.stop()
      const version = sessionVersionRef.current
      const stream = new ChatEventStream(threadId)
      streamRef.current = stream
      const active = () =>
        sessionVersionRef.current === version &&
        activeThreadRef.current === threadId &&
        streamRef.current === stream
      stream.onEvent = (event) => {
        if (active()) applyEvent(event)
      }
      stream.onStateChange = (state, err) => {
        if (!active()) return
        setStreamState(state)
        if (state === 'error')
          setError(err instanceof Error ? err.message : String(err))
      }
      stream.start(lastEventId)
    },
    [applyEvent],
  )

  const refreshThreads = useCallback(async () => {
    const sequence = ++titleRefreshSeqRef.current
    try {
      const data = await listThreads()
      if (sequence !== titleRefreshSeqRef.current) return
      setThreads(data.threads)
      setCurrentThread((prev) => {
        const updated = data.threads.find((item) => item.thread_id === prev?.thread_id)
        return prev && updated
          ? { ...prev, title: updated.title, title_pending: updated.title_pending }
          : prev
      })
      // An older selected chat can be outside the first page of recent chats.
      const activeId = activeThreadRef.current
      if (
        activeId &&
        currentThreadRef.current?.title_pending &&
        !data.threads.some((item) => item.thread_id === activeId)
      ) {
        const detail = await getThread(activeId, 1)
        if (sequence !== titleRefreshSeqRef.current) return
        setCurrentThread((prev) =>
          prev?.thread_id === activeId
            ? {
                ...prev,
                title: detail.thread.title,
                title_pending: detail.thread.title_pending,
              }
            : prev,
        )
      }
    } catch {
      // 列表失败不阻塞当前会话
    }
  }, [])

  const clearSession = useCallback(() => {
    sessionVersionRef.current += 1
    activeThreadRef.current = null
    const stream = streamRef.current
    streamRef.current = null
    stream?.stop()
    setCurrentThread(null)
    setTurns([])
    setParts({})
    setStreamState('idle')
    setError(null)
    seenEventIdsRef.current.clear()
    selectionSeqRef.current.clear()
    terminalTurnPatchesRef.current.clear()
    loadedTurnIdsRef.current.clear()
    minLoadedTurnIdRef.current = null
    historyOffsetRef.current = 0
    setHasMoreHistory(false)
    return sessionVersionRef.current
  }, [])

  const selectThread = useCallback(
    async (threadId: string): Promise<void> => {
      const version = clearSession()
      activeThreadRef.current = threadId
      try {
        const detail = await getThread(threadId)
        if (sessionVersionRef.current !== version) return
        setCurrentThread(detail.thread)
        setTurns(detail.turns)
        historyOffsetRef.current = detail.turns.length
        setHasMoreHistory(Boolean(detail.has_more))
        loadedTurnIdsRef.current = new Set(detail.turns.map((turn) => turn.id))
        minLoadedTurnIdRef.current = detail.turns.length
          ? Math.min(...detail.turns.map((turn) => turn.id))
          : null
        persistThreadId(threadId)
        connectStream(threadId, 0)
      } catch (exc) {
        if (sessionVersionRef.current === version) setError(getApiErrorMessage(exc))
      }
    },
    [clearSession, connectStream, persistThreadId],
  )

  const newThread = useCallback(async (): Promise<string> => {
    const version = clearSession()
    persistThreadId(null)
    const thread = await createThread()
    if (sessionVersionRef.current !== version) return thread.thread_id
    setThreads((prev) => [thread, ...prev])
    await selectThread(thread.thread_id)
    return thread.thread_id
  }, [clearSession, persistThreadId, selectThread])

  const send = useCallback(
    async (content: string, context?: PageContext): Promise<void> => {
      const text = content.trim()
      if (!text) return
      const version = sessionVersionRef.current
      try {
        if (runtimeStatus && !runtimeStatus.available) {
          setError('Agent 聊天当前不可用，请检查模型配置后重试')
          return
        }
        let thread = currentThread
        if (!thread) {
          const created = await createThread()
          if (sessionVersionRef.current !== version) return
          activeThreadRef.current = created.thread_id
          setThreads((prev) => [created, ...prev])
          setCurrentThread(created)
          minLoadedTurnIdRef.current = null
          loadedTurnIdsRef.current.clear()
          historyOffsetRef.current = 0
          setHasMoreHistory(false)
          thread = created
          persistThreadId(created.thread_id)
          connectStream(created.thread_id, 0)
        }
        const turn = await submitTurn(
          thread.thread_id,
          text,
          newIdempotencyKey(),
          context || contextRef.current,
        )
        if (
          sessionVersionRef.current !== version ||
          activeThreadRef.current !== thread.thread_id
        )
          return
        const terminalPatch = terminalTurnPatchesRef.current.get(turn.id)
        const mergedTurn = terminalPatch ? { ...turn, ...terminalPatch } : turn
        setTurns((prev) => {
          const index = prev.findIndex((item) => item.id === mergedTurn.id)
          if (index < 0) return [...prev, mergedTurn]
          const next = [...prev]
          next[index] = { ...next[index], ...mergedTurn }
          return next
        })
        loadedTurnIdsRef.current.add(mergedTurn.id)
        terminalTurnPatchesRef.current.delete(mergedTurn.id)
        void refreshThreads()
      } catch (exc) {
        if (sessionVersionRef.current === version) setError(getApiErrorMessage(exc))
      }
    },
    [connectStream, currentThread, persistThreadId, refreshThreads, runtimeStatus],
  )

  const stop = useCallback(async (): Promise<void> => {
    if (!currentThread) return
    const version = sessionVersionRef.current
    try {
      const turn = await cancelTurn(currentThread.thread_id)
      if (sessionVersionRef.current !== version) return
      setTurns((prev) => prev.map((t) => (t.id === turn.id ? { ...t, ...turn } : t)))
    } catch (exc) {
      if (sessionVersionRef.current === version) setError(getApiErrorMessage(exc))
    }
  }, [currentThread])

  const archive = useCallback(
    async (threadId: string): Promise<void> => {
      try {
        await archiveThread(threadId)
        titleRefreshSeqRef.current += 1
        setThreads((prev) => prev.filter((t) => t.thread_id !== threadId))
        if (activeThreadRef.current === threadId) {
          clearSession()
          persistThreadId(null)
        }
      } catch (exc) {
        setError(getApiErrorMessage(exc))
      }
    },
    [clearSession, persistThreadId],
  )

  const refreshStatus = useCallback(async (): Promise<void> => {
    try {
      setRuntimeStatus(await getChatStatus())
    } catch {
      setRuntimeStatus(null)
    }
  }, [])

  const loadOlder = useCallback(async (): Promise<void> => {
    if (!currentThread || !hasMoreHistory) return
    const version = sessionVersionRef.current
    try {
      const detail = await getThread(
        currentThread.thread_id,
        100,
        historyOffsetRef.current,
      )
      if (sessionVersionRef.current !== version) return
      setTurns((prev) => {
        const existing = new Set(prev.map((turn) => turn.id))
        return [...detail.turns.filter((turn) => !existing.has(turn.id)), ...prev]
      })
      loadedTurnIdsRef.current = new Set([
        ...detail.turns.map((turn) => turn.id),
        ...loadedTurnIdsRef.current,
      ])
      if (detail.turns.length > 0) {
        minLoadedTurnIdRef.current = Math.min(
          minLoadedTurnIdRef.current ?? detail.turns[0].id,
          detail.turns[0].id,
        )
      }
      historyOffsetRef.current += detail.turns.length
      setHasMoreHistory(Boolean(detail.has_more))
    } catch (exc) {
      if (sessionVersionRef.current === version) setError(getApiErrorMessage(exc))
    }
  }, [currentThread, hasMoreHistory])

  // 刷新后从 URL 中的 thread_id 恢复；只消费一次。
  useEffect(() => {
    void refreshStatus()
  }, [refreshStatus])

  useEffect(() => {
    const id = initialThreadId.current
    if (id) {
      // StrictMode cleans up the first effect before its request resolves.
      // Keep the restore target until selection finishes so the second setup
      // can retry instead of leaving the conversation empty.
      void selectThread(id).then(() => {
        if (activeThreadRef.current === id) {
          initialThreadId.current = null
          void refreshThreads()
        }
      })
    } else {
      void refreshThreads()
    }
  }, [refreshThreads, selectThread])

  useEffect(() => {
    return () => {
      sessionVersionRef.current += 1
      titleRefreshSeqRef.current += 1
      streamRef.current?.stop()
    }
  }, [])

  // 左栏运行状态跟随最新 turn 生命周期刷新（queued/running → 完成/取消）
  const latestTurnStatus = turns.length > 0 ? turns[turns.length - 1].status : null
  useEffect(() => {
    if (!latestTurnStatus) return
    void refreshThreads()
  }, [latestTurnStatus, refreshThreads])

  // Naming runs independently of the chat turn, including historical chats.
  // Refresh until the server has persisted either an AI title or its fallback.
  const hasPendingTitles =
    Boolean(currentThread?.title_pending) ||
    threads.some((thread) => thread.title_pending)
  useEffect(() => {
    if (!hasPendingTitles) return
    let cancelled = false
    let timer: ReturnType<typeof window.setTimeout>
    const poll = async () => {
      await refreshThreads()
      if (!cancelled) timer = window.setTimeout(() => void poll(), 2000)
    }
    timer = window.setTimeout(() => void poll(), 2000)
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [hasPendingTitles, refreshThreads])

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
        content: p && p.content.length > 0 ? p.content : (turn.final_reply ?? ''),
        reasoning: p?.reasoning ?? null,
        tools: p?.tools ?? [],
        status: turn.status,
        runId: p?.runId ?? null,
        error: turn.error,
      })
    }
    return msgs
  }, [parts, turns])

  const stockCode = useMemo(() => {
    const latest = Object.entries(parts)
      .filter(([, part]) => part.stockCode)
      .sort(([left], [right]) => Number(right) - Number(left))[0]
    return latest?.[1].stockCode ?? null
  }, [parts])

  const running = useMemo(
    () => turns.some((t) => t.status === 'queued' || t.status === 'running'),
    [turns],
  )

  return {
    threads,
    currentThread,
    messages,
    stockCode,
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
    loadOlder,
    hasMoreHistory,
  }
}
