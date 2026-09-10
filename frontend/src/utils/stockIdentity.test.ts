import { describe, expect, it } from 'vitest'
import {
  buildStockIdentityMap,
  extractStockCode,
  getStockCodeAliases,
  normalizeStockCode,
  sameStock,
} from './stockIdentity'

describe('stock identity', () => {
  it.each([
    ['sh.600000', 'sh.600000'],
    ['SH600000', 'sh.600000'],
    ['sh600000', 'sh.600000'],
    ['600000', 'sh.600000'],
    ['sz.000001', 'sz.000001'],
    ['000001', 'sz.000001'],
  ])('normalizes %s', (input, expected) => {
    expect(normalizeStockCode(input)).toBe(expected)
  })

  it('rejects malformed or unknown codes', () => {
    expect(normalizeStockCode('sh.123456')).toBeNull()
    expect(normalizeStockCode('60000')).toBeNull()
    expect(normalizeStockCode('not-a-stock')).toBeNull()
  })

  it('matches dotted and quote aliases', () => {
    expect(sameStock('sz.000001', '000001')).toBe(true)
    expect(getStockCodeAliases('SH600000')).toEqual(['sh.600000', 'sh600000', '600000'])
  })

  it('extracts a code from natural language without fallback', () => {
    expect(extractStockCode('请分析一下sh600000')).toBe('sh.600000')
    expect(extractStockCode('分析一下这个股票')).toBeNull()
  })

  it('indexes every alias once', () => {
    const map = buildStockIdentityMap(
      [{ code: 'sh.600000', value: 42 }],
      (item) => item.code,
    )
    expect(map.get('600000')).toEqual({ code: 'sh.600000', value: 42 })
  })
})
