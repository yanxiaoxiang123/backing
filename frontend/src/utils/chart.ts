import type { EChartsOption } from 'echarts'
import type {
  SignalDataPoint,
  StrategyBacktestResponse,
  CompareResponse,
  PortfolioValue,
} from '../types'
import { COMPARE_COLORS } from '../constants/strategy'
import { formatNumber } from './dataFormat'

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
  backtestResult: StrategyBacktestResponse | null,
): EChartsOption {
  if (klineData.length === 0 && signals.length === 0) {
    return {}
  }

  const dates = klineData.map((d) => d.date)
  const ohlc = klineData.map((d) => [d.open, d.close, d.low, d.high])

  const buySignals: { coord: [number, number]; itemStyle: { color: string } }[] = []
  const sellSignals: { coord: [number, number]; itemStyle: { color: string } }[] = []

  signals.forEach((signal) => {
    const dateIndex = dates.indexOf(signal.date)
    if (dateIndex >= 0) {
      if (signal.signal === 1) {
        buySignals.push({
          coord: [dateIndex, signal.close],
          itemStyle: { color: '#34c759' },
        })
      } else if (signal.signal === -1) {
        sellSignals.push({
          coord: [dateIndex, signal.close],
          itemStyle: { color: '#ff3b30' },
        })
      }
    }
  })

  if (backtestResult?.trades) {
    backtestResult.trades.forEach((trade) => {
      const dateIndex = dates.indexOf(trade.date)
      if (dateIndex >= 0) {
        if (trade.action === 'buy') {
          buySignals.push({
            coord: [dateIndex, trade.price],
            itemStyle: { color: '#34c759' },
          })
        } else {
          sellSignals.push({
            coord: [dateIndex, trade.price],
            itemStyle: { color: '#ff3b30' },
          })
        }
      }
    })
  }

  return {
    backgroundColor: 'transparent',
    animation: false,
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    legend: {
      top: 10,
      left: 'center',
      textStyle: { color: '#777777', fontSize: 13 },
      data: ['K线'],
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      backgroundColor: 'transparent',
      borderColor: '#e8e8e8',
      textStyle: { color: '#242424' },
    },
    grid: [
      { left: 60, right: 24, top: 54, height: '56%' },
      { left: 60, right: 24, top: '73%', height: '13%' },
    ],
    xAxis: [
      {
        type: 'category',
        data: dates,
        boundaryGap: false,
        axisLine: { onZero: false },
        axisLabel: {
          color: '#777777',
          fontSize: 12,
          hideOverlap: true,
          formatter: (value: string) => value.slice(5).replace('-', '.'),
        },
        splitLine: { show: false },
      },
      {
        type: 'category',
        gridIndex: 1,
        data: dates,
        boundaryGap: false,
        axisLine: { onZero: false },
        axisTick: { show: false },
        splitLine: { show: false },
        axisLabel: { show: false },
      },
    ],
    yAxis: [
      {
        scale: true,
        splitArea: { show: false },
        axisLabel: {
          color: '#777777',
          fontSize: 12,
          formatter: (value: number) => value.toFixed(2),
        },
        splitLine: { lineStyle: { color: '#eeeeee' } },
      },
      {
        scale: true,
        gridIndex: 1,
        splitNumber: 2,
        axisLabel: { show: false },
        axisLine: { show: false },
        axisTick: { show: false },
        splitLine: { show: false },
      },
    ],
    dataZoom: [
      {
        type: 'inside',
        xAxisIndex: [0, 1],
        start: 50,
        end: 100,
      },
      {
        show: true,
        xAxisIndex: [0, 1],
        type: 'slider',
        bottom: 10,
        start: 50,
        end: 100,
        height: 24,
        moveHandleSize: 0,
        showDetail: false,
        borderColor: '#e8e8e8',
        backgroundColor: '#f7f7f7',
        fillerColor: 'rgba(150, 150, 150, 0.12)',
        handleStyle: { color: '#ffffff', borderColor: '#bbbbbb' },
        dataBackground: {
          lineStyle: { color: '#bbbbbb' },
          areaStyle: { color: '#eeeeee' },
        },
        selectedDataBackground: {
          lineStyle: { color: '#aaaaaa' },
          areaStyle: { color: '#dddddd' },
        },
      },
    ],
    series: [
      {
        name: 'K线',
        type: 'candlestick',
        data: ohlc,
        itemStyle: {
          color: '#c4242a',
          color0: '#1e7a4d',
          borderColor: '#c4242a',
          borderColor0: '#1e7a4d',
        },
        markPoint: {
          data: [
            ...buySignals.map((s) => ({
              type: 'max' as const,
              name: '买入',
              coord: s.coord,
              itemStyle: s.itemStyle,
              symbol: 'triangle',
              symbolSize: 16,
            })),
            ...sellSignals.map((s) => ({
              type: 'min' as const,
              name: '卖出',
              coord: s.coord,
              itemStyle: s.itemStyle,
              symbol: 'triangle',
              symbolSize: 16,
            })),
          ],
        },
      },
      {
        name: '成交量',
        type: 'bar',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: klineData.map((d) => ({
          value: d.volume,
          itemStyle: { color: d.close >= d.open ? '#c4242a' : '#1e7a4d', opacity: 0.5 },
        })),
      },
    ],
  }
}

export function getCompareChartOption(compareResult: CompareResponse): EChartsOption {
  if (!compareResult || compareResult.results.length === 0) {
    return {}
  }

  const dateSet = new Set<string>()
  const seriesData: {
    name: string
    type: 'line'
    data: [string, number][]
    lineStyle: { color: string; width: number }
    smooth: boolean
    symbol: 'none'
  }[] = []

  compareResult.results.forEach((r) => {
    r.equity_curve.forEach((p) => dateSet.add(p.date))
  })
  const allDates = Array.from(dateSet).sort()

  compareResult.results.forEach((r, i) => {
    if (r.error || r.equity_curve.length === 0) return
    const color = COMPARE_COLORS[i % COMPARE_COLORS.length]
    const curveMap = new Map(r.equity_curve.map((p) => [p.date, p.value]))
    const data: [string, number][] = allDates.map((d) => [d, curveMap.get(d) ?? NaN])
    seriesData.push({
      name: r.strategy_name,
      type: 'line',
      data,
      lineStyle: { color, width: 2 },
      smooth: false,
      symbol: 'none',
    })
  })

  return {
    backgroundColor: 'transparent',
    animation: false,
    legend: {
      top: 10,
      left: 'center',
      textStyle: { color: '#777777', fontSize: 13 },
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'transparent',
      borderColor: '#e8e8e8',
      textStyle: { color: '#242424' },
      formatter: ((params: { seriesName: string; value: [string, number] }[]) =>
        params
          .map((p) => `${p.seriesName}: ¥${formatNumber(p.value[1])}`)
          .join('<br/>')) as unknown as string,
    },
    grid: { left: '10%', right: '5%', bottom: '10%', top: '15%' },
    xAxis: {
      type: 'category',
      data: allDates,
      axisLine: { lineStyle: { color: '#e8e8e8' } },
      axisLabel: { color: '#777777', fontSize: 12 },
    },
    yAxis: {
      type: 'value',
      name: '资金 (元)',
      axisLine: { show: false },
      axisLabel: {
        color: '#777777',
        fontSize: 12,
        formatter: (v: number) => `¥${(v / 10000).toFixed(1)}万`,
      },
      splitLine: { lineStyle: { color: '#eeeeee', type: 'dashed' } },
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
        borderColor: '#e8e8e8',
        backgroundColor: '#f7f7f7',
        fillerColor: 'rgba(150, 150, 150, 0.12)',
        handleStyle: { color: '#777777' },
      },
    ],
    series: seriesData,
  }
}

export function getPortfolioChartOption(values: PortfolioValue[] = []): EChartsOption {
  if (values.length === 0) return {}

  return {
    backgroundColor: 'transparent',
    animation: false,
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'transparent',
      borderColor: '#e8e8e8',
      textStyle: { color: '#242424' },
      valueFormatter: (value) => `¥${formatNumber(value)}`,
    },
    grid: { left: '10%', right: '5%', bottom: '15%', top: '12%' },
    xAxis: {
      type: 'category',
      data: values.map((item) => item.date),
      axisLine: { lineStyle: { color: '#e8e8e8' } },
      axisLabel: { color: '#777777', fontSize: 12 },
    },
    yAxis: {
      type: 'value',
      name: '资金 (元)',
      axisLine: { show: false },
      axisLabel: {
        color: '#777777',
        fontSize: 12,
        formatter: (value: number) => `¥${(value / 10000).toFixed(1)}万`,
      },
      splitLine: { lineStyle: { color: '#eeeeee', type: 'dashed' } },
    },
    dataZoom: [
      { type: 'inside', start: 0, end: 100 },
      {
        show: true,
        type: 'slider',
        bottom: 8,
        start: 0,
        end: 100,
        height: 24,
        moveHandleSize: 0,
        borderColor: '#eeeeee',
        backgroundColor: '#f7f7f7',
        fillerColor: 'rgba(150, 150, 150, 0.12)',
        dataBackground: {
          lineStyle: { color: '#bbbbbb' },
          areaStyle: { color: '#eeeeee' },
        },
        selectedDataBackground: {
          lineStyle: { color: '#aaaaaa' },
          areaStyle: { color: '#dddddd' },
        },
      },
    ],
    series: [
      {
        name: '组合价值',
        type: 'line',
        smooth: false,
        symbol: 'none',
        data: values.map((item) => item.total_value),
        lineStyle: { color: '#1677ff', width: 2 },
      },
    ],
  }
}
