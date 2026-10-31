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
    ['000001.sz', 'sz.000001'],
    ['000001.SZ', 'sz.000001'],
    ['600000.sh', 'sh.600000'],
    ['430047.BJ', 'bj.430047'],
    ['000001.sh', 'sh.000001'],
    ['SH.000001', 'sh.000001'],
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

  it.each([
    '1234567',
    'abc000001',
    'foo_sz000001',
    '000001.xyz',
    'sz000001xyz',
    '000001_foo',
    '000001.sz.xyz',
  ])('does not extract partial stock tokens from %s', (input) => {
    expect(extractStockCode(input)).toBeNull()
  })

  it('extracts complete suffix codes in Chinese and preserves explicit exchanges', () => {
    expect(extractStockCode('查询000001.SZ，最近走势？')).toBe('sz.000001')
    expect(extractStockCode('查询000001.sh。')).toBe('sh.000001')
  })

  it.each(['000001.SZ', '600000.sh', 'SH.000001'])(
    'normalizes %s idempotently',
    (input) => {
      expect(normalizeStockCode(normalizeStockCode(input))).toBe(
        normalizeStockCode(input),
      )
    },
  )

  it('indexes every alias once', () => {
    const map = buildStockIdentityMap(
      [{ code: 'sh.600000', value: 42 }],
      (item) => item.code,
    )
    expect(map.get('600000')).toEqual({ code: 'sh.600000', value: 42 })
  })
})
