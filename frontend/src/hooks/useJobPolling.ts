import { useCallback, useEffect, useRef, useState } from 'react'
import { getJobStatus } from '../services/api'
import type { JobStatus } from '../types'

export interface JobPollingOptions {
  /** Base polling interval in ms (default 1500). */
  intervalMs?: number
  /** Hard timeout for `waitForJob` in ms; `0` disables (default 10 min). */
  timeoutMs?: number
  /** Cap for exponential backoff on transient request errors (default 15000). */
  maxIntervalMs?: number
}

export interface WaitJobOptions<T> {
  /** Called with the latest job status on every poll. */
  onStatus?: (job: JobStatus<T>) => void
}

export interface JobPollingError extends Error {
  code: 'timeout' | 'canceled' | 'failed' | 'unknown_status'
  jobId?: string
}

function jobError(
  message: string,
  code: JobPollingError['code'],
  jobId?: string,
): JobPollingError {
  const err = new Error(message) as JobPollingError
  err.code = code
  err.jobId = jobId
  return err
}

/**
 * Polls a backend job (via `GET /jobs/{id}`) until it completes, fails, or a
 * hard timeout is reached.
 *
 * - **Cancellation / unmount cleanup**: the active poll is aborted on unmount
 *   (and via the returned `cancel()`), rejecting the pending promise with
 *   `code === 'canceled'` — no setState after unmount, no leaked timers.
 * - **Exponential backoff**: transient network failures double the interval up
 *   to `maxIntervalMs`; a successful poll resets it.
 * - **State**: `isPolling` and `lastStatus` are exposed so pages can render
 *   progress and re-enable actions.
 */
export function useJobPolling<T = Record<string, unknown>>(
  options: JobPollingOptions = {},
) {
  const { intervalMs = 1500, timeoutMs = 600000, maxIntervalMs = 15000 } = options

  const controllerRef = useRef<AbortController | null>(null)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const mountedRef = useRef(true)
  const intervalRef = useRef(intervalMs)

  const [isPolling, setIsPolling] = useState(false)
  // waitForJob 支持按调用指定返回类型，这里用 unknown 兜底记录最近一次状态
  const [lastStatus, setLastStatus] = useState<JobStatus<unknown> | null>(null)

  const clearTimer = useCallback(() => {
    if (timerRef.current !== null) {
      clearTimeout(timerRef.current)
      timerRef.current = null
    }
  }, [])

  const stop = useCallback(() => {
    clearTimer()
    controllerRef.current?.abort()
    controllerRef.current = null
    setIsPolling(false)
  }, [clearTimer])

  // Abort any in-flight poll when the component unmounts.
  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      stop()
    }
  }, [stop])

  const waitForJob = useCallback(
    async <TResult = T>(
      jobId: string,
      waitOptions: WaitJobOptions<TResult> = {},
    ): Promise<TResult> => {
      stop() // never run two polls at once

      const controller = new AbortController()
      controllerRef.current = controller
      intervalRef.current = intervalMs
      setLastStatus(null)
      setIsPolling(true)

      const deadline = timeoutMs > 0 ? Date.now() + timeoutMs : 0

      // Resolves on timeout *or* abort, so the loop can re-check both.
      const sleep = (ms: number) =>
        new Promise<void>((resolve) => {
          const onAbort = () => {
            if (timerRef.current === timer) {
              clearTimer()
            }
            resolve()
          }
          const timer = setTimeout(() => {
            controller.signal.removeEventListener('abort', onAbort)
            timerRef.current = null
            resolve()
          }, ms)
          timerRef.current = timer
          controller.signal.addEventListener('abort', onAbort, { once: true })
        })

      try {
        while (true) {
          if (controller.signal.aborted) {
            throw jobError('任务轮询已取消', 'canceled', jobId)
          }
          if (deadline && Date.now() > deadline) {
            throw jobError('任务超时，请稍后重试', 'timeout', jobId)
          }

          let job: JobStatus<TResult>
          try {
            job = await getJobStatus<TResult>(jobId, controller.signal)
          } catch (error) {
            if (controller.signal.aborted) {
              throw jobError('任务轮询已取消', 'canceled', jobId)
            }
            if (deadline && Date.now() > deadline) {
              throw jobError('任务超时，请稍后重试', 'timeout', jobId)
            }
            // Fail fast on client errors (e.g. 404: job gone); transient
            // network / server errors back off and retry.
            const status = (error as { response?: { status?: number } } | undefined)
              ?.response?.status
            if (status !== undefined && status < 500) {
              throw error
            }
            if (!mountedRef.current) {
              throw jobError('组件已卸载', 'canceled', jobId)
            }
            // Transient failure: back off and retry.
            intervalRef.current = Math.min(intervalRef.current * 2, maxIntervalMs)
            await sleep(intervalRef.current)
            continue
          }

          intervalRef.current = intervalMs // success resets the backoff
          if (!mountedRef.current) {
            throw jobError('组件已卸载', 'canceled', jobId)
          }

          setLastStatus(job)
          waitOptions.onStatus?.(job)

          if (job.status === 'completed') {
            return job.result as TResult
          }
          if (job.status === 'failed') {
            throw jobError(job.error || job.message || '任务执行失败', 'failed', jobId)
          }
          if (!['pending', 'running', 'queued'].includes(job.status)) {
            throw jobError(`未知任务状态: ${job.status}`, 'unknown_status', jobId)
          }
          await sleep(intervalRef.current)
        }
      } finally {
        if (controllerRef.current === controller) {
          controllerRef.current = null
          setIsPolling(false)
        }
      }
    },
    [intervalMs, maxIntervalMs, stop, timeoutMs],
  )

  return { waitForJob, isPolling, lastStatus, cancel: stop }
}
