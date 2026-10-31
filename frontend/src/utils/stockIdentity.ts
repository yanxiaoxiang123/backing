export type StockMarket = 'sh' | 'sz' | 'bj'

export interface StockIdentity {
  market: StockMarket
  code: string
  normalized: `${StockMarket}.${string}`
  raw: string
}

export type StockAliasSet = ReadonlySet<string>

const MARKET_CODE_RULES: Array<[StockMarket, RegExp]> = [
  ['sh', /^(?:600|601|603|605|688|689)\d{3}$/],
  ['sz', /^(?:000|001|002|003|300|301)\d{3}$/],
  ['bj', /^(?:4|8)\d{5}$/],
]

function inferMarket(code: string): StockMarket | null {
  for (const [market, rule] of MARKET_CODE_RULES) {
    if (rule.test(code)) return market
  }
  return null
}

/** Convert all supported stock spellings to the canonical `sh.600000` form. */
export function normalizeStockCode(value: string | null | undefined): string | null {
  const raw = String(value ?? '')
    .trim()
    .toLowerCase()
  if (!raw) return null

  const prefix = raw.match(/^(sh|sz|bj)\.?([0-9]{6})$/)
  const suffix = raw.match(/^([0-9]{6})\.(sh|sz|bj)$/)
  if (prefix || suffix) {
    const market = prefix ? prefix[1] : suffix![2]
    const code = prefix ? prefix[2] : suffix![1]
    if (!inferMarket(code)) return null
    return `${market}.${code}`
  }

  if (/^\d{6}$/.test(raw)) {
    const market = inferMarket(raw)
    return market ? `${market}.${raw}` : null
  }

  return null
}

export function extractStockCode(value: string | null | undefined): string | null {
  const match = String(value ?? '').match(
    /(?<![A-Za-z0-9_.])(?:(?:sh|sz|bj)\.?[0-9]{6}|[0-9]{6}\.(?:sh|sz|bj)|[0-9]{6})(?![A-Za-z0-9_]|\.[A-Za-z0-9_])/i,
  )
  return match ? normalizeStockCode(match[0]) : null
}

export function parseStockIdentity(
  value: string | null | undefined,
): StockIdentity | null {
  const normalized = normalizeStockCode(value)
  if (!normalized) return null
  const [market, code] = normalized.split('.') as [StockMarket, string]
  return {
    market,
    code,
    normalized: normalized as `${StockMarket}.${string}`,
    raw: String(value ?? ''),
  }
}

/** Return aliases used by APIs that expose either dotted or bare symbols. */
export function getStockCodeAliases(value: string | null | undefined): string[] {
  const identity = parseStockIdentity(value)
  if (!identity) return []
  return [identity.normalized, `${identity.market}${identity.code}`, identity.code]
}

export function sameStock(
  left: string | null | undefined,
  right: string | null | undefined,
): boolean {
  const a = normalizeStockCode(left)
  const b = normalizeStockCode(right)
  return Boolean(a && b && a === b)
}

export function buildStockIdentityMap<T>(
  values: Iterable<T>,
  getCode: (value: T) => string,
): Map<string, T> {
  const map = new Map<string, T>()
  for (const value of values) {
    for (const alias of getStockCodeAliases(getCode(value))) map.set(alias, value)
  }
  return map
}
