export const FONT_FAMILY =
  "'Inter Variable', 'Noto Sans SC Variable', 'Source Han Sans CN', 'PingFang SC', 'Microsoft YaHei', sans-serif"

export const FONT_SIZE = {
  metric: 28,
  title: 20,
  body: 14,
  meta: 12,
} as const

export const CHART_TEXT = {
  fontFamily: FONT_FAMILY,
  label: FONT_SIZE.meta,
  tooltip: FONT_SIZE.meta,
} as const
