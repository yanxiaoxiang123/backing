import { describe, expect, it } from 'vitest'
import { CHART_TEXT, FONT_FAMILY, FONT_SIZE } from './typography'

describe('typography roles', () => {
  it('defines exactly four text sizes', () => {
    expect(new Set(Object.values(FONT_SIZE)).size).toBe(4)
    expect(FONT_SIZE).toEqual({
      metric: 28,
      title: 20,
      body: 14,
      meta: 12,
    })
  })

  it('loads Inter first and Noto Sans SC for Chinese', () => {
    expect(FONT_FAMILY).toContain('Inter Variable')
    expect(FONT_FAMILY).toContain('Noto Sans SC Variable')
    expect(FONT_FAMILY.indexOf('Inter Variable')).toBeLessThan(
      FONT_FAMILY.indexOf('Noto Sans SC Variable'),
    )
  })

  it('gives chart labels the auxiliary size', () => {
    expect(CHART_TEXT).toEqual({
      fontFamily: FONT_FAMILY,
      label: FONT_SIZE.meta,
      tooltip: FONT_SIZE.meta,
    })
  })
})
