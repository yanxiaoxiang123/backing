import { describe, expect, it } from 'vitest'
import {
  hasRevealableLine,
  LINE_REVEAL_MS,
  settledChartOption,
} from './chartInteraction'

describe('chart line entrance', () => {
  const option = {
    animation: true,
    xAxis: { type: 'category', data: ['2026-11-05', '2026-11-06'] },
    dataZoom: [{ type: 'inside', throttle: 200 }],
    series: [
      { type: 'line', data: [10, 11], areaStyle: { opacity: 0.06 } },
      { type: 'bar', data: [100, 120] },
    ],
  }

  it('reveals only the line, retaining its actual points, area and static coordinate system', () => {
    const result = settledChartOption(option, true)
    expect(result.animation).toBe(false)
    expect(result.xAxis).toEqual(option.xAxis)
    expect(result.series).toEqual([
      expect.objectContaining({
        animation: true,
        animationDuration: LINE_REVEAL_MS,
        animationEasing: 'cubicInOut',
        data: [10, 11],
        areaStyle: { opacity: 0.06 },
      }),
      expect.objectContaining({ animation: false, data: [100, 120] }),
    ])
    expect(option.series[0]).not.toHaveProperty('animation')
  })

  it('settles refreshes immediately and preserves synchronous zoom feedback', () => {
    const result = settledChartOption(option)
    expect(result.series).toEqual([
      expect.objectContaining({ animation: false, animationDurationUpdate: 0 }),
      expect.objectContaining({ animation: false, animationDurationUpdate: 0 }),
    ])
    expect(result.dataZoom).toEqual([
      expect.objectContaining({ realtime: true, throttle: 0, animation: false }),
    ])
  })

  it('does not start a reveal for an empty chart, one point or a candlestick series', () => {
    expect(hasRevealableLine({})).toBe(false)
    expect(hasRevealableLine({ series: { type: 'line', data: [] } })).toBe(false)
    expect(hasRevealableLine({ series: { type: 'line', data: [10] } })).toBe(false)
    expect(
      hasRevealableLine({
        series: {
          type: 'candlestick',
          data: [
            [1, 2, 0, 3],
            [2, 3, 1, 4],
          ],
        },
      }),
    ).toBe(false)
    expect(hasRevealableLine(option)).toBe(true)
  })
})
