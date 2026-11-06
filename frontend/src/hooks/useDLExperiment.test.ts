import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, expect, it, vi } from 'vitest'
import { useDLExperiment } from './useDLExperiment'
import { cancelJob, getJobStatus } from '../services/api'
import { submitDLExperiment } from '../services/dl'

vi.mock('../services/api', () => ({
  cancelJob: vi.fn(),
  getJobStatus: vi.fn(),
  getApiErrorMessage: (error: Error) => error.message,
}))
vi.mock('../services/dl', () => ({ submitDLExperiment: vi.fn() }))

const request = {
  model: 'kronos-small' as const,
  stock_code: 'sh.600000',
  kline_days: 256,
  prediction_days: 5,
}
const complete = {
  id: 'job',
  job_type: 'dl_predict',
  status: 'completed' as const,
  progress: 1,
  message: '实验完成',
  payload: request,
  created_at: '',
  updated_at: '',
  result: { success: true, data: { stock_code: 'sh.600000', predicted_prices: [11] } },
}

beforeEach(() => {
  sessionStorage.clear()
  vi.clearAllMocks()
  vi.mocked(submitDLExperiment).mockResolvedValue({
    job_id: 'job',
    status: 'pending',
    message: 'queued',
  })
  vi.mocked(getJobStatus).mockResolvedValue(complete as never)
})

it('submits a stable experiment, persists the job and restores its result on remount', async () => {
  const first = renderHook(() => useDLExperiment())
  act(() => first.result.current.start('predict', request))
  await waitFor(() => expect(first.result.current.result).not.toBeNull())
  expect(submitDLExperiment).toHaveBeenCalledTimes(1)
  expect(JSON.parse(sessionStorage.getItem('backing_dl_experiment')!).jobId).toBe('job')
  first.unmount()
  const restored = renderHook(() => useDLExperiment())
  await waitFor(() => expect(restored.result.current.result?.request).toEqual(request))
  expect(submitDLExperiment).toHaveBeenCalledTimes(1)
})

it('does not display a successful late GPU response after cancellation', async () => {
  let resolveStatus!: (value: unknown) => void
  vi.mocked(getJobStatus).mockImplementation(
    () =>
      new Promise((resolve) => {
        resolveStatus = resolve
      }) as never,
  )
  const hook = renderHook(() => useDLExperiment())
  act(() => hook.result.current.start('predict', request))
  await waitFor(() => expect(getJobStatus).toHaveBeenCalled())
  await act(async () => {
    await hook.result.current.cancel()
  })
  expect(cancelJob).toHaveBeenCalledWith('job')
  await act(async () => {
    resolveStatus(complete)
  })
  await waitFor(() => expect(hook.result.current.running).toBe(false))
  expect(hook.result.current.result).toBeNull()
  expect(hook.result.current.error).toBe('任务已取消')
})

it('does not overwrite a newer experiment with a late submission from an unmounted page', async () => {
  let finishOldSubmission!: (value: unknown) => void
  vi.mocked(submitDLExperiment).mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        finishOldSubmission = resolve
      }) as never,
  )
  const old = renderHook(() => useDLExperiment())
  act(() => old.result.current.start('predict', request))
  await waitFor(() => expect(submitDLExperiment).toHaveBeenCalledTimes(1))
  old.unmount()
  const restored = renderHook(() => useDLExperiment())
  await waitFor(() => expect(restored.result.current.running).toBe(false))
  act(() =>
    restored.result.current.start('predict', { ...request, model: 'kronos-base' }),
  )
  await waitFor(() =>
    expect(restored.result.current.result?.request.model).toBe('kronos-base'),
  )
  const current = sessionStorage.getItem('backing_dl_experiment')
  await act(async () => {
    finishOldSubmission({ job_id: 'old-job', status: 'pending', message: 'queued' })
  })
  expect(sessionStorage.getItem('backing_dl_experiment')).toBe(current)
})

it('retries a lost submission after reload with the original idempotency key', async () => {
  sessionStorage.setItem(
    'backing_dl_experiment',
    JSON.stringify({
      request,
      kind: 'predict',
      key: 'original-key',
    }),
  )
  const restored = renderHook(() => useDLExperiment())
  await waitFor(() => expect(restored.result.current.result).not.toBeNull())
  expect(submitDLExperiment).toHaveBeenCalledWith('predict', request, 'original-key')
})

it('shows a model failure without inventing a successful result', async () => {
  vi.mocked(getJobStatus).mockResolvedValue({
    ...complete,
    status: 'failed',
    error: '远程 GPU 显存不足',
  } as never)
  const hook = renderHook(() => useDLExperiment())
  act(() => hook.result.current.start('predict', request))
  await waitFor(() => expect(hook.result.current.error).toContain('显存不足'))
  expect(hook.result.current.result).toBeNull()
})

it('keeps real completion timestamps and reads history without submitting again', async () => {
  vi.mocked(getJobStatus).mockResolvedValue({
    ...complete,
    updated_at: '2026-11-05T04:34:53.821802',
  } as never)
  const hook = renderHook(() => useDLExperiment())
  act(() => hook.result.current.start('predict', request))
  await waitFor(() => expect(hook.result.current.history).toHaveLength(1))
  expect(hook.result.current.result?.completedAt).toBe('2026-11-05T04:34:53.821802Z')
  const entry = hook.result.current.history[0]
  act(() => hook.result.current.openHistory(entry))
  await waitFor(() => expect(hook.result.current.running).toBe(false))
  expect(submitDLExperiment).toHaveBeenCalledTimes(1)
  expect(hook.result.current.history).toHaveLength(1)
  expect(hook.result.current.results.predict?.request).toEqual(request)
})

it('retains the previous forecast when a backtest finishes', async () => {
  const hook = renderHook(() => useDLExperiment())
  act(() => hook.result.current.start('predict', request))
  await waitFor(() => expect(hook.result.current.running).toBe(false))
  act(() =>
    hook.result.current.start('backtest', {
      ...request,
      start_date: '2025-11-05',
      end_date: '2026-11-05',
      initial_capital: 200000,
    }),
  )
  await waitFor(() => expect(hook.result.current.result?.kind).toBe('backtest'))
  expect(hook.result.current.results.predict?.response).toEqual(complete.result)
  expect(hook.result.current.results.backtest?.request.initial_capital).toBe(200000)
})
