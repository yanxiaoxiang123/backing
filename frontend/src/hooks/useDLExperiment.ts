import { useCallback, useEffect, useRef, useState } from 'react'
import { cancelJob, getApiErrorMessage } from '../services/api'
import {
  submitDLExperiment,
  type DLExperimentKind,
  type DLExperimentRequest,
  type DLJobResult,
} from '../services/dl'
import { useJobPolling } from './useJobPolling'

const STORAGE_KEY = 'backing_dl_experiment'
const HISTORY_KEY = 'backing_dl_history'
interface SavedExperiment {
  kind: DLExperimentKind
  request: DLExperimentRequest
  key: string
  jobId?: string
}

export interface DLExperimentHistory extends SavedExperiment {
  jobId: string
  completedAt?: string
}

export interface DLExperimentResult {
  kind: DLExperimentKind
  request: DLExperimentRequest
  response: DLJobResult
  jobId?: string
  completedAt?: string
}

function restoreHistory(): DLExperimentHistory[] {
  try {
    const items: unknown = JSON.parse(sessionStorage.getItem(HISTORY_KEY) || '[]')
    return Array.isArray(items)
      ? items
          .filter(
            (item): item is DLExperimentHistory =>
              item &&
              ['predict', 'backtest'].includes(item.kind) &&
              typeof item.jobId === 'string' &&
              typeof item.key === 'string' &&
              item.request,
          )
          .slice(0, 20)
      : []
  } catch {
    return []
  }
}

function restore(): SavedExperiment | null {
  try {
    const value = JSON.parse(sessionStorage.getItem(STORAGE_KEY) || 'null')
    return value &&
      ['predict', 'backtest'].includes(value.kind) &&
      value.key &&
      value.request
      ? value
      : null
  } catch {
    return null
  }
}

export function useDLExperiment() {
  const [saved, setSaved] = useState<SavedExperiment | null>(restore)
  const [running, setRunning] = useState(Boolean(saved))
  const [result, setResult] = useState<DLExperimentResult | null>(null)
  const [results, setResults] = useState<
    Partial<Record<DLExperimentKind, DLExperimentResult>>
  >({})
  const [history, setHistory] = useState(restoreHistory)
  const [error, setError] = useState<string | null>(null)
  const mounted = useRef(true)
  const active = useRef<SavedExperiment | null>(saved)
  const cancelling = useRef(false)
  const generation = useRef(0)
  const { waitForJob, lastStatus } = useJobPolling<DLJobResult>({
    timeoutMs: 4 * 60 * 60_000,
  })

  const observe = useCallback(
    async (record: SavedExperiment) => {
      const ticket = ++generation.current
      const current = () => mounted.current && ticket === generation.current
      active.current = record
      if (mounted.current) {
        setRunning(true)
        setError(null)
        setSaved(record)
      }
      try {
        if (!record.jobId) {
          const submission = await submitDLExperiment(
            record.kind,
            record.request,
            record.key,
          )
          record = { ...record, jobId: submission.job_id }
          if (!current()) return
          sessionStorage.setItem(STORAGE_KEY, JSON.stringify(record))
          active.current = record
          setSaved(record)
        }
        if (cancelling.current) await cancelJob(record.jobId!)
        if (!current()) return
        let completedAt: string | undefined
        const response = await waitForJob(record.jobId!, {
          onStatus: (job) => {
            if (job.status === 'completed' && job.updated_at) {
              // The job store serializes UTC datetimes without an offset.
              completedAt = /(?:Z|[+-]\d{2}:\d{2})$/i.test(job.updated_at)
                ? job.updated_at
                : `${job.updated_at}Z`
            }
          },
        })
        if (current() && active.current?.key === record.key) {
          if (cancelling.current) {
            setError('任务已取消')
            return
          }
          if (!response?.success || !response.data)
            throw new Error('实验未返回有效结果')
          const next = {
            kind: record.kind,
            request: record.request,
            response,
            jobId: record.jobId,
            completedAt,
          }
          setResult(next)
          setResults((previous) => ({ ...previous, [record.kind]: next }))
          setHistory((previous) => {
            const entry = { ...record, jobId: record.jobId!, completedAt }
            const entries = [
              entry,
              ...previous.filter((item) => item.jobId !== entry.jobId),
            ].slice(0, 20)
            try {
              sessionStorage.setItem(HISTORY_KEY, JSON.stringify(entries))
            } catch {
              // History is optional; a full session store must not hide a result.
            }
            return entries
          })
        }
      } catch (cause) {
        if (current() && active.current?.key === record.key) {
          const message = getApiErrorMessage(cause)
          setError(
            cancelling.current || message === 'Cancelled' ? '任务已取消' : message,
          )
        }
      } finally {
        if (current() && active.current?.key === record.key) setRunning(false)
      }
    },
    [waitForJob],
  )

  useEffect(() => {
    mounted.current = true
    const record = restore()
    if (record) void observe(record)
    return () => {
      mounted.current = false
      generation.current += 1
    }
  }, [observe])

  const start = useCallback(
    (kind: DLExperimentKind, request: DLExperimentRequest) => {
      if (running) return
      const record = { kind, request, key: crypto.randomUUID() }
      cancelling.current = false
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(record))
      void observe(record)
    },
    [observe, running],
  )

  const cancel = useCallback(async () => {
    cancelling.current = true
    try {
      if (active.current?.jobId) await cancelJob(active.current.jobId)
    } catch (cause) {
      cancelling.current = false
      if (mounted.current) setError(getApiErrorMessage(cause))
    }
  }, [])

  const openHistory = useCallback(
    (entry: DLExperimentHistory) => {
      if (running) return
      cancelling.current = false
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(entry))
      void observe(entry)
    },
    [observe, running],
  )

  return {
    start,
    cancel,
    running,
    saved,
    result,
    results,
    history,
    openHistory,
    error,
    lastStatus,
  }
}
