import { describe, expect, it } from 'vitest'
import {
  formatDate,
  formatDateTime,
  formatNumber,
  formatPercent,
  numberTone,
  tradeAction,
} from './dataFormat'

describe('financial display', () => {
  it('keeps missing values distinct from real zero and rounds small signed values to neutral', () => {
    for (const value of [null, undefined, NaN, Infinity, '12']) {
      expect(formatNumber(value)).toBe('—')
      expect(formatPercent(value)).toBe('—')
      expect(numberTone(value)).toBe('price-flat')
    }
    expect(formatNumber(0)).toBe('0.00')
    expect(formatPercent(0, 2, true)).toBe('0.00%')
    expect(formatPercent(-0.0001, 2, true)).toBe('0.00%')
    expect(numberTone(-0.0001)).toBe('price-flat')
    expect(formatPercent(5.2, 2, true)).toBe('+5.20%')
    expect(formatPercent(-2.8, 2, true)).toBe('-2.80%')
    expect(formatNumber(1234567.89)).toBe('1,234,567.89')
  })
  it('uses A-share colors for signed returns and buy/sell without hiding unknown actions', () => {
    expect(numberTone(2)).toBe('price-up')
    expect(numberTone(-2)).toBe('price-down')
    expect(tradeAction('BUY')).toEqual({ label: '买入', className: 'price-up' })
    expect(tradeAction('sell')).toEqual({ label: '卖出', className: 'price-down' })
    expect(tradeAction('adjust')).toEqual({ label: 'adjust', className: 'price-flat' })
  })
  it('validates calendar dates and uses Beijing time only for zoned timestamps', () => {
    expect(formatDate('2026-02-31')).toBe('—')
    expect(formatDate('2024-02-29')).toBe('2024-02-29')
    expect(formatDateTime('2026-11-05T23:45:00Z')).toBe('2026-11-06 07:45')
    expect(formatDateTime('2026-11-06T12:30:00+08:00')).toBe('2026-11-06 12:30')
    expect(formatDateTime('2026-11-06T12:30:00')).toBe('2026-11-06 12:30')
    expect(formatDateTime('2026-11-06T25:30:00')).toBe('—')
    expect(formatDateTime('invalid')).toBe('—')
  })
})
