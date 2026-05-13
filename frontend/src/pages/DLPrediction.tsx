import { useState, useRef } from 'react'
import {
  Card,
  InputNumber,
  DatePicker,
  Button,
  Spin,
  Empty,
  message,
  Descriptions,
  Table,
  Tag
} from 'antd'
import { LoadingOutlined, LineChartOutlined, PlayCircleOutlined } from '@ant-design/icons'
import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'
import { dlPredict, dlBacktest } from '../services/api'
import StockSearch from '../components/StockSearch'
import { logger } from '../utils/logger'
import { usePersistedState } from '../hooks/usePersistedState'
import dayjs from 'dayjs'

const { RangePicker } = DatePicker

interface DLPredictionResult {
  stock_code: string
  current_price: number
  last_date: string
  prediction_dates: string[]
  predicted_prices: number[]
  kline_data: {
    date: string
    open: number
    close: number
    high: number
    low: number
    volume: number
  }[]
}

interface DLBacktestResult {
  total_return: number
  annualized_return: number
  sharpe_ratio: number
  max_drawdown: number
  win_rate: number
  total_trades: number
  trades: {
    date: string
    action: 'BUY' | 'SELL'
    price: number
    quantity: number
    cost?: number
    revenue?: number
    return?: number
    profit?: number
  }[]
  portfolio_values: number[]
  dates: string[]
  close_prices: number[]
}

function DLPrediction() {
  const chartRef = useRef<ReactECharts>(null)

  // State
  const [loadingPredict, setLoadingPredict] = useState(false)
  const [loadingBacktest, setLoadingBacktest] = useState(false)

  // Form state
  const [stockCode, setStockCode] = usePersistedState<string | null>('dl_stockCode', null)
  const [klineDays, setKlineDays] = usePersistedState('dl_klineDays', 60)
  const [dateRange, setDateRange] = usePersistedState<[string, string]>('dl_dateRange', [
    dayjs().subtract(1, 'year').format('YYYY-MM-DD'),
    dayjs().format('YYYY-MM-DD')
  ])
  const [initialCapital, setInitialCapital] = usePersistedState('dl_initialCapital', 100000)

  // Results state
  const [predictionResult, setPredictionResult] = useState<DLPredictionResult | null>(null)
  const [backtestResult, setBacktestResult] = useState<DLBacktestResult | null>(null)

  const handlePredict = async () => {
    if (!stockCode) {
      message.warning('请选择股票')
      return
    }

    setLoadingPredict(true)
    setBacktestResult(null)
    try {
      const response = await dlPredict({
        stock_code: stockCode,
        kline_days: klineDays
      })
      if (!response.success || !response.data) {
        message.error(response.error || '预测失败')
        return
      }
      setPredictionResult(response.data)
      message.success('预测完成')
    } catch (error) {
      message.error('预测失败')
      logger.error(error)
    } finally {
      setLoadingPredict(false)
    }
  }

  const handleBacktest = async () => {
    if (!stockCode || !dateRange[0] || !dateRange[1]) {
      message.warning('请选择股票和回测区间')
      return
    }

    setLoadingBacktest(true)
    setPredictionResult(null)
    try {
      const response = await dlBacktest({
        stock_code: stockCode,
        start_date: dateRange[0],
        end_date: dateRange[1],
        initial_capital: initialCapital
      })
      if (!response.success || !response.data) {
        message.error(response.error || '回测失败')
        return
      }
      setBacktestResult(response.data as DLBacktestResult)
      message.success('回测完成')
    } catch (error) {
      message.error('回测失败')
      logger.error(error)
    } finally {
      setLoadingBacktest(false)
    }
  }

  const getChartOption = (): EChartsOption => {
    if (!predictionResult || !Array.isArray(predictionResult.kline_data) || predictionResult.kline_data.length === 0) {
      return {}
    }

    const klineData = predictionResult.kline_data
    const dates = klineData.map(d => d.date)
    const closePrices = klineData.map(d => d.close)

    // 预测数据
    const predictionDates = predictionResult.prediction_dates || []
    const predictedPrices = predictionResult.predicted_prices || []

    // 合并所有日期用于x轴
    const allDates = [...dates, ...predictionDates]

    // 预测起点索引（历史数据的最后一天）
    const predictionStartIndex = dates.length - 1

    return {
      backgroundColor: '#fff',
      animation: false,
      legend: {
        top: 10,
        left: 'center',
        textStyle: { color: 'var(--color-text-secondary)', fontSize: 11 },
        data: ['历史价格', '预测价格']
      },
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross' },
        backgroundColor: '#fff',
        borderColor: 'var(--color-border)',
        textStyle: { color: 'var(--color-text-primary)' }
      },
      grid: [
        { left: '10%', right: '8%', height: '70%' }
      ],
      xAxis: {
        type: 'category',
        data: allDates,
        boundaryGap: false,
        axisLine: { onZero: false },
        axisLabel: { color: 'var(--color-text-tertiary)', fontSize: 10 },
        splitLine: { show: false }
      },
      yAxis: {
        scale: true,
        splitArea: { show: false },
        axisLabel: { color: 'var(--color-text-tertiary)', fontSize: 10 }
      },
      dataZoom: [
        {
          type: 'inside',
          start: 50,
          end: 100
        },
        {
          show: true,
          type: 'slider',
          bottom: 10,
          start: 50,
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
          name: '历史价格',
          type: 'line',
          data: [...closePrices, ...Array(predictionDates.length).fill(null)],
          smooth: true,
          symbol: 'none',
          lineStyle: {
            color: '#0071e3',
            width: 2
          },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(0, 113, 227, 0.2)' },
                { offset: 1, color: 'rgba(0, 113, 227, 0.02)' }
              ]
            }
          }
        },
        {
          name: '预测价格',
          type: 'line',
          data: [...Array(dates.length - 1).fill(null), closePrices[closePrices.length - 1], ...predictedPrices],
          smooth: true,
          symbol: 'circle',
          symbolSize: 6,
          lineStyle: {
            color: '#ff3b30',
            width: 2,
            type: 'dashed'
          },
          itemStyle: {
            color: '#ff3b30'
          }
        },
        {
          name: '预测起点',
          type: 'line',
          markLine: {
            silent: true,
            symbol: 'none',
            data: [
              {
                xAxis: predictionStartIndex,
                lineStyle: {
                  color: '#ff9500',
                  width: 2,
                  type: 'solid'
                },
                label: {
                  show: true,
                  position: 'start',
                  formatter: '预测起点',
                  color: '#ff9500',
                  fontSize: 11
                }
              }
            ]
          }
        }
      ]
    }
  }

  const getBacktestChartOption = (): EChartsOption => {
    if (!backtestResult || !backtestResult.dates || backtestResult.dates.length === 0) {
      return {}
    }

    const dates = backtestResult.dates
    const closePrices = backtestResult.close_prices
    const trades = backtestResult.trades || []

    // 提取买卖点
    const buyPoints: { date: string; price: number; profit?: number }[] = []
    const sellPoints: { date: string; price: number; return?: number; profit?: number }[] = []

    trades.forEach(trade => {
      if (trade.action === 'BUY') {
        buyPoints.push({ date: trade.date, price: trade.price })
      } else {
        sellPoints.push({ date: trade.date, price: trade.price, return: trade.return, profit: trade.profit })
      }
    })

    // 买卖点对应的索引
    const buyData = buyPoints.map(p => ({
      value: [p.date, p.price],
      itemStyle: { color: '#34c759', borderColor: '#fff', borderWidth: 1 }
    }))
    const sellData = sellPoints.map(p => ({
      value: [p.date, p.price, p.profit],
      itemStyle: { color: '#ff3b30', borderColor: '#fff', borderWidth: 1 }
    }))

    return {
      backgroundColor: '#fff',
      animation: false,
      legend: {
        top: 10,
        left: 'center',
        textStyle: { color: 'var(--color-text-secondary)', fontSize: 11 },
        data: ['收盘价', '买入', '卖出']
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
          const price = params[0].data[1]
          let html = `<div style="font-weight:500">${date}</div>`
          html += `<div>价格: <span style="color:#0071e3;font-weight:500">${price.toFixed(2)}</span></div>`

          const buy = buyPoints.find(p => p.date === date)
          const sell = sellPoints.find(p => p.date === date)
          if (buy) {
            html += `<div style="color:#34c759">买入: ${buy.price.toFixed(2)}</div>`
          }
          if (sell) {
            const color = (sell.profit ?? 0) >= 0 ? '#34c759' : '#ff3b30'
            const sign = (sell.profit ?? 0) >= 0 ? '+' : ''
            html += `<div style="color:${color}">卖出: ${sell.price.toFixed(2)}</div>`
            html += `<div style="color:${color}">收益: ${sign}${sell.profit?.toFixed(2)} (${sign}${sell.return?.toFixed(2)}%)</div>`
          }
          return html
        }
      },
      grid: [
        { left: '10%', right: '8%', top: '15%', height: '70%' }
      ],
      xAxis: {
        type: 'category',
        data: dates,
        boundaryGap: false,
        axisLine: { onZero: false },
        axisLabel: { color: 'var(--color-text-tertiary)', fontSize: 10 },
        splitLine: { show: false }
      },
      yAxis: {
        scale: true,
        splitArea: { show: false },
        axisLabel: { color: 'var(--color-text-tertiary)', fontSize: 10 }
      },
      dataZoom: [
        {
          type: 'inside',
          start: 0,
          end: 100
        },
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
          handleStyle: { color: 'var(--color-accent)' }
        }
      ],
      series: [
        {
          name: '收盘价',
          type: 'line',
          data: closePrices,
          smooth: true,
          symbol: 'none',
          lineStyle: {
            color: '#0071e3',
            width: 2
          },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(0, 113, 227, 0.2)' },
                { offset: 1, color: 'rgba(0, 113, 227, 0.02)' }
              ]
            }
          }
        },
        {
          name: '买入',
          type: 'scatter',
          data: buyData,
          symbol: 'triangle',
          symbolSize: 10,
          zlevel: 10
        },
        {
          name: '卖出',
          type: 'scatter',
          data: sellData,
          symbol: 'triangle',
          symbolSize: 10,
          symbolRotate: 180,
          zlevel: 10
        }
      ]
    }
  }

  const tradeColumns = [
    { title: '日期', dataIndex: 'date', key: 'date' },
    {
      title: '操作',
      dataIndex: 'action',
      key: 'action',
      render: (action: string) => (
        <Tag color={action.toUpperCase() === 'BUY' ? 'green' : 'red'}>
          {action.toUpperCase() === 'BUY' ? '买入' : '卖出'}
        </Tag>
      )
    },
    { title: '价格', dataIndex: 'price', key: 'price', render: (v: number) => v.toFixed(2) },
    { title: '数量', dataIndex: 'quantity', key: 'quantity' },
    {
      title: '金额',
      key: 'amount',
      render: (_: number | undefined, record: DLBacktestResult['trades'][number]) => {
        const amount = record.action === 'BUY'
          ? (record.cost ?? record.price * record.quantity)
          : (record.revenue ?? record.price * record.quantity)
        return amount.toFixed(2)
      }
    },
    {
      title: '收益率',
      key: 'return',
      render: (_: number | undefined, record: DLBacktestResult['trades'][number]) => {
        if (record.action === 'BUY' || record.return === undefined) return '-'
        const color = record.return >= 0 ? '#34c759' : '#ff3b30'
        const sign = record.return >= 0 ? '+' : ''
        return <span style={{ color }}>{sign}{record.return.toFixed(2)}%</span>
      }
    },
  ]

  return (
    <div className="fade-in">
      {/* Page Header */}
      <div className="page-header">
        <div className="flex flex-between" style={{ flexWrap: 'wrap', gap: 'var(--space-md)' }}>
          <div>
            <h1 className="page-title">DL 预测</h1>
            <p className="page-subtitle">深度学习模型预测未来5天股票价格</p>
          </div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr 1fr', gap: 'var(--space-lg)', alignItems: 'start' }}>
        {/* Left: Configuration */}
        <Card
          title={<><LineChartOutlined style={{ marginRight: 8 }} />预测配置</>}
          style={{ position: 'sticky', top: 80 }}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
            {/* Stock Selection */}
            <div>
              <StockSearch
                value={stockCode ?? undefined}
                onChange={(code) => setStockCode(code)}
              />
            </div>

            {/* Kline Days */}
            <div>
              <label style={{
                display: 'block',
                fontSize: 'var(--font-size-sm)',
                color: 'var(--color-text-secondary)',
                marginBottom: 'var(--space-xs)'
              }}>
                历史K线天数
              </label>
              <InputNumber
                value={klineDays}
                onChange={(value) => setKlineDays(value ?? 60)}
                min={30}
                max={250}
                step={10}
                style={{ width: '100%' }}
              />
            </div>

            {/* Buttons */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)', marginTop: 'var(--space-md)' }}>
              <Button
                type="primary"
                icon={<LoadingOutlined spin={loadingPredict} />}
                onClick={handlePredict}
                loading={loadingPredict}
                disabled={!stockCode}
                block
              >
                预测未来5天
              </Button>
            </div>

            <div style={{ borderTop: '1px solid var(--color-border)', paddingTop: 'var(--space-md)', marginTop: 'var(--space-md)' }}>
              <label style={{
                display: 'block',
                fontSize: 'var(--font-size-sm)',
                color: 'var(--color-text-secondary)',
                marginBottom: 'var(--space-xs)'
              }}>
                回测区间
              </label>
              <RangePicker
                value={[dayjs(dateRange[0]), dayjs(dateRange[1])]}
                onChange={(dates) => {
                  if (dates) {
                    setDateRange([dates[0]!.format('YYYY-MM-DD'), dates[1]!.format('YYYY-MM-DD')])
                  }
                }}
                style={{ width: '100%' }}
              />

              <label style={{
                display: 'block',
                fontSize: 'var(--font-size-sm)',
                color: 'var(--color-text-secondary)',
                marginBottom: 'var(--space-xs)',
                marginTop: 'var(--space-md)'
              }}>
                初始资金
              </label>
              <InputNumber
                value={initialCapital}
                onChange={(value) => setInitialCapital(value ?? 100000)}
                min={10000}
                step={10000}
                style={{ width: '100%' }}
                formatter={(value) => `${value}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}
                parser={(value) => Number(value!.replace(/\$\s?|(,*)/g, ''))}
              />

              <Button
                type="primary"
                icon={<PlayCircleOutlined />}
                onClick={handleBacktest}
                loading={loadingBacktest}
                disabled={!stockCode}
                style={{ marginTop: 'var(--space-md)', width: '100%' }}
              >
                执行回测
              </Button>
            </div>
          </div>
        </Card>

        {/* Middle: Chart */}
        <Card
          title={backtestResult ? '回测图表' : '价格走势'}
          style={{ minHeight: 400 }}
        >
          {loadingBacktest ? (
            <div className="loading-container">
              <Spin indicator={<LoadingOutlined style={{ fontSize: 32 }} spin />} />
            </div>
          ) : backtestResult ? (
            <ReactECharts
              option={getBacktestChartOption()}
              style={{ height: 400 }}
              opts={{ renderer: 'canvas' }}
            />
          ) : loadingPredict ? (
            <div className="loading-container">
              <Spin indicator={<LoadingOutlined style={{ fontSize: 32 }} spin />} />
            </div>
          ) : predictionResult ? (
            <ReactECharts
              ref={chartRef}
              option={getChartOption()}
              style={{ height: 400 }}
              opts={{ renderer: 'canvas' }}
            />
          ) : (
            <Empty
              description="点击「预测未来5天」或「执行回测」查看图表"
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              style={{ padding: 'var(--space-2xl)' }}
            />
          )}
        </Card>

        {/* Right: Results */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-lg)' }}>
          {/* Prediction Results */}
          {predictionResult && (
            <Card title="预测结果">
              <Descriptions column={1} size="small" bordered>
                <Descriptions.Item label="股票代码">{predictionResult.stock_code}</Descriptions.Item>
                <Descriptions.Item label="当前价格">{predictionResult.current_price.toFixed(2)}</Descriptions.Item>
                <Descriptions.Item label="最后交易日">{predictionResult.last_date}</Descriptions.Item>
              </Descriptions>

              <div style={{ marginTop: 'var(--space-md)' }}>
                <h4 style={{ marginBottom: 'var(--space-sm)' }}>未来5天预测</h4>
                <Table
                  dataSource={predictionResult.prediction_dates.map((date, index) => ({
                    key: index,
                    date,
                    predicted_price: predictionResult.predicted_prices[index],
                    change: index > 0
                      ? ((predictionResult.predicted_prices[index] - predictionResult.predicted_prices[index - 1]) / predictionResult.predicted_prices[index - 1] * 100).toFixed(2)
                      : ((predictionResult.predicted_prices[0] - predictionResult.current_price) / predictionResult.current_price * 100).toFixed(2)
                  }))}
                  columns={[
                    { title: '日期', dataIndex: 'date', key: 'date' },
                    {
                      title: '预测价格',
                      dataIndex: 'predicted_price',
                      key: 'predicted_price',
                      render: (v: number) => v.toFixed(2)
                    },
                    {
                      title: '涨跌幅',
                      dataIndex: 'change',
                      key: 'change',
                      render: (v: string) => (
                        <span style={{ color: Number(v) >= 0 ? '#34c759' : '#ff3b30' }}>
                          {Number(v) >= 0 ? '+' : ''}{v}%
                        </span>
                      )
                    }
                  ]}
                  pagination={false}
                  size="small"
                />
              </div>
            </Card>
          )}

          {/* Backtest Results */}
          {backtestResult && (
            <Card title="回测结果">
              <Descriptions column={2} size="small" bordered>
                <Descriptions.Item label="总收益率">
                  <span style={{ color: backtestResult.total_return >= 0 ? '#34c759' : '#ff3b30' }}>
                    {backtestResult.total_return.toFixed(2)}%
                  </span>
                </Descriptions.Item>
                <Descriptions.Item label="年化收益率">
                  <span style={{ color: backtestResult.annualized_return >= 0 ? '#34c759' : '#ff3b30' }}>
                    {backtestResult.annualized_return.toFixed(2)}%
                  </span>
                </Descriptions.Item>
                <Descriptions.Item label="夏普比率">{backtestResult.sharpe_ratio.toFixed(4)}</Descriptions.Item>
                <Descriptions.Item label="最大回撤">
                  {backtestResult.max_drawdown.toFixed(2)}%
                </Descriptions.Item>
                <Descriptions.Item label="胜率">{backtestResult.win_rate.toFixed(2)}%</Descriptions.Item>
                <Descriptions.Item label="交易次数">{backtestResult.total_trades}</Descriptions.Item>
              </Descriptions>

              <div style={{ marginTop: 'var(--space-md)' }}>
                <h4 style={{ marginBottom: 'var(--space-sm)' }}>交易记录</h4>
                <Table
                  dataSource={backtestResult.trades}
                  columns={tradeColumns}
                  rowKey={(record, index) => `${record.date}-${index}`}
                  size="small"
                  pagination={{ pageSize: 10 }}
                  scroll={{ y: 300 }}
                />
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}

export default DLPrediction
