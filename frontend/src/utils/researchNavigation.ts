import { normalizeStockCode } from './stockIdentity'

const RESEARCH_PANELS = [
  'market',
  'evidence',
  'backtest',
  'risk',
  'artifacts',
  'attribution',
  'alerts',
] as const
export type ResearchPanelKey = (typeof RESEARCH_PANELS)[number]

export function readResearchPanel(value: string | null): ResearchPanelKey | null {
  return RESEARCH_PANELS.includes(value as ResearchPanelKey)
    ? (value as ResearchPanelKey)
    : null
}

export function readAlertId(value: string | null): number | null {
  return value && /^[1-9]\d*$/.test(value) && Number.isSafeInteger(Number(value))
    ? Number(value)
    : null
}

export function workspaceHref(
  options: {
    threadId?: string | null
    stockCode?: string | null
    panel?: ResearchPanelKey
    alertId?: number | null
  } = {},
): string {
  const params = new URLSearchParams()
  if (options.threadId) params.set('thread_id', options.threadId)
  const stock = normalizeStockCode(options.stockCode)
  if (stock) params.set('stock', stock)
  if (options.panel) params.set('panel', options.panel)
  if (readAlertId(String(options.alertId))) params.set('alert', String(options.alertId))
  return `/workspace${params.size ? `?${params}` : ''}`
}
