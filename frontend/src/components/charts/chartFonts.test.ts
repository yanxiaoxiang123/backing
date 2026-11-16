import { describe, expect, it } from 'vitest'
import { collectChartText } from './chartFonts'

describe('chart font text', () => {
  it('collects unique Chinese characters from labels and tooltip copy', () => {
    const text = collectChartText({
      legend: { data: ['K线', '成交量'] },
      xAxis: { data: ['2026-01-05'] },
      tooltip: { formatter: '<b>开盘</b> 10.00' },
    })
    expect([...text].sort()).toEqual([...new Set('线成交量开盘')].sort())
    expect(text).not.toContain('2')
    expect(text).not.toContain('<')
  })

  it('does not recurse forever through shared references', () => {
    const option: Record<string, unknown> = { name: '股票' }
    option.self = option
    expect(collectChartText(option)).toBe('股票')
  })
})
