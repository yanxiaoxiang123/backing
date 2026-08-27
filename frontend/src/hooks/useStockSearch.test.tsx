import { act, renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { getStocks } from '../services/stocks'
import { useStockSearch } from './useStockSearch'

vi.mock('../services/stocks', () => ({ getStocks: vi.fn() }))

const mockedGetStocks = vi.mocked(getStocks)

function createWrapper() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: 1, retryDelay: 10 } },
  })
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>
  }
}

describe('useStockSearch', () => {
  beforeEach(() => {
    localStorage.clear()
    mockedGetStocks.mockReset()
  })

  it('debounces input and uses the server result', async () => {
    mockedGetStocks.mockResolvedValue({
      items: [
        {
          id: 1,
          code: 'sh.600000',
          name: '浦发银行',
          market: 'sh',
          created_at: '2026-08-27T00:00:00Z',
        },
      ],
      total: 1,
      nextCursor: null,
    })

    const { result } = renderHook(() => useStockSearch(), {
      wrapper: createWrapper(),
    })
    act(() => result.current.setQuery('600000'))

    await waitFor(() =>
      expect(mockedGetStocks).toHaveBeenCalledWith(undefined, 0, 50, '600000'),
    )
    expect(result.current.search('600000')).toEqual([
      { code: 'sh.600000', name: '浦发银行', label: 'sh.600000 - 浦发银行' },
    ])
  })

  it('retries a transient search failure and keeps recent selections', async () => {
    mockedGetStocks
      .mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValueOnce({ items: [], total: 0, nextCursor: null })

    const { result } = renderHook(() => useStockSearch(), {
      wrapper: createWrapper(),
    })
    act(() =>
      result.current.trackSelection({
        code: 'SH600000',
        name: '浦发银行',
        label: 'SH600000 - 浦发银行',
      }),
    )
    expect(result.current.search('')).toEqual([
      {
        code: 'sh.600000',
        name: '浦发银行',
        label: 'SH600000 - 浦发银行',
        isRecent: true,
      },
    ])

    act(() => result.current.setQuery('浦发'))
    await waitFor(() => expect(mockedGetStocks).toHaveBeenCalledTimes(2))
    expect(result.current.error).toBeNull()
  })
})
