import { describe, expect, it } from 'vitest'
import {
  chartZoomPercent,
  chartZoomSlide,
  isNextZoomWindow,
  readChartZoomWindow,
} from './chartZoom'

describe('chart zoom window', () => {
  it('reads start and end values with the category length', () => {
    expect(
      readChartZoomWindow({
        dataZoom: [{ type: 'inside', startValue: 224, endValue: 319 }],
        xAxis: [
          {
            type: 'category',
            data: Array.from({ length: 320 }, (_, index) => `${index}`),
          },
        ],
      }),
    ).toEqual({ startValue: 224, endValue: 319, length: 320 })
  })

  it('returns null when the option has no explicit window', () => {
    expect(
      readChartZoomWindow({
        dataZoom: [{ type: 'inside' }],
        xAxis: [{ data: ['a'] }],
      }),
    ).toBeNull()
  })

  it('converts window indexes to percentages', () => {
    expect(chartZoomPercent({ startValue: 0, endValue: 99, length: 100 })).toEqual({
      start: 0,
      end: 100,
    })
    expect(
      chartZoomPercent({ startValue: 50, endValue: 99, length: 100 }).start,
    ).toBeCloseTo(50.505, 2)
  })

  it('recognizes a one-bar advance', () => {
    const previous = { startValue: 223, endValue: 318, length: 319 }
    const next = { startValue: 224, endValue: 319, length: 320 }
    expect(isNextZoomWindow(previous, next)).toBe(true)
    expect(isNextZoomWindow(previous, { ...next, startValue: 230 })).toBe(false)
    expect(isNextZoomWindow(previous, { ...next, length: 322 })).toBe(false)
  })

  it('maps the previous window onto the new data length', () => {
    const previous = { startValue: 223, endValue: 318, length: 319 }
    const next = { startValue: 224, endValue: 319, length: 320 }
    const { from, to } = chartZoomSlide(previous, next)
    expect(from.start).toBeCloseTo(69.906, 3)
    expect(from.end).toBeCloseTo(99.687, 3)
    expect(to.start).toBeCloseTo(70.219, 3)
    expect(to.end).toBe(100)
  })
})
