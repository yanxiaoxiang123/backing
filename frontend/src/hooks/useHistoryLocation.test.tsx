import type { ReactNode } from 'react'
import { act, renderHook } from '@testing-library/react'
import { MemoryRouter, useNavigate, useLocation } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useHistoryLocation } from './useHistoryLocation'

function setup(path: string) {
  const wrapper = ({ children }: { children: ReactNode }) => (
    <MemoryRouter
      initialEntries={[path]}
      future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
    >
      {children}
    </MemoryRouter>
  )
  return renderHook(
    () => ({
      ...useHistoryLocation(),
      navigate: useNavigate(),
      search: useLocation().search,
    }),
    { wrapper },
  )
}

afterEach(() => vi.useRealTimers())

describe('history URL state', () => {
  it('restores filtered pagination and selected detail without resetting page on mount', async () => {
    vi.useFakeTimers()
    const { result } = setup(
      '/history?stock=sh.600000&strategy=ma_cross&page=3&page_size=10&sort=return&result=42&source=research',
    )
    await act(() => vi.advanceTimersByTimeAsync(500))
    expect(result.current).toMatchObject({
      stock: 'sh.600000',
      strategy: 'ma_cross',
      page: 3,
      pageSize: 10,
      sort: 'return',
      selectedId: 42,
    })
    expect(result.current.scrollKey).not.toContain('result=')
    act(() => result.current.update({ result: null }, true))
    expect(result.current.page).toBe(3)
    expect(result.current.search).toContain('source=research')
  })
  it('debounces typed filters, resets pagination and restores URL and inputs on back navigation', async () => {
    vi.useFakeTimers()
    const { result } = setup('/history?stock=sh.600000&page=2')
    act(() => result.current.setStockInput('600036'))
    await act(() => vi.advanceTimersByTimeAsync(299))
    expect(result.current.page).toBe(2)
    await act(() => vi.advanceTimersByTimeAsync(1))
    expect(result.current.stock).toBe('600036')
    expect(result.current.page).toBe(1)
    act(() => result.current.update({ page: 2 }))
    expect(result.current.page).toBe(2)
    act(() => result.current.navigate(-1))
    await act(() => vi.advanceTimersByTimeAsync(500))
    expect(result.current.page).toBe(1)
    expect(result.current.stockInput).toBe('600036')
  })
  it('ignores malformed URL parameters and restores different inputs on back navigation', async () => {
    vi.useFakeTimers()
    const { result } = setup(
      '/history?page=-1&page_size=7&result=not-an-id&sort=unknown&stock=600000',
    )
    expect(result.current).toMatchObject({
      page: 1,
      pageSize: 20,
      selectedId: null,
      sort: 'newest',
    })
    act(() => result.current.navigate('/history?stock=600036&page=2'))
    await act(() => vi.advanceTimersByTimeAsync(500))
    expect(result.current.stockInput).toBe('600036')
    expect(result.current.page).toBe(2)
    act(() => result.current.navigate(-1))
    await act(() => vi.advanceTimersByTimeAsync(500))
    expect(result.current.stockInput).toBe('600000')
    expect(result.current.stock).toBe('600000')
  })
})
