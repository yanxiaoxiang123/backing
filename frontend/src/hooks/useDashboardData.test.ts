import { describe, expect, it } from 'vitest'
import { getMarketPollingInterval } from './useDashboardData'

describe('getMarketPollingInterval', () => {
  it('returns 60s on weekends', () => {
    // 2026-10-18 is Sunday (day 0)
    const sunday = new Date('2026-10-18T10:00:00')
    expect(getMarketPollingInterval(sunday)).toBe(60_000)

    // 2026-10-17 is Saturday (day 6)
    const saturday = new Date('2026-10-17T10:00:00')
    expect(getMarketPollingInterval(saturday)).toBe(60_000)
  })

  it('returns 10s during morning trading hours (09:15 - 11:35)', () => {
    // 2026-10-19 is Monday
    const start = new Date('2026-10-19T09:15:00')
    expect(getMarketPollingInterval(start)).toBe(10_000)

    const midMorning = new Date('2026-10-19T10:30:00')
    expect(getMarketPollingInterval(midMorning)).toBe(10_000)

    const end = new Date('2026-10-19T11:35:00')
    expect(getMarketPollingInterval(end)).toBe(10_000)
  })

  it('returns 10s during afternoon trading hours (12:55 - 15:05)', () => {
    // 2026-10-19 is Monday
    const start = new Date('2026-10-19T12:55:00')
    expect(getMarketPollingInterval(start)).toBe(10_000)

    const midAfternoon = new Date('2026-10-19T14:00:00')
    expect(getMarketPollingInterval(midAfternoon)).toBe(10_000)

    const end = new Date('2026-10-19T15:05:00')
    expect(getMarketPollingInterval(end)).toBe(10_000)
  })

  it('returns 60s outside trading hours on weekdays', () => {
    // 2026-10-19 is Monday
    const earlyMorning = new Date('2026-10-19T08:30:00')
    expect(getMarketPollingInterval(earlyMorning)).toBe(60_000)

    const lunchBreak = new Date('2026-10-19T12:00:00')
    expect(getMarketPollingInterval(lunchBreak)).toBe(60_000)

    const lateAfternoon = new Date('2026-10-19T15:06:00')
    expect(getMarketPollingInterval(lateAfternoon)).toBe(60_000)

    const evening = new Date('2026-10-19T20:00:00')
    expect(getMarketPollingInterval(evening)).toBe(60_000)
  })

  it('defaults to current time if no argument provided', () => {
    const interval = getMarketPollingInterval()
    expect([10_000, 60_000]).toContain(interval)
  })
})
