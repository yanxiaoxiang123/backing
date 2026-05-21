import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Select, Spin, message } from 'antd'
import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'
import { getStock, getRealtimeBars } from '../services/api'
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

  const loadData = async () => {
    if (!code) return

    setLoading(true)
    try {
      const stockInfo = await getStock(code)
      setStockName(stockInfo.name)

      // 直接用 mootdx 实时数据
      const res = await getRealtimeBars(code, period)

      // 将 RealtimeBar 格式转换为 KlineIndicator 格式
      const klineData: KlineIndicator[] = (res.data ?? []).map((bar: any) => ({
        date: bar.date,
        open: bar.open,
        high: bar.high,
        low: bar.low,
        close: bar.close,
        volume: bar.volume,
        amount: bar.amount,
        ma5: undefined,
        ma10: undefined,
        ma20: undefined,
        ma60: undefined,
        ma120: undefined,
        dif: undefined,
        dea: undefined,
        macd: undefined,
        kdj_k: undefined,
        kdj_d: undefined,
        kdj_j: undefined,
        rsi6: undefined,
        rsi12: undefined,
        rsi24: undefined,
      }))

      setKlineData(klineData)
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
      itemColor: d.close >= d.open ? '#EB001B' : '#52C41A'
    }))

    return {
      backgroundColor: 'transparent',
      animation: false,
      legend: {
        top: 10,
        left: 'center',
        textStyle: { color: '#696969', fontSize: 11, fontWeight: 450 },
        data: ['K线', '成交量']
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
            const color = c >= o ? '#EB001B' : '#52C41A'
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
        { left: '10%', right: '8%', top: 50, height: '65%' },
        { left: '10%', right: '8%', top: '70%', height: '15%' }
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
        }
      ],
      dataZoom: [
        {
          type: 'inside',
          xAxisIndex: [0, 1],
          start: 0,
          end: 100
        },
        {
          show: true,
          xAxisIndex: [0, 1],
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
            color0: '#52C41A',
            borderColor: '#EB001B',
            borderColor0: '#52C41A'
          }
        },
        {
          name: '成交量',
          type: 'bar',
          xAxisIndex: 1,
          yAxisIndex: 1,
          data: volumes
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