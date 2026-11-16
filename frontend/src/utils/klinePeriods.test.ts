import { describe, expect, it } from 'vitest'
import { PERIOD_OPTIONS, formatKlineAxisLabel } from './klinePeriods'

describe('kline periods', () => {
  it('orders the five-minute option before daily, weekly and monthly', () => {
    expect(PERIOD_OPTIONS.map((option) => option.value)).toEqual([
      '5m',
      'daily',
      'weekly',
      'monthly',
    ])
    expect(PERIOD_OPTIONS.map((option) => option.label)).toEqual([
      '分K',
      '日K',
      '周K',
      '月K',
    ])
  })

  it('shows five-minute axis labels as time of day', () => {
    expect(formatKlineAxisLabel('5m', '2026-11-16 10:20')).toBe('10:20')
    expect(formatKlineAxisLabel('daily', '2026-11-16')).toBe('2026-11-16')
  })
})
