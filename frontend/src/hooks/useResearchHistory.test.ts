import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useResearchHistory } from './useResearchHistory'
import { syncResearchHistories } from '../services/marketData'

const polling = vi.hoisted(() => ({ waitForJob: vi.fn(), cancel: vi.fn() }))
vi.mock('./useJobPolling', () => ({ useJobPolling: () => polling }))
vi.mock('../services/marketData', () => ({ syncResearchHistories: vi.fn() }))
vi.mock('../services/api', () => ({
  getApiErrorMessage: (error: Error) => error.message,
}))

const first = '2025-01-01',
  last = '2025-12-31'
const advance = () =>
  act(async () => {
    await vi.advanceTimersByTimeAsync(350)
  })

describe('automatic research history', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.resetAllMocks()
    vi.mocked(syncResearchHistories).mockResolvedValue('job')
    polling.waitForJob.mockResolvedValue({ success: true })
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it('fetches only selected stocks for the chosen dates and reuses completed data', async () => {
    const { result, rerender } = renderHook(
      ({ codes }) => useResearchHistory(codes, first, last),
      { initialProps: { codes: ['600000'] } },
    )
    await advance()
    expect(syncResearchHistories).toHaveBeenCalledWith(['sh.600000'], first, last)
    expect(result.current.status).toBe('ready')
    rerender({ codes: ['sh.600000', '000001', 'sh.600000'] })
    await advance()
    expect(syncResearchHistories).toHaveBeenLastCalledWith(['sz.000001'], first, last)
    expect(result.current.status).toBe('ready')
  })

  it('debounces selection changes and ignores an obsolete completion', async () => {
    let completeOld!: (report: { success: boolean }) => void
    polling.waitForJob.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          completeOld = resolve
        }),
    )
    const { result, rerender } = renderHook(
      ({ code }) => useResearchHistory([code], first, last),
      { initialProps: { code: '600000' } },
    )
    await advance()
    rerender({ code: '600004' })
    rerender({ code: '000001' })
    await advance()
    expect(syncResearchHistories).toHaveBeenCalledTimes(2)
    expect(syncResearchHistories).toHaveBeenLastCalledWith(['sz.000001'], first, last)
    expect(polling.cancel).toHaveBeenCalled()
    expect(result.current.status).toBe('ready')
    await act(async () => {
      completeOld({ success: false })
    })
    expect(result.current.status).toBe('ready')
    expect(result.current.error).toBe('')
  })

  it('fetches again when the period changes and supports an explicit retry', async () => {
    const { result, rerender } = renderHook(
      ({ end }) => useResearchHistory(['600000'], first, end),
      { initialProps: { end: last } },
    )
    await advance()
    rerender({ end: '2026-01-30' })
    await advance()
    expect(syncResearchHistories).toHaveBeenLastCalledWith(
      ['sh.600000'],
      first,
      '2026-01-30',
    )
    await act(async () => {
      await result.current.retry()
    })
    expect(syncResearchHistories).toHaveBeenCalledTimes(3)
  })

  it('never marks incomplete or failed downloads ready', async () => {
    polling.waitForJob.mockResolvedValueOnce({ success: false })
    const { result } = renderHook(() => useResearchHistory(['600000'], first, last))
    await advance()
    expect(result.current.status).toBe('failed')
    expect(result.current.error).toContain('不完整')
    await act(async () => {
      await result.current.retry()
    })
    expect(result.current.status).toBe('ready')
  })

  it('reuses a submitted job when its HTTP response arrives after a selection change', async () => {
    let submitted!: (id: string) => void
    vi.mocked(syncResearchHistories).mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          submitted = resolve
        }),
    )
    const { result, rerender } = renderHook(
      ({ codes }) => useResearchHistory(codes, first, last),
      { initialProps: { codes: ['600000'] } },
    )
    await advance()
    rerender({ codes: ['600000', '000001'] })
    await advance()
    expect(syncResearchHistories).toHaveBeenCalledTimes(1)
    await act(async () => submitted('first-job'))
    expect(syncResearchHistories).toHaveBeenCalledTimes(2)
    expect(syncResearchHistories).toHaveBeenLastCalledWith(['sz.000001'], first, last)
    expect(result.current.status).toBe('ready')
  })

  it('does not submit incomplete selections or fetch after unmount', async () => {
    const { result, rerender, unmount } = renderHook(
      ({ codes }) => useResearchHistory(codes, first, last),
      { initialProps: { codes: [] as string[] } },
    )
    await advance()
    expect(result.current.status).toBe('idle')
    expect(syncResearchHistories).not.toHaveBeenCalled()
    rerender({ codes: ['600000'] })
    unmount()
    await advance()
    expect(syncResearchHistories).not.toHaveBeenCalled()
  })

  it('does not let removed securities in an old batch fail the remaining selection', async () => {
    let completeOld!: (report: { success: boolean }) => void
    polling.waitForJob.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          completeOld = resolve
        }),
    )
    vi.mocked(syncResearchHistories)
      .mockResolvedValueOnce('old-batch')
      .mockResolvedValueOnce('new-selection')
    const { result, rerender } = renderHook(
      ({ codes }) => useResearchHistory(codes, first, last),
      { initialProps: { codes: ['600000', '000001'] } },
    )
    await advance()
    rerender({ codes: ['000001'] })
    await advance()
    expect(syncResearchHistories).toHaveBeenLastCalledWith(['sz.000001'], first, last)
    await act(async () => completeOld({ success: false }))
    expect(result.current.status).toBe('ready')
    expect(result.current.error).toBe('')
  })
})
