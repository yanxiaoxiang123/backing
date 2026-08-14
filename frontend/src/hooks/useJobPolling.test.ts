import { describe, expect, it, vi, beforeEach } from 'vitest'
import { act, renderHook } from '@testing-library/react'
import { useJobPolling } from './useJobPolling'

vi.mock('../services/api', () => ({
  getJobStatus: vi.fn()
}))

import { getJobStatus } from '../services/api'

const mockedGetJobStatus = vi.mocked(getJobStatus)

function jobStatus(partial: Record<string, unknown>) {
  return partial as never
}

describe('useJobPolling', () => {
  beforeEach(() => {
    mockedGetJobStatus.mockReset()
  })

  it('任务完成后返回 result', async () => {
    mockedGetJobStatus
      .mockResolvedValueOnce(jobStatus({ status: 'running', progress: 0.5 }))
      .mockResolvedValueOnce(jobStatus({ status: 'completed', result: { ok: true } }))

    const { result } = renderHook(() => useJobPolling<{ ok: boolean }>({ intervalMs: 5 }))
    let promise: Promise<{ ok: boolean }>
    act(() => {
      promise = result.current.waitForJob('job-1')
    })
    await expect(promise!).resolves.toEqual({ ok: true })
    expect(mockedGetJobStatus).toHaveBeenCalledWith('job-1', expect.any(AbortSignal))
  })

  it('任务失败时抛出 failed 错误', async () => {
    mockedGetJobStatus.mockResolvedValueOnce(
      jobStatus({ status: 'failed', error: '模型异常' })
    )

    const { result } = renderHook(() => useJobPolling({ intervalMs: 5 }))
    let promise: Promise<never>
    act(() => {
      promise = result.current.waitForJob('job-2')
    })
    await expect(promise!).rejects.toMatchObject({ message: '模型异常', code: 'failed' })
  })

  it('超过 timeoutMs 后抛出 timeout 错误', async () => {
    mockedGetJobStatus.mockResolvedValue(jobStatus({ status: 'running' }))

    const { result } = renderHook(() => useJobPolling({ intervalMs: 5, timeoutMs: 40 }))
    let promise: Promise<never>
    act(() => {
      promise = result.current.waitForJob('job-3')
    })
    await expect(promise!).rejects.toMatchObject({ code: 'timeout' })
  })

  it('卸载时取消轮询并拒绝 pending promise', async () => {
    mockedGetJobStatus.mockResolvedValue(jobStatus({ status: 'running' }))

    const { result, unmount } = renderHook(() => useJobPolling({ intervalMs: 1000 }))
    let promise: Promise<never>
    act(() => {
      promise = result.current.waitForJob('job-4')
    })
    // 先挂上拒绝处理器，避免卸载瞬间产生 unhandled rejection
    const assertion = expect(promise!).rejects.toMatchObject({ code: 'canceled' })
    await act(async () => {
      unmount()
    })
    await assertion
  })

  it('网络抖动（瞬时错误）退避重试后仍能完成', async () => {
    mockedGetJobStatus
      .mockRejectedValueOnce(new Error('Network Error'))
      .mockRejectedValueOnce(new Error('Network Error'))
      .mockResolvedValueOnce(jobStatus({ status: 'completed', result: 42 }))

    const { result } = renderHook(() => useJobPolling<number>({ intervalMs: 5, maxIntervalMs: 10 }))
    let promise: Promise<number>
    act(() => {
      promise = result.current.waitForJob('job-5')
    })
    await expect(promise!).resolves.toBe(42)
  })

  it('4xx 快速失败，不做无限重试', async () => {
    const notFound = new Error('Request failed with status code 404') as Error & {
      response?: { status: number }
    }
    notFound.response = { status: 404 }
    mockedGetJobStatus.mockRejectedValue(notFound)

    const { result } = renderHook(() => useJobPolling({ intervalMs: 5, timeoutMs: 2000 }))
    let promise: Promise<never>
    act(() => {
      promise = result.current.waitForJob('job-6')
    })
    await expect(promise!).rejects.toMatchObject({ message: 'Request failed with status code 404' })
    // 只请求了一次，没有重试
    expect(mockedGetJobStatus).toHaveBeenCalledTimes(1)
  })
})
