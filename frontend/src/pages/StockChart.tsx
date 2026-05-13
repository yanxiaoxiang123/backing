import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Select, Spin, message } from 'antd'
import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'
import { getStockIndicators, getStock } from '../services/api'
import type { KlineIndicator } from '../types'
import { ArrowLeftOutlined } from '@ant-design/icons'
import { logger } from '../utils/logger'

type PeriodType = 'daily' | 'weekly' | 'monthly'

function StockChart() {
  const { code } = useParams<{ code: string }>()
  const navigate = useNavigate()
  const chartRef = useRef<ReactECharts>(null)

  const [loading, setLoading] = useState(true)
  const [stockName, setStockName] = useState('')
  const [period, setPeriod] = useState<PeriodType>('daily')
  const [klineData, setKlineData] = useState<KlineIndicator[]>([])

  useEffect(() => {
    if (code) {
      loadData()
    }
  }, [code, period])

  const loadData = async () => {
    if (!code) return

    setLoading(true)
    try {
      const stockInfo = await getStock(code)
      setStockName(stockInfo.name)

      const endDate = new Date().toISOString().split('T')[0]
      const startDate = new Date(Date.now() - 730 * 24 * 60 * 60 * 1000).toISOString().split('T')[0]

      const response = await getStockIndicators(code, period, startDate, endDate)
      setKlineData(response.data)
    } catch (error) {
      message.error('加载K线数据失败')
      logger.error(error)
    } finally {
      setLoading(false)
    }
  }

  const getChartOption = (): EChartsOption => {
    if (!klineData.length) return {}

    const dates = klineData.map(d => d.date)
    const ohlc = klineData.map(d => [d.open, d.close, d.low, d.high])
    const volumes = klineData.map((d) => ({
      value: d.volume,
      itemColor: d.close >= d.open ? '#ff3b30' : '#34c759'
    }))

    const ma5 = klineData.map(d => d.ma5)
    const ma10 = klineData.map(d => d.ma10)
    const ma20 = klineData.map(d => d.ma20)
    const ma60 = klineData.map(d => d.ma60)
    const ma120 = klineData.map(d => d.ma120)

    const dif = klineData.map(d => d.dif)
    const dea = klineData.map(d => d.dea)
    const macd = klineData.map(d => d.macd)

    const kdjK = klineData.map(d => d.kdj_k)
    const kdjD = klineData.map(d => d.kdj_d)
    const kdjJ = klineData.map(d => d.kdj_j)

    return {
      backgroundColor: '#fff',
      animation: false,
      legend: {
        top: 10,
        left: 'center',
        textStyle: { color: 'var(--color-text-secondary)', fontSize: 11 },
        data: ['K线', 'MA5', 'MA10', 'MA20', 'MA60', 'MA120']
      },
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross' },
        backgroundColor: '#fff',
        borderColor: 'var(--color-border)',
        textStyle: { color: 'var(--color-text-primary)' },
        formatter: (params: any) => {
          if (!params || params.length === 0) return ''
          const date = params[0].axisValue
          const kline = params.find((p: any) => p.seriesName === 'K线')
          const vol = params.find((p: any) => p.seriesName === '成交量')
          let html = `<div style="font-weight:600;margin-bottom:4px">${date}</div>`
          if (kline) {
            const [o, c, l, h] = kline.data as number[]
            const color = c >= o ? '#ff3b30' : '#34c759'
            html += `<div>开: <b>${o.toFixed(2)}</b> 收: <b style="color:${color}">${c.toFixed(2)}</b></div>`
            html += `<div>高: <b>${h.toFixed(2)}</b> 低: <b>${l.toFixed(2)}</b></div>`
            html += `<div>涨跌: <b style="color:${color}">${((c - o) / o * 100).toFixed(2)}%</b></div>`
          }
          if (vol) {
            const v = vol.data as number
            html += `<div>成交量: ${v.toLocaleString()}</div>`
          }
          return html
        }
      },
      axisPointer: {
        link: [{ xAxisIndex: 'all' }],
        label: { backgroundColor: '#777' }
      },
      grid: [
        { left: '10%', right: '8%', top: 50, height: '42%' },
        { left: '10%', right: '8%', top: '55%', height: '10%' },
        { left: '10%', right: '8%', top: '69%', height: '10%' },
        { left: '10%', right: '8%', top: '83%', height: '10%' }
      ],
      xAxis: [
        {
          type: 'category',
          data: dates,
          boundaryGap: false,
          axisLine: { onZero: false },
          axisLabel: { color: 'var(--color-text-tertiary)', fontSize: 10 },
          splitLine: { show: false },
          min: 'dataMin',
          max: 'dataMax'
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
        },
        {
          type: 'category',
          gridIndex: 2,
          data: dates,
          boundaryGap: false,
          axisLine: { onZero: false },
          axisTick: { show: false },
          splitLine: { show: false },
          axisLabel: { show: false }
        },
        {
          type: 'category',
          gridIndex: 3,
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
          axisLabel: { color: 'var(--color-text-tertiary)', fontSize: 10 },
          min: 'dataMin',
          max: 'dataMax'
        },
        {
          scale: true,
          gridIndex: 1,
          splitNumber: 2,
          axisLabel: { show: true, color: 'var(--color-text-tertiary)', fontSize: 9 },
          axisLine: { show: false },
          axisTick: { show: false },
          splitLine: { show: false }
        },
        {
          scale: true,
          gridIndex: 2,
          splitNumber: 2,
          axisLabel: { show: true, color: 'var(--color-text-tertiary)', fontSize: 9 },
          axisLine: { show: false },
          axisTick: { show: false },
          splitLine: { show: false }
        },
        {
          scale: true,
          gridIndex: 3,
          splitNumber: 2,
          axisLabel: { show: true, color: 'var(--color-text-tertiary)', fontSize: 9 },
          axisLine: { show: false },
          axisTick: { show: false },
          splitLine: { show: false }
        }
      ],
      dataZoom: [
        {
          type: 'inside',
          xAxisIndex: [0, 1, 2, 3],
          start: 0,
          end: 100
        },
        {
          show: true,
          xAxisIndex: [0, 1, 2, 3],
          type: 'slider',
          bottom: 10,
          start: 0,
          end: 100,
          height: 20,
          borderColor: 'var(--color-border)',
          backgroundColor: 'var(--color-bg-secondary)',
          fillerColor: 'rgba(0, 113, 227, 0.1)',
          handleStyle: { color: 'var(--color-accent)' }
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
          }
        },
        { name: 'MA5', type: 'line', data: ma5, smooth: true, lineStyle: { opacity: 0.5 } },
        { name: 'MA10', type: 'line', data: ma10, smooth: true, lineStyle: { opacity: 0.5 } },
        { name: 'MA20', type: 'line', data: ma20, smooth: true, lineStyle: { opacity: 0.5 } },
        { name: 'MA60', type: 'line', data: ma60, smooth: true, lineStyle: { opacity: 0.5 } },
        { name: 'MA120', type: 'line', data: ma120, smooth: true, lineStyle: { opacity: 0.5 } },
        {
          name: '成交量',
          type: 'bar',
          xAxisIndex: 1,
          yAxisIndex: 1,
          data: volumes
        },
        {
          name: 'MACD',
          type: 'bar',
          xAxisIndex: 2,
          yAxisIndex: 2,
          data: macd
        },
        {
          name: 'DIF',
          type: 'line',
          xAxisIndex: 2,
          yAxisIndex: 2,
          data: dif
        },
        {
          name: 'DEA',
          type: 'line',
          xAxisIndex: 2,
          yAxisIndex: 2,
          data: dea
        },
        {
          name: 'K',
          type: 'line',
          xAxisIndex: 3,
          yAxisIndex: 3,
          data: kdjK
        },
        {
          name: 'D',
          type: 'line',
          xAxisIndex: 3,
          yAxisIndex: 3,
          data: kdjD
        },
        {
          name: 'J',
          type: 'line',
          xAxisIndex: 3,
          yAxisIndex: 3,
          data: kdjJ
        }
      ]
    }
  }

  return (
    <div className="fade-in">
      {/* 页面标题 */}
      <div className="page-header">
        <div className="flex flex-between" style={{ flexWrap: 'wrap', gap: 'var(--space-md)' }}>
          <div className="flex gap-md" style={{ alignItems: 'center' }}>
            <button
              className="apple-btn apple-btn-secondary"
              onClick={() => navigate('/stocks')}
              style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-xs)' }}
            >
              <ArrowLeftOutlined /> 返回
            </button>
            <h1 className="page-title" style={{ margin: 0 }}>{stockName || code}</h1>
          </div>
          <Select
            value={period}
            onChange={setPeriod}
            style={{ width: 100 }}
            options={[
              { value: 'daily', label: '日K' },
              { value: 'weekly', label: '周K' },
              { value: 'monthly', label: '月K' }
            ]}
          />
        </div>
      </div>

      {/* K线图 */}
      <div className="apple-card" style={{ padding: 0, overflow: 'hidden' }}>
        <Spin spinning={loading}>
          {klineData.length > 0 ? (
            <ReactECharts
              ref={chartRef}
              option={getChartOption()}
              style={{ height: 800 }}
              opts={{ renderer: 'canvas' }}
            />
          ) : (
            <div className="empty-state" style={{ padding: 'var(--space-2xl)' }}>
              {loading ? '加载中...' : '暂无数据，请先同步K线数据'}
            </div>
          )}
        </Spin>
      </div>
    </div>
  )
}

export default StockChart
