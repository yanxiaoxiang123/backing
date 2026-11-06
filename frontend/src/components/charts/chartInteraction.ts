import type { EChartsOption } from 'echarts'
import { ui } from '../../styles/uiTheme'

export const LINE_REVEAL_MS = 900

export function hasRevealableLine(option: EChartsOption | Record<string, unknown>) {
  const series = Array.isArray(option.series) ? option.series : [option.series]
  return series.some(
    (item) =>
      item && item.type === 'line' && Array.isArray(item.data) && item.data.length > 1,
  )
}

/** No trailing dataZoom timer or animated interpolation after a pointer is released. */
export function settledChartOption(
  option: EChartsOption | Record<string, unknown>,
  revealLines = false,
): EChartsOption {
  const zoom = option.dataZoom
  const normalizeZoom = (value: object) => ({
    ...value,
    ...('type' in value && value.type === 'slider'
      ? { backgroundColor: ui.main, borderColor: ui.line }
      : {}),
    realtime: true,
    throttle: 0,
    animation: false,
  })
  const tooltip = option.tooltip
  const normalizeTooltip = (value: object) => ({
    ...value,
    backgroundColor: ui.panel,
    borderColor: ui.line,
    extraCssText: 'box-shadow:none',
  })
  const normalizeSeries = (value: object) => ({
    ...value,
    // A line's native clip reveals its stroke and area together. Axes stay static.
    animation: revealLines && 'type' in value && value.type === 'line',
    animationDuration: LINE_REVEAL_MS,
    animationDelay: 0,
    animationEasing: 'cubicInOut',
    animationDurationUpdate: 0,
    animationDelayUpdate: 0,
  })
  return {
    ...option,
    backgroundColor: 'transparent',
    animation: false,
    animationDurationUpdate: 0,
    ...(option.series
      ? {
          series: Array.isArray(option.series)
            ? option.series.map(normalizeSeries)
            : normalizeSeries(option.series as object),
        }
      : {}),
    ...(zoom
      ? {
          dataZoom: Array.isArray(zoom)
            ? zoom.map(normalizeZoom)
            : normalizeZoom(zoom as object),
        }
      : {}),
    ...(tooltip
      ? {
          tooltip: Array.isArray(tooltip)
            ? tooltip.map(normalizeTooltip)
            : normalizeTooltip(tooltip as object),
        }
      : {}),
  } as EChartsOption
}
