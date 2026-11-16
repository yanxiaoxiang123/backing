export interface ChartZoomWindow {
  startValue: number
  endValue: number
  length: number
}

type ZoomItem = Record<string, unknown>

function zoomItems(option: unknown): ZoomItem[] {
  const dataZoom = (option as { dataZoom?: unknown } | null)?.dataZoom
  if (Array.isArray(dataZoom)) return dataZoom as ZoomItem[]
  return dataZoom ? [dataZoom as ZoomItem] : []
}

export function readChartZoomWindow(option: unknown): ChartZoomWindow | null {
  const item = zoomItems(option).find(
    (entry) => entry && ('startValue' in entry || 'endValue' in entry),
  )
  const xAxis = (option as { xAxis?: unknown } | null)?.xAxis
  const firstAxis = Array.isArray(xAxis) ? xAxis[0] : xAxis
  const data = (firstAxis as { data?: unknown } | null | undefined)?.data
  const length = Array.isArray(data) ? data.length : 0
  if (!item || !length) return null

  const startValue = Number(item.startValue)
  const endValue = Number(item.endValue)
  if (!Number.isFinite(startValue) || !Number.isFinite(endValue)) return null
  return { startValue, endValue, length }
}

export function chartZoomPercent(window: ChartZoomWindow): {
  start: number
  end: number
} {
  const max = Math.max(1, window.length - 1)
  return {
    start: (window.startValue / max) * 100,
    end: (window.endValue / max) * 100,
  }
}

export function isNextZoomWindow(
  previous: ChartZoomWindow,
  next: ChartZoomWindow,
): boolean {
  return (
    next.length === previous.length + 1 &&
    next.startValue === previous.startValue + 1 &&
    next.endValue === previous.endValue + 1
  )
}

export function chartZoomSlide(
  previous: ChartZoomWindow,
  next: ChartZoomWindow,
): {
  from: { start: number; end: number }
  to: { start: number; end: number }
} {
  return {
    from: chartZoomPercent({ ...previous, length: next.length }),
    to: chartZoomPercent(next),
  }
}
