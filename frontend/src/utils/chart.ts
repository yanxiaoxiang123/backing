import type { EChartsOption } from 'echarts'
import type { SignalDataPoint, StrategyBacktestResponse, CompareResponse } from '../types'
import { COMPARE_COLORS } from '../constants/strategy'

export interface KlineData {
  date: string
  open: number
  close: number
  high: number
  low: number
  volume: number
}

export function getChartOption(
  klineData: KlineData[],
  signals: SignalDataPoint[],
  backtestResult: StrategyBacktestResponse | null
): EChartsOption {
  if (klineData.length === 0 && signals.length === 0) {
    return {}
  }

  const dates = klineData.map(d => d.date)
  const ohlc = klineData.map(d => [d.open, d.close, d.low, d.high])

  const buySignals: { coord: [number, number]; itemStyle: { color: string } }[] = []
  const sellSignals: { coord: [number, number]; itemStyle: { color: string } }[] = []

  signals.forEach(signal => {
    const dateIndex = dates.indexOf(signal.date)
    if (dateIndex >= 0) {
      if (signal.signal === 1) {
        buySignals.push({
          coord: [dateIndex, signal.close],
          itemStyle: { color: '#34c759' }
        })
      } else if (signal.signal === -1) {
        sellSignals.push({
          coord: [dateIndex, signal.close],
          itemStyle: { color: '#ff3b30' }
        })
      }
    }
  })

  if (backtestResult?.trades) {
    backtestResult.trades.forEach(trade => {
      const dateIndex = dates.indexOf(trade.date)
      if (dateIndex >= 0) {
        if (trade.action === 'buy') {
          buySignals.push({
            coord: [dateIndex, trade.price],
            itemStyle: { color: '#34c759' }
          })
        } else {
          sellSignals.push({
            coord: [dateIndex, trade.price],
            itemStyle: { color: '#ff3b30' }
          })
        }
      }
    })
  }

  return {
    backgroundColor: '#fff',
    animation: false,
    legend: {
      top: 10,
      left: 'center',
      textStyle: { color: 'var(--color-text-secondary)', fontSize: 11 },
      data: ['K线']
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      backgroundColor: '#fff',
      borderColor: 'var(--color-border)',
      textStyle: { color: 'var(--color-text-primary)' }
    },
    grid: [
      { left: '10%', right: '8%', height: '60%' },
      { left: '10%', right: '8%', top: '75%', height: '15%' }
    ],
    xAxis: [
      {
        type: 'category',
        data: dates,
        boundaryGap: false,
        axisLine: { onZero: false },
        axisLabel: { color: 'var(--color-text-tertiary)', fontSize: 10 },
        splitLine: { show: false }
      },
      {
        type: 'category',
        gridIndex: 1,
        data: dates,
        boundaryGap: false,
        axisLine: { onZero: false },
        axisTick: { show: false },
        splitLine: { show: false },
        axisLabel: { show: false }
      }
    ],
    yAxis: [
      {
        scale: true,
        splitArea: { show: false },
        axisLabel: { color: 'var(--color-text-tertiary)', fontSize: 10 }
      },
      {
        scale: true,
        gridIndex: 1,
        splitNumber: 2,
        axisLabel: { show: false },
        axisLine: { show: false },
        axisTick: { show: false },
        splitLine: { show: false }
      }
    ],
    dataZoom: [
      {
        type: 'inside',
        xAxisIndex: [0, 1],
        start: 50,
        end: 100
      },
      {
        show: true,
        xAxisIndex: [0, 1],
        type: 'slider',
        bottom: 10,
        start: 50,
        end: 100,
        height: 20,
        borderColor: 'var(--color-border)',
        backgroundColor: 'var(--color-bg-secondary)',
        fillerColor: 'rgba(0, 113, 227, 0.1)',
        handleStyle: { color: 'var(--color-ink)' }
      }
    ],
    series: [
      {
        name: 'K线',
        type: 'candlestick',
        data: ohlc,
        itemStyle: {
          color: '#ff3b30',
          color0: '#34c759',
          borderColor: '#ff3b30',
          borderColor0: '#34c759'
        },
        markPoint: {
          data: [
            ...buySignals.map(s => ({
              type: 'max' as const,
              name: '买入',
              coord: s.coord,
              itemStyle: s.itemStyle,
              symbol: 'triangle',
              symbolSize: 16
            })),
            ...sellSignals.map(s => ({
              type: 'min' as const,
              name: '卖出',
              coord: s.coord,
              itemStyle: s.itemStyle,
              symbol: 'triangle',
              symbolSize: 16
            }))
          ]
        }
      },
      {
        name: '成交量',
        type: 'bar',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: klineData.map(d => ({
          value: d.volume,
          itemColor: d.close >= d.open ? '#ff3b30' : '#34c759'
        }))
      }
    ]
  }
}

export function getCompareChartOption(compareResult: CompareResponse): EChartsOption {
  if (!compareResult || compareResult.results.length === 0) {
    return {}
  }

  const dateSet = new Set<string>()
  const seriesData: { name: string; type: 'line'; data: [string, number][]; lineStyle: { color: string; width: number }; smooth: boolean; symbol: 'none' }[] = []

  compareResult.results.forEach(r => {
    r.equity_curve.forEach(p => dateSet.add(p.date))
  })
  const allDates = Array.from(dateSet).sort()

  compareResult.results.forEach((r, i) => {
    if (r.error || r.equity_curve.length === 0) return
    const color = COMPARE_COLORS[i % COMPARE_COLORS.length]
    const curveMap = new Map(r.equity_curve.map(p => [p.date, p.value]))
    const data: [string, number][] = allDates.map(d => [d, curveMap.get(d) ?? NaN])
    seriesData.push({
      name: r.strategy_name,
      type: 'line',
      data,
      lineStyle: { color, width: 2 },
      smooth: true,
      symbol: 'none',
    })
  })

  return {
    backgroundColor: '#fff',
    animation: false,
    legend: {
      top: 10,
      left: 'center',
      textStyle: { color: 'var(--color-text-secondary)', fontSize: 11 },
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#fff',
      borderColor: 'var(--color-border)',
      textStyle: { color: 'var(--color-text-primary)' },
      formatter: ((params: { seriesName: string; value: [string, number] }[]) =>
        params.map(p => `${p.seriesName}: ¥${Number(p.value[1]).toLocaleString()}`).join('<br/>')
      ) as unknown as string,
    },
    grid: { left: '10%', right: '5%', bottom: '10%', top: '15%' },
    xAxis: {
      type: 'category',
      data: allDates,
      axisLine: { lineStyle: { color: 'var(--color-border)' } },
      axisLabel: { color: 'var(--color-text-tertiary)', fontSize: 10 },
    },
    yAxis: {
      type: 'value',
      name: '资金 (元)',
      axisLine: { show: false },
      axisLabel: {
        color: 'var(--color-text-tertiary)',
        fontSize: 10,
        formatter: (v: number) => `¥${(v / 10000).toFixed(1)}万`,
      },
      splitLine: { lineStyle: { color: 'var(--color-border-light)', type: 'dashed' } },
    },
    dataZoom: [
      { type: 'inside', start: 0, end: 100 },
      {
        show: true,
        type: 'slider',
        bottom: 10,
        start: 0,
        end: 100,
        height: 20,
        borderColor: 'var(--color-border)',
        backgroundColor: 'var(--color-bg-secondary)',
        fillerColor: 'rgba(0, 113, 227, 0.1)',
        handleStyle: { color: 'var(--color-ink)' },
      },
    ],
    series: seriesData,
  }
}