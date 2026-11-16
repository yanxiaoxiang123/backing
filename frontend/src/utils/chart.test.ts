import { describe, expect, it } from 'vitest'
import { getChartOption, getPortfolioChartOption, type KlineData } from './chart'
import { CHART_TEXT } from '../styles/typography'

type Axis = { axisLabel?: { fontSize?: number } }
type ChartShape = {
  textStyle?: { fontFamily?: string }
  legend?: { textStyle?: { fontSize?: number } }
  xAxis?: Axis | Axis[]
}

const firstAxis = (option: ChartShape): Axis => {
  const axis = option.xAxis
  return Array.isArray(axis) ? (axis[0] ?? {}) : (axis ?? {})
}

describe('chart typography', () => {
  it('uses the shared font and auxiliary label size for candles', () => {
    const bar: KlineData = {
      date: '2026-01-05',
      open: 10,
      close: 10.2,
      high: 10.4,
      low: 9.9,
      volume: 1000,
    }
    const option = getChartOption([bar], [], null) as ChartShape
    expect(option.textStyle).toEqual({ fontFamily: CHART_TEXT.fontFamily })
    expect(option.legend?.textStyle?.fontSize).toBe(CHART_TEXT.label)
    expect(firstAxis(option).axisLabel?.fontSize).toBe(CHART_TEXT.label)
  })

  it('uses the shared font for portfolio charts', () => {
    const option = getPortfolioChartOption([
      {
        date: '2026-01-05',
        total_value: 100000,
        cash: 100000,
        receivable: 0,
        position_value: 0,
        position: 0,
      },
    ]) as ChartShape
    expect(option.textStyle).toEqual({ fontFamily: CHART_TEXT.fontFamily })
    expect(firstAxis(option).axisLabel?.fontSize).toBe(CHART_TEXT.label)
  })
})
