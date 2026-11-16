export type KlinePeriod = '5m' | 'daily' | 'weekly' | 'monthly'

export const PERIOD_OPTIONS: ReadonlyArray<{
  value: KlinePeriod
  label: string
}> = [
  { value: '5m', label: '分K' },
  { value: 'daily', label: '日K' },
  { value: 'weekly', label: '周K' },
  { value: 'monthly', label: '月K' },
]

export function formatKlineAxisLabel(period: KlinePeriod, date: string): string {
  return period === '5m' && date.length >= 16 ? date.slice(11, 16) : date
}
