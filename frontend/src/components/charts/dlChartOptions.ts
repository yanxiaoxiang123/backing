import type { EChartsOption } from 'echarts'
import type { DLBacktest, DLForecast } from '../../services/dl'
import { formatNumber } from '../../utils/dataFormat'

const blue = '#1677ff'
const red = '#ff4545'
const fontFamily = "'Microsoft YaHei', 'PingFang SC', sans-serif"

function priceChart(dates: string[], start: number): EChartsOption {
  return {
    backgroundColor: 'transparent',
    animation: false,
    textStyle: { fontFamily },
    color: [blue, red],
    legend: {
      top: 12,
      left: 'center',
      itemWidth: 26,
      itemHeight: 8,
      itemGap: 28,
      textStyle: { color: '#777777', fontSize: 15 },
    },
    tooltip: {
      trigger: 'axis',
      confine: true,
      axisPointer: {
        type: 'cross',
        label: { backgroundColor: '#777777' },
      },
      backgroundColor: 'transparent',
      borderColor: '#e8e8e8',
      textStyle: { color: '#242424', fontSize: 13 },
      valueFormatter: (value) =>
        typeof value === 'number' ? `${formatNumber(value)} CNY` : '—',
    },
    grid: { left: 58, right: 48, top: 64, bottom: 86 },
    xAxis: {
      type: 'category',
      data: dates,
      boundaryGap: false,
      axisLine: { onZero: false, lineStyle: { color: '#bbbbbb' } },
      axisTick: { show: false },
      axisLabel: {
        color: '#777777',
        fontSize: 13,
        margin: 14,
        showMinLabel: true,
        showMaxLabel: true,
        hideOverlap: true,
        formatter: (value: string) => value.slice(5, 10).replace('-', '.'),
      },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value',
      name: '价格 / 元',
      scale: true,
      splitNumber: 4,
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { lineStyle: { color: '#eeeeee', width: 1 } },
      axisLabel: { color: '#777777', fontSize: 12, margin: 12 },
    },
    dataZoom: [
      { type: 'inside', start, end: 100 },
      {
        type: 'slider',
        start,
        end: 100,
        bottom: 10,
        left: 28,
        right: 34,
        height: 30,
        showDetail: false,
        brushSelect: false,
        borderColor: '#eeeeee',
        backgroundColor: '#f7f7f7',
        fillerColor: 'rgba(150, 150, 150, 0.12)',
        dataBackground: {
          lineStyle: { color: '#c9c9c9', width: 1 },
          areaStyle: { color: '#eeeeee', opacity: 0.4 },
        },
        selectedDataBackground: {
          lineStyle: { color: '#aaaaaa', width: 1 },
          areaStyle: { color: '#dddddd', opacity: 0.3 },
        },
        handleSize: '85%',
        handleStyle: { color: '#ffffff', borderColor: '#bbbbbb', borderWidth: 1 },
        moveHandleSize: 0,
      },
    ],
  }
}

export function forecastChartOption(result: DLForecast | null): EChartsOption {
  if (!result?.kline_data?.length) return {}
  const history = result.kline_data
  const dates = [...history.map((bar) => bar.date), ...result.prediction_dates]
  const lastIndex = history.length - 1
  const lastPrice = result.predicted_prices[result.predicted_prices.length - 1]
  return {
    ...priceChart(dates, 50),
    series: [
      {
        name: '历史价格',
        type: 'line',
        data: [
          ...history.map((bar) => bar.close),
          ...Array(result.prediction_dates.length).fill(null),
        ],
        smooth: false,
        symbol: 'none',
        lineStyle: { color: blue, width: 2 },
        itemStyle: { color: blue },
      },
      {
        name: '预测价格',
        type: 'line',
        data: [
          ...Array(lastIndex).fill(null),
          history[lastIndex].close,
          ...result.predicted_prices,
        ],
        smooth: false,
        symbol: 'none',
        lineStyle: { color: red, width: 2, type: 'dashed' },
        itemStyle: { color: red },
        markLine: {
          silent: true,
          symbol: 'none',
          lineStyle: { color: '#ff9500', width: 1, type: 'dashed' },
          label: {
            formatter: '预测起点',
            position: 'insideEndTop',
            rotate: 0,
            color: '#ee8b00',
            fontSize: 12,
            distance: 8,
          },
          data: [{ xAxis: lastIndex }],
        },
        ...(lastPrice === undefined
          ? {}
          : {
              markPoint: {
                symbol: 'circle',
                symbolSize: 7,
                itemStyle: { color: red, borderColor: '#ffffff', borderWidth: 1 },
                label: {
                  show: true,
                  position: 'top',
                  formatter: lastPrice.toFixed(2),
                  color: red,
                  fontSize: 13,
                  backgroundColor: 'transparent',
                  borderColor: red,
                  borderWidth: 1,
                  borderRadius: 4,
                  padding: [4, 7],
                },
                data: [{ name: '预测末值', coord: [dates.length - 1, lastPrice] }],
              },
            }),
      },
    ],
  }
}

export function backtestChartOption(result: DLBacktest | null): EChartsOption {
  if (!result?.dates?.length) return {}
  return {
    ...priceChart(result.dates, 0),
    tooltip: {
      trigger: 'axis',
      confine: true,
      backgroundColor: 'transparent',
      borderColor: '#e8e8e8',
      textStyle: { color: '#242424', fontSize: 13 },
      formatter: (params) => {
        const items = Array.isArray(params) ? params : [params]
        const index = items.find((item) => item.seriesName === '收盘价')?.dataIndex
        if (index === undefined) return ''
        const day = result.dates[index]
        const safeDay = day.replace(/[&<>"']/g, '')
        const trades = result.trades.filter((trade) => trade.date === day)
        return [
          `<strong>${safeDay}</strong>`,
          `收盘价：${result.close_prices[index].toFixed(2)} CNY`,
          ...trades.map((trade) =>
            [
              `${trade.action === 'BUY' ? '买入' : '卖出'}：${trade.price.toFixed(2)} CNY`,
              ...(trade.profit === undefined
                ? []
                : [`收益：${trade.profit.toFixed(2)} CNY`]),
              ...(trade.return === undefined
                ? []
                : [`收益率：${trade.return.toFixed(2)}%`]),
            ].join('<br/>'),
          ),
        ].join('<br/>')
      },
    },
    series: [
      {
        name: '收盘价',
        type: 'line',
        data: result.close_prices,
        symbol: 'none',
        lineStyle: { color: blue, width: 2 },
        itemStyle: { color: blue },
      },
      ...(['BUY', 'SELL'] as const).map((action) => ({
        name: action === 'BUY' ? '买入' : '卖出',
        type: 'scatter' as const,
        data: result.trades
          .filter((trade) => trade.action === action)
          .map((trade) => [trade.date, trade.price]),
        symbol: 'triangle',
        symbolRotate: action === 'BUY' ? 0 : 180,
        symbolSize: 10,
        itemStyle: {
          color: action === 'BUY' ? '#2e7d32' : red,
          borderColor: '#ffffff',
          borderWidth: 1,
        },
      })),
    ],
  }
}
