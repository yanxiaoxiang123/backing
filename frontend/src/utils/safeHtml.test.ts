import { describe, expect, it } from 'vitest'
import { escapeHtml, safeHttpUrl } from './safeHtml'

describe('safe report html helpers', () => {
  it('escapes markup and attributes', () => {
    expect(escapeHtml('<script>alert("x")</script>')).toBe(
      '&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;',
    )
  })

  it('only allows http(s) links', () => {
    expect(safeHttpUrl('https://example.com/a')).toBe('https://example.com/a')
    expect(safeHttpUrl('javascript:alert(1)')).toBeNull()
  })
})
