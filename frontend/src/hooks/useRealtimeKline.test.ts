import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { getRealtimeBars } from '../services/api'
import { mergeRealtimeBars, useRealtimeKline } from './useRealtimeKline'

vi.mock('../services/api', () => ({ getRealtimeBars: vi.fn() }))

const mockedGetRealtimeBars = vi.mocked(getRealtimeBars)

class MockWebSocket {
  static instances: MockWebSocket[] = []

  readonly url: string
  onopen: (() => void) | null = null
  onmessage: ((event: { data: string }) => void) | null = null
  onerror: (() => void) | null = null
  onclose: (() => void) | null = null
  close = vi.fn()

  constructor(url: string) {
    this.url = url
    MockWebSocket.instances.push(this)
  }
}

beforeEach(() => {
  MockWebSocket.instances = []
  mockedGetRealtimeBars.mockReset()
  vi.stubGlobal('WebSocket', MockWebSocket)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('mergeRealtimeBars', () => {
  it('updates an existing date and appends new bars in chronological order', () => {
    const result = mergeRealtimeBars(
      [{ date: '2026-08-14', open: 10, high: 11, low: 9, close: 10, volume: 10 }],
      [
        {
          date: '2026-08-14',
          open: 10,
          high: 12,
          low: 9,
          close: 11,
          volume: 20,
          amount: 200,
        },
        {
          date: '2026-08-15',
          open: 11,
          high: 12,
          low: 10,
          close: 11.5,
          volume: 30,
          amount: 300,
        },
      ],
    )

    expect(result).toHaveLength(2)
    expect(result[0]).toMatchObject({
      date: '2026-08-14',
      high: 12,
      close: 11,
      volume: 20,
    })
    expect(result[1]).toMatchObject({ date: '2026-08-15', close: 11.5 })
  })
})

describe('useRealtimeKline', () => {
  it('loads an HTTP snapshot immediately and keeps it when websocket init is empty', async () => {
    mockedGetRealtimeBars.mockResolvedValue({
      success: true,
      code: '600036',
      data: [
        {
          date: '2026-08-25',
          open: 40,
          high: 41,
          low: 39,
          close: 40.5,
          volume: 100,
          amount: 4000,
          symbol: '600036',
        },
      ],
    })

    const { result, unmount } = renderHook(() => useRealtimeKline('600036', 'daily'))

    await waitFor(() => expect(result.current.data).toHaveLength(1))
    expect(mockedGetRealtimeBars).toHaveBeenCalledWith('600036', 'daily')
    expect(MockWebSocket.instances[0].url).toContain(
      '/api/v1/ws/realtime/600036?period=daily',
    )

    act(() => {
      MockWebSocket.instances[0].onopen?.()
      MockWebSocket.instances[0].onmessage?.({
        data: JSON.stringify({ type: 'init', data: [] }),
      })
    })

    expect(result.current.connected).toBe(true)
    expect(result.current.data).toHaveLength(1)
    unmount()
    expect(MockWebSocket.instances[0].close).toHaveBeenCalledOnce()
  })
})
