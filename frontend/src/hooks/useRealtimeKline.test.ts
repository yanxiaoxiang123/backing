import { describe, expect, it } from 'vitest'
import { mergeRealtimeBars } from './useRealtimeKline'

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
