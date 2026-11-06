const missing = '—'

export function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value)
}

function rounded(value: number, digits: number) {
  return Math.abs(value) < 0.5 * 10 ** -digits ? 0 : value
}

export function formatNumber(value: unknown, digits = 2): string {
  return isFiniteNumber(value)
    ? new Intl.NumberFormat('zh-CN', {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
      }).format(rounded(value, digits))
    : missing
}

/** API returns percentages as percentage points; never multiply them by 100 here. */
export function formatPercent(value: unknown, digits = 2, signed = false): string {
  if (!isFiniteNumber(value)) return missing
  const number = rounded(value, digits)
  return `${signed && number > 0 ? '+' : ''}${formatNumber(number, digits)}%`
}

export function numberTone(value: unknown, digits = 2) {
  if (!isFiniteNumber(value)) return 'price-flat'
  const number = rounded(value, digits)
  return number > 0 ? 'price-up' : number < 0 ? 'price-down' : 'price-flat'
}

export function formatDate(value: unknown): string {
  if (typeof value !== 'string') return missing
  const match = value.match(/^\d{4}-\d{2}-\d{2}/)
  if (!match) return missing
  const date = new Date(`${match[0]}T00:00:00Z`)
  if (!Number.isFinite(date.getTime()) || date.toISOString().slice(0, 10) !== match[0])
    return missing
  return match[0]
}

/** Zoned timestamps use Beijing time; legacy unzoned timestamps keep their wall time. */
export function formatDateTime(value: unknown): string {
  if (typeof value !== 'string' || formatDate(value) === missing) return missing
  if (!/(?:z|[+-]\d{2}:?\d{2})$/i.test(value)) {
    const match = value.match(/^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2})/)
    if (match && (Number(match[2].slice(0, 2)) > 23 || Number(match[2].slice(3)) > 59))
      return missing
    return match ? `${match[1]} ${match[2]}` : formatDate(value)
  }
  const timestamp = new Date(value)
  if (!Number.isFinite(timestamp.getTime())) return missing
  const parts = new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(timestamp)
  const part = (type: string) => parts.find((item) => item.type === type)?.value
  return `${part('year')}-${part('month')}-${part('day')} ${part('hour')}:${part('minute')}`
}

export function tradeAction(action: unknown) {
  const normalized = typeof action === 'string' ? action.toLowerCase() : ''
  return normalized === 'buy'
    ? { label: '买入', className: 'price-up' }
    : normalized === 'sell'
      ? { label: '卖出', className: 'price-down' }
      : {
          label: typeof action === 'string' ? action : missing,
          className: 'price-flat',
        }
}
