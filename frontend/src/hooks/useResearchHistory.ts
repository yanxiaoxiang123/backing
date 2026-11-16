import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { getApiErrorMessage } from '../services/api'
import { syncResearchHistories } from '../services/marketData'
import { normalizeStockCode } from '../utils/stockIdentity'
import { useJobPolling } from './useJobPolling'

interface HistoryReport {
  success: boolean
  errors?: Array<{ stock_code: string; error: string }>
  skipped?: Array<{ stock_code: string; reason: string }>
}

interface Selection {
  codes: string[]
  start: string
  end: string
}
interface Preparation {
  key: string
  status: 'loading' | 'ready' | 'failed'
  progress: number
  error: string
}

function selectionKey(codes: string[], start: string, end: string): string {
  const normalized = [
    ...new Set(codes.map(normalizeStockCode).filter((code): code is string => !!code)),
  ].sort()
  return normalized.length && start && end && start <= end
    ? JSON.stringify({ codes: normalized, start, end })
    : ''
}

const stockKey = (code: string, start: string, end: string) =>
  JSON.stringify([code, start, end])

/** Selection changes stop observing old jobs; their persisted downloads remain reusable. */
export function useResearchHistory(codes: string[], start: string, end: string) {
  const key = selectionKey(codes, start, end)
  const selection = useMemo<Selection | null>(
    () => (key ? JSON.parse(key) : null),
    [key],
  )
  const current = useRef(key)
  current.current = key
  const mounted = useRef(true)
  const ready = useRef(new Set<string>())
  const jobs = useRef(new Map<string, string>())
  const jobMembers = useRef(new Map<string, Set<string>>())
  const submissions = useRef(new Map<string, Promise<string>>())
  const operations = useRef(new Map<string, Promise<void>>())
  const [state, setState] = useState<Preparation | null>(null)
  const { waitForJob, cancel } = useJobPolling<HistoryReport>({ timeoutMs: 3600000 })

  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
    }
  }, [])

  const ensure = useCallback(
    (
      requestedCodes: string[],
      first: string,
      last: string,
      refresh = false,
    ): Promise<void> => {
      const requestKey = selectionKey(requestedCodes, first, last)
      if (!requestKey) return Promise.reject(new Error('请选择股票和有效研究区间'))
      const existing = operations.current.get(requestKey)
      if (existing) return existing
      const request: Selection = JSON.parse(requestKey)
      const active = () => mounted.current && current.current === requestKey
      const check = () => {
        if (!active())
          throw Object.assign(new Error('已切换研究股票或日期'), { code: 'canceled' })
      }
      const update = (status: Preparation['status'], progress = 0, error = '') => {
        if (active()) setState({ key: requestKey, status, progress, error })
      }
      const operation = (async () => {
        check()
        update('loading')
        const stockKeys = request.codes.map((code) => stockKey(code, first, last))
        if (refresh)
          for (const item of stockKeys) {
            ready.current.delete(item)
            jobs.current.delete(item)
          }
        for (const item of stockKeys) {
          const submission = submissions.current.get(item)
          if (submission) jobs.current.set(item, await submission)
        }
        check()
        // A pending batch containing removed securities may fail on those
        // securities. Give the current selection its own result in that case.
        const requested = new Set(stockKeys)
        for (const item of stockKeys) {
          const id = jobs.current.get(item)
          const members = id ? jobMembers.current.get(id) : undefined
          if (
            !ready.current.has(item) &&
            members &&
            [...members].some((member) => !requested.has(member))
          ) {
            jobs.current.delete(item)
          }
        }
        const missing = request.codes.filter((code) => {
          const item = stockKey(code, first, last)
          return !ready.current.has(item) && !jobs.current.has(item)
        })
        if (missing.length) {
          const submission = syncResearchHistories(missing, first, last)
          for (const code of missing)
            submissions.current.set(stockKey(code, first, last), submission)
          try {
            const jobId = await submission
            jobMembers.current.set(
              jobId,
              new Set(missing.map((code) => stockKey(code, first, last))),
            )
            for (const code of missing)
              jobs.current.set(stockKey(code, first, last), jobId)
          } finally {
            for (const code of missing) {
              const item = stockKey(code, first, last)
              if (submissions.current.get(item) === submission)
                submissions.current.delete(item)
            }
          }
        }
        check()
        const jobIds = [
          ...new Set(
            stockKeys
              .filter((item) => !ready.current.has(item))
              .map((item) => jobs.current.get(item)!),
          ),
        ]
        for (const [index, jobId] of jobIds.entries()) {
          check()
          let lastReport: HistoryReport | undefined
          try {
            const report = await waitForJob(jobId, {
              onStatus: (job) => {
                lastReport = job.result
                update(
                  'loading',
                  Math.round(
                    ((index + Math.max(0, Math.min(job.progress || 0, 1))) /
                      jobIds.length) *
                      100,
                  ),
                )
              },
            })
            check()
            if (!report?.success) throw new Error('行情或分红数据仍不完整，请重试获取')
            if (report.skipped?.length)
              throw new Error(
                `${report.skipped[0].stock_code} 在所选区间没有可用上市行情，请调整日期`,
              )
            for (const [item, id] of jobs.current)
              if (id === jobId) ready.current.add(item)
          } catch (cause) {
            if ((cause as { code?: string }).code !== 'canceled') {
              for (const [item, id] of jobs.current)
                if (id === jobId) jobs.current.delete(item)
            }
            const detail = lastReport?.errors?.[0]
            if (detail)
              throw new Error(`${detail.stock_code} 数据获取失败：${detail.error}`)
            throw cause
          }
        }
        check()
        update('ready', 100)
      })()
        .catch((cause) => {
          if ((cause as { code?: string }).code !== 'canceled')
            update('failed', 0, getApiErrorMessage(cause))
          throw cause
        })
        .finally(() => {
          if (operations.current.get(requestKey) === operation)
            operations.current.delete(requestKey)
        })
      operations.current.set(requestKey, operation)
      return operation
    },
    [waitForJob],
  )

  useEffect(() => {
    if (!selection) return
    const timer = setTimeout(() => {
      void ensure(selection.codes, selection.start, selection.end).catch(() => {})
    }, 350)
    return () => {
      clearTimeout(timer)
      cancel()
    }
  }, [selection, ensure, cancel])

  const currentState = state?.key === key ? state : null
  return {
    selectionKey: key,
    ensure,
    status: selection ? (currentState?.status ?? 'loading') : 'idle',
    progress: currentState?.progress ?? 0,
    error: currentState?.error ?? '',
    retry: () =>
      selection &&
      ensure(selection.codes, selection.start, selection.end, true).catch(() => {}),
  }
}
