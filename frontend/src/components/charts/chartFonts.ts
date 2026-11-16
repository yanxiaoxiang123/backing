const CJK = /[㐀-鿿]/

/** Collect the Chinese characters a chart may paint on its canvas. */
export function collectChartText(option: unknown, limit = 500): string {
  const chars = new Set<string>()
  const seen = new Set<object>()

  const walk = (value: unknown, depth: number) => {
    if (chars.size >= limit || depth > 8) return
    if (typeof value === 'string') {
      for (const char of value) {
        if (CJK.test(char)) chars.add(char)
        if (chars.size >= limit) return
      }
      return
    }
    if (Array.isArray(value)) {
      for (const item of value) walk(item, depth + 1)
      return
    }
    if (value && typeof value === 'object') {
      if (seen.has(value)) return
      seen.add(value)
      for (const item of Object.values(value)) walk(item, depth + 1)
    }
  }

  walk(option, 0)
  return [...chars].join('')
}
