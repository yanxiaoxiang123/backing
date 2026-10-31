import { describe, expect, it } from 'vitest'
import { safeNextPath } from './nextPath'

describe('safeNextPath', () => {
  it('accepts same-origin absolute paths', () => {
    expect(safeNextPath('/')).toBe('/')
    expect(safeNextPath('/stocks/600519')).toBe('/stocks/600519')
    expect(safeNextPath('/stocks?code=600519')).toBe('/stocks?code=600519')
  })

  it('rejects protocol-relative and external URLs', () => {
    expect(safeNextPath('//evil.com')).toBeNull()
    expect(safeNextPath('https://evil.com')).toBeNull()
    expect(safeNextPath('/\\evil.com')).toBeNull()
    expect(safeNextPath('javascript:alert(1)')).toBeNull()
  })

  it('rejects empty values', () => {
    expect(safeNextPath(null)).toBeNull()
    expect(safeNextPath(undefined)).toBeNull()
    expect(safeNextPath('')).toBeNull()
  })
})
