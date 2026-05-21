import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Select, Spin, message } from 'antd'
import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'
import { getStockIndicators, getStock, getRealtimeBars } from '../services/api'
import type { KlineIndicator } from '../types'
import { ArrowLeftOutlined } from '@ant-design/icons'

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

  // Realtime polling every 10 seconds - updates the latest K-line bar with live data
  useEffect(() => {
    if (!code) return

    const pollRealtime = async () => {
      try {
        const res = await getRealtimeBars(code)
        if (!res.data?.length) return
        setKlineData(prev => {
          const merged = [...prev]
          for (const bar of res.data) {
            // Convert RealtimeBar format to KlineIndicator format
            const indicatorBar: KlineIndicator = {
              date: bar.date,
              open: bar.open,
              high: bar.high,
              low: bar.low,
              close: bar.close,
              volume: bar.volume,
              // Technical indicators will be recalculated below
            }
            const existIdx = merged.findIndex(b => b.date === bar.date)
            if (existIdx >= 0) {
              merged[existIdx] = indicatorBar
            } else {
              merged.push(indicatorBar)
            }
          }
          return merged
            .sort((a, b) => a.date.localeCompare(b.date))
            .slice(-120)
        })
      } catch (e) {
        console.warn('StockChart realtime poll failed:', e)
      }
    }

    pollRealtime()
    const interval = setInterval(pollRealtime, 10_000)
    return () => clearInterval(interval)
  }, [code])

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
      itemColor: d.close >= d.open ? '#EB001B' : '#F79E1B'
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
      backgroundColor: 'transparent',
      animation: false,
      legend: {
        top: 10,
        left: 'center',
        textStyle: { color: '#696969', fontSize: 11, fontWeight: 450 },
        data: ['K线', 'MA5', 'MA10', 'MA20', 'MA60', 'MA120']
      },
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross' },
        backgroundColor: '#FCFBFA',
        borderColor: '#D1CDC7',
        borderWidth: 1,
        textStyle: { color: '#141413', fontWeight: 450 },
        formatter: (params: any) => {
          if (!params || params.length === 0) return ''
          const date = params[0].axisValue
          const kline = params.find((p: any) => p.seriesName === 'K线')
          const vol = params.find((p: any) => p.seriesName === '成交量')
          let html = `<div style="font-weight:500;margin-bottom:4px;letter-spacing:-0.02em">${date}</div>`
          if (kline) {
            const [o, c, l, h] = kline.data as number[]
            const color = c >= o ? '#EB001B' : '#F79E1B'
            html += `<div style="font-size:14px;font-weight:450">开: <b>${o.toFixed(2)}</b> 收: <b style="color:${color}">${c.toFixed(2)}</b></div>`
            html += `<div style="font-size:14px;font-weight:450">高: <b>${h.toFixed(2)}</b> 低: <b>${l.toFixed(2)}</b></div>`
            html += `<div style="font-size:14px;font-weight:450">涨跌: <b style="color:${color}">${((c - o) / o * 100).toFixed(2)}%</b></div>`
          }
          if (vol) {
            const v = vol.data as number
            html += `<div style="font-size:14px;font-weight:450">成交量: ${v.toLocaleString()}</div>`
          }
          return html
        }
      },
      axisPointer: {
        link: [{ xAxisIndex: 'all' }],
        label: { backgroundColor: '#696969' }
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
          axisLine: { onZero: false, lineStyle: { color: '#D1CDC7' } },
          axisLabel: { color: '#696969', fontSize: 10, fontWeight: 450 },
          splitLine: { show: false },
          min: 'dataMin',
          max: 'dataMax'
        },
        {
          type: 'category',
          gridIndex: 1,
          data: dates,
          boundaryGap: false,
          axisLine: { onZero: false, lineStyle: { color: '#D1CDC7' } },
          axisTick: { show: false },
          splitLine: { show: false },
          axisLabel: { show: false }
        },
        {
          type: 'category',
          gridIndex: 2,
          data: dates,
          boundaryGap: false,
          axisLine: { onZero: false, lineStyle: { color: '#D1CDC7' } },
          axisTick: { show: false },
          splitLine: { show: false },
          axisLabel: { show: false }
        },
        {
          type: 'category',
          gridIndex: 3,
          data: dates,
          boundaryGap: false,
          axisLine: { onZero: false, lineStyle: { color: '#D1CDC7' } },
          axisTick: { show: false },
          splitLine: { show: false },
          axisLabel: { show: false }
        }
      ],
      yAxis: [
        {
          scale: true,
          splitArea: { show: false },
          axisLabel: { color: '#696969', fontSize: 10, fontWeight: 450 },
          min: 'dataMin',
          max: 'dataMax',
          splitLine: { lineStyle: { color: '#F3F0EE' } }
        },
        {
          scale: true,
          gridIndex: 1,
          splitNumber: 2,
          axisLabel: { show: true, color: '#696969', fontSize: 9, fontWeight: 450 },
          axisLine: { show: false },
          axisTick: { show: false },
          splitLine: { show: false }
        },
        {
          scale: true,
          gridIndex: 2,
          splitNumber: 2,
          axisLabel: { show: true, color: '#696969', fontSize: 9, fontWeight: 450 },
          axisLine: { show: false },
          axisTick: { show: false },
          splitLine: { show: false }
        },
        {
          scale: true,
          gridIndex: 3,
          splitNumber: 2,
          axisLabel: { show: true, color: '#696969', fontSize: 9, fontWeight: 450 },
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
          borderColor: '#D1CDC7',
          backgroundColor: '#F3F0EE',
          fillerColor: 'rgba(207, 69, 0, 0.08)',
          handleStyle: { color: '#141413', borderColor: '#141413' },
          textStyle: { color: '#696969', fontSize: 10, fontWeight: 450 }
        }
      ],
      series: [
        {
          name: 'K线',
          type: 'candlestick',
          data: ohlc,
          itemStyle: {
            color: '#EB001B',
            color0: '#F79E1B',
            borderColor: '#EB001B',
            borderColor0: '#F79E1B'
          }
        },
        { name: 'MA5', type: 'line', data: ma5, smooth: true, lineStyle: { width: 1, opacity: 0.6 } },
        { name: 'MA10', type: 'line', data: ma10, smooth: true, lineStyle: { width: 1, opacity: 0.6 } },
        { name: 'MA20', type: 'line', data: ma20, smooth: true, lineStyle: { width: 1, opacity: 0.6 } },
        { name: 'MA60', type: 'line', data: ma60, smooth: true, lineStyle: { width: 1, opacity: 0.6 } },
        { name: 'MA120', type: 'line', data: ma120, smooth: true, lineStyle: { width: 1, opacity: 0.6 } },
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
      <style>{`
        .mastercard-select .ant-select-selector {
          border-radius: 20px !important;
          border: 1.5px solid #141413 !important;
          background: #FFFFFF !important;
          font-weight: 450 !important;
          letter-spacing: -0.02em;
        }
        .mastercard-select .ant-select-selection-item {
          font-weight: 450 !important;
        }
        .mastercard-select .ant-select-arrow {
          color: #141413 !important;
        }
        .mastercard-select.ant-select:hover .ant-select-selector {
          border-color: #141413 !important;
        }
        .mastercard-select .ant-select-selection-placeholder {
          font-weight: 450 !important;
        }
      `}</style>
      {/* 页面标题 */}
      <div className="page-header">
        <div className="flex flex-between" style={{ flexWrap: 'wrap', gap: 'var(--space-md)' }}>
          <div className="flex gap-md" style={{ alignItems: 'center' }}>
            <button
              onClick={() => navigate('/stocks')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                padding: '6px 24px',
                background: '#FFFFFF',
                color: '#141413',
                border: '1.5px solid #141413',
                borderRadius: 20,
                fontSize: 14,
                fontWeight: 450,
                cursor: 'pointer',
                letterSpacing: '-0.02em'
              }}
            >
              <ArrowLeftOutlined style={{ fontSize: 14 }} />
              <span style={{ fontSize: 14, fontWeight: 500 }}>返回</span>
            </button>
            <h1 className="page-title" style={{ margin: 0 }}>{stockName || code}</h1>
          </div>
          <Select
            value={period}
            onChange={setPeriod}
            style={{ width: 100, borderRadius: 20 }}
            className="mastercard-select"
            options={[
              { value: 'daily', label: '日K' },
              { value: 'weekly', label: '周K' },
              { value: 'monthly', label: '月K' }
            ]}
          />
        </div>
      </div>

      {/* K线图 - Mastercard Stadium Style */}
      <div style={{
        padding: 0,
        overflow: 'hidden',
        background: '#F3F0EE',
        borderRadius: 40,
        boxShadow: 'rgba(0, 0, 0, 0.08) 0px 24px 48px 0px'
      }}>
        <Spin spinning={loading}>
          {klineData.length > 0 ? (
            <ReactECharts
              ref={chartRef}
              option={getChartOption()}
              style={{ height: 800 }}
              opts={{ renderer: 'canvas' }}
            />
          ) : (
            <div style={{
              padding: '64px',
              textAlign: 'center',
              color: '#696969',
              fontSize: 16,
              fontWeight: 450
            }}>
              {loading ? '加载中...' : '暂无数据，请先同步K线数据'}
            </div>
          )}
        </Spin>
      </div>
    </div>
  )
}

export default StockChart
