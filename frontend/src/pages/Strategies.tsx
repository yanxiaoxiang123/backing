import { useState, useEffect, useRef } from 'react'
import {
  Card,
  Select,
  InputNumber,
  DatePicker,
  Button,
  Spin,
  Empty,
  Slider,
  message,
  Tag,
  Descriptions,
  Table,
  Tabs
} from 'antd'
import { LoadingOutlined, PlayCircleOutlined, ThunderboltOutlined, LineChartOutlined, BarChartOutlined } from '@ant-design/icons'
import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'
import {
  getStrategies,
  generateSignals,
  runStrategyBacktest,
  submitOptimizeParameters,
  getJobStatus,
  getStockIndicators,
  compareStrategies,
} from '../services/api'
import StockSearch from '../components/StockSearch'
import type {
  StrategyInfo,
  SignalDataPoint,
  SignalStats,
  StrategyBacktestResponse,
  OptimizeResponse,
  CompareResponse,
  CompareStrategyResult,
} from '../types'
import { logger } from '../utils/logger'
import { usePersistedState } from '../hooks/usePersistedState'
import dayjs from 'dayjs'

const { RangePicker } = DatePicker

// Predefined strategies with metadata
const STRATEGY_METADATA: Record<string, { name: string; description: string; color: string }> = {
  'MA Cross': {
    name: 'MA Cross',
    description: 'Moving Average Crossover strategy using short and long period MA signals',
    color: '#0071e3'
  },
  'Mean Reversion': {
    name: 'Mean Reversion',
    description: 'Buy when price deviates below moving average, sell when above',
    color: '#34c759'
  },
  'Momentum': {
    name: 'Momentum',
    description: 'Follow strong price trends using momentum indicators',
    color: '#ff9500'
  },
  'Breakout': {
    name: 'Breakout',
    description: 'Trade price breakouts above resistance or below support levels',
    color: '#ff3b30'
  },
  'RSI Reversal': {
    name: 'RSI Reversal',
    description: 'Buy oversold (RSI<30) and sell overbought (RSI>70) conditions',
    color: '#af52de'
  },
  'MACD Cross': {
    name: 'MACD Cross',
    description: 'Trade MACD line crossovers with signal line',
    color: '#5856d6'
  },
  'Dual Thrust': {
    name: 'Dual Thrust',
    description: 'Classic breakout strategy using yesterday\'s price range',
    color: '#ff2d55'
  },
  'lstm_5d': {
    name: 'LSTM 5D',
    description: 'Predict 5-day close price and generate threshold-based signals',
    color: '#0a84ff'
  }
}

function Strategies() {
  const chartRef = useRef<ReactECharts>(null)

  // State
  const [strategies, setStrategies] = useState<StrategyInfo[]>([])
  const [selectedStrategy, setSelectedStrategy] = usePersistedState<string | null>('strategies_selectedStrategy', null)
  const [loadingStrategies, setLoadingStrategies] = useState(true)
  const [loadingSignals, setLoadingSignals] = useState(false)
  const [loadingBacktest, setLoadingBacktest] = useState(false)
  const [loadingOptimize, setLoadingOptimize] = useState(false)

  // Form state
  const [stockCode, setStockCode] = usePersistedState<string | null>('strategies_stockCode', null)
  const [dateRange, setDateRange] = usePersistedState<[string, string]>('strategies_dateRange', [
    dayjs().subtract(1, 'year').format('YYYY-MM-DD'),
    dayjs().format('YYYY-MM-DD')
  ])
  const [initialCapital, setInitialCapital] = usePersistedState('strategies_initialCapital', 100000)
  const [parameters, setParameters] = useState<Record<string, number | string>>({})

  // Results state
  const [signals, setSignals] = useState<SignalDataPoint[]>([])
  const [signalStats, setSignalStats] = useState<SignalStats | null>(null)
  const [backtestResult, setBacktestResult] = useState<StrategyBacktestResponse | null>(null)
  const [optimizeResult, setOptimizeResult] = useState<OptimizeResponse | null>(null)
  const [klineData, setKlineData] = useState<{ date: string; open: number; close: number; high: number; low: number; volume: number }[]>([])

  // Comparison state
  const [compareResult, setCompareResult] = useState<CompareResponse | null>(null)
  const [loadingCompare, setLoadingCompare] = useState(false)

  // Load strategies and stocks on mount
  useEffect(() => {
    loadData()
  }, [])

  // Update parameters when strategy changes
  useEffect(() => {
    if (selectedStrategy && strategies.length > 0) {
      const strategy = strategies.find(s => s.name === selectedStrategy)
      if (strategy) {
        const defaultParams: Record<string, number | string> = {}
        Object.entries(strategy.parameters).forEach(([key, config]) => {
          defaultParams[key] = config.default
        })
        setParameters(defaultParams)
      }
    }
  }, [selectedStrategy, strategies])

  const loadData = async () => {
    try {
      setLoadingStrategies(true)
      const strategiesData = await getStrategies()
      setStrategies(strategiesData)
    } catch (error) {
      message.error('加载数据失败')
      logger.error(error)
    } finally {
      setLoadingStrategies(false)
    }
  }

  const handleGenerateSignals = async () => {
    if (!selectedStrategy || !stockCode || !dateRange[0] || !dateRange[1]) {
      message.warning('请选择策略、股票和日期范围')
      return
    }

    setLoadingSignals(true)
    setBacktestResult(null)
    setOptimizeResult(null)
    try {
      const response = await generateSignals({
        strategy_name: selectedStrategy,
        stock_code: stockCode,
        start_date: dateRange[0],
        end_date: dateRange[1],
        parameters
      })
      setSignals(response.data)
      setSignalStats(response.stats ?? null)

      // Fetch kline data for chart
      const klineResponse = await getStockIndicators(stockCode, 'daily', dateRange[0], dateRange[1])
      if (klineResponse.data) {
        setKlineData(klineResponse.data)
      }
    } catch (error) {
      message.error('生成信号失败')
      logger.error(error)
    } finally {
      setLoadingSignals(false)
    }
  }

  const handleRunBacktest = async () => {
    if (!selectedStrategy || !stockCode || !dateRange[0] || !dateRange[1]) {
      message.warning('请选择策略、股票和日期范围')
      return
    }

    setLoadingBacktest(true)
    try {
      const response = await runStrategyBacktest({
        strategy_name: selectedStrategy,
        stock_code: stockCode,
        start_date: dateRange[0],
        end_date: dateRange[1],
        initial_capital: initialCapital,
        parameters
      })
      setBacktestResult(response)
      setSignals([])
    } catch (error) {
      message.error('回测执行失败')
      logger.error(error)
    } finally {
      setLoadingBacktest(false)
    }
  }

  const handleOptimize = async () => {
    if (!selectedStrategy || !stockCode || !dateRange[0] || !dateRange[1]) {
      message.warning('请选择策略、股票和日期范围')
      return
    }

    setLoadingOptimize(true)
    try {
      // Build param grid from current strategy
      const strategy = strategies.find(s => s.name === selectedStrategy)
      if (!strategy) return

      const paramGrid: Record<string, number[]> = {}
      Object.entries(strategy.parameters).forEach(([key, config]) => {
        if (config.type === 'slider' && config.min !== undefined && config.max !== undefined) {
          if (selectedStrategy === 'lstm_5d' && !['buy_threshold', 'sell_threshold', 'min_confidence'].includes(key)) {
            return
          }
          const step = config.step || 1
          const values: number[] = []
          for (let v = config.min; v <= config.max; v += step) {
            values.push(v)
          }
          paramGrid[key] = values
        }
      })

      if (Object.keys(paramGrid).length === 0) {
        message.warning('当前策略无可优化参数')
        return
      }

      const submission = await submitOptimizeParameters({
        strategy_name: selectedStrategy,
        stock_code: stockCode,
        start_date: dateRange[0],
        end_date: dateRange[1],
        initial_capital: initialCapital,
        param_grid: paramGrid,
        metric: 'sharpe_ratio'
      })
      const response = await waitForJob<OptimizeResponse>(submission.job_id)
      setOptimizeResult(response)

      // Apply best parameters
      setParameters(response.best_params)
      message.success(`优化完成，最佳夏普比率: ${response.best_score.toFixed(4)}`)
    } catch (error) {
      message.error('参数优化失败')
      logger.error(error)
    } finally {
      setLoadingOptimize(false)
    }
  }

  const handleCompare = async () => {
    if (!stockCode || !dateRange[0] || !dateRange[1]) {
      message.warning('请选择股票和日期范围')
      return
    }
    setLoadingCompare(true)
    setCompareResult(null)
    try {
      const response = await compareStrategies({
        stock_code: stockCode,
        start_date: dateRange[0],
        end_date: dateRange[1],
        initial_capital: initialCapital,
      })
      setCompareResult(response)
      message.success(`对比完成: ${response.total_strategies} 个策略`)
    } catch (error) {
      message.error('策略对比失败')
      logger.error(error)
    } finally {
      setLoadingCompare(false)
    }
  }

  const waitForJob = async <T,>(jobId: string): Promise<T> => {
    while (true) {
      const job = await getJobStatus<T>(jobId)
      if (job.status === 'completed') {
        return job.result as T
      }
      if (job.status === 'failed') {
        throw new Error(job.error || job.message || '任务执行失败')
      }
      await new Promise(resolve => setTimeout(resolve, 1500))
    }
  }

  const getChartOption = (): EChartsOption => {
    if (klineData.length === 0 && signals.length === 0) {
      return {}
    }

    const dates = klineData.map(d => d.date)
    const ohlc = klineData.map(d => [d.open, d.close, d.low, d.high])

    // Prepare signal markers
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

    // Add trade markers from backtest result
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

  const renderParameterInputs = () => {
    if (!selectedStrategy) return null

    const strategy = strategies.find(s => s.name === selectedStrategy)
    if (!strategy) return null

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
        {Object.entries(strategy.parameters).map(([key, config]) => (
          <div key={key}>
            <label style={{
              display: 'block',
              fontSize: 'var(--font-size-sm)',
              color: 'var(--color-text-secondary)',
              marginBottom: 'var(--space-xs)'
            }}>
              {key}
              {config.description && <span style={{ marginLeft: 8, fontWeight: 400 }}>({config.description})</span>}
            </label>
            {config.type === 'slider' && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-md)' }}>
                <Slider
                  min={config.min}
                  max={config.max}
                  step={config.step}
                  value={Number(parameters[key] ?? config.default)}
                  onChange={(value) => setParameters(prev => ({ ...prev, [key]: Number(value) }))}
                  style={{ flex: 1 }}
                />
                <InputNumber
                  min={config.min}
                  max={config.max}
                  step={config.step}
                  value={Number(parameters[key] ?? config.default)}
                  onChange={(value) => setParameters(prev => ({ ...prev, [key]: Number(value ?? 0) }))}
                  style={{ width: 80 }}
                />
              </div>
            )}
            {config.type === 'input' && (
              <InputNumber
                min={config.min}
                max={config.max}
                step={config.step}
                value={Number(parameters[key] ?? config.default)}
                onChange={(value) => setParameters(prev => ({ ...prev, [key]: Number(value ?? 0) }))}
                style={{ width: '100%' }}
              />
            )}
            {config.type === 'select' && config.options && (
              <Select
                value={parameters[key] ?? config.default}
                onChange={(value) => setParameters(prev => ({ ...prev, [key]: value }))}
                style={{ width: '100%' }}
                options={config.options.map(opt => ({
                  value: opt.value,
                  label: opt.label
                }))}
              />
            )}
          </div>
        ))}
      </div>
    )
  }

  const tradeColumns = [
    { title: '日期', dataIndex: 'date', key: 'date' },
    {
      title: '操作',
      dataIndex: 'action',
      key: 'action',
      render: (action: string) => (
        <Tag color={action === 'buy' ? 'green' : 'red'}>
          {action === 'buy' ? '买入' : '卖出'}
        </Tag>
      )
    },
    { title: '价格', dataIndex: 'price', key: 'price', render: (v: number) => v.toFixed(2) },
    { title: '数量', dataIndex: 'quantity', key: 'quantity' },
    { title: '金额', dataIndex: 'amount', key: 'amount', render: (v: number) => v.toFixed(2) }
  ]

  const optimizeColumns = [
    {
      title: '参数',
      dataIndex: 'params',
      key: 'params',
      render: (params: Record<string, number>) => (
        <span>
          {Object.entries(params).map(([k, v]) => `${k}: ${v}`).join(', ')}
        </span>
      )
    },
    { title: '夏普比率', dataIndex: 'score', key: 'score', render: (v: number) => v.toFixed(4) },
    {
      title: '收益率',
      dataIndex: 'metrics',
      key: 'total_return',
      render: (m: Record<string, number>) => `${m.total_return.toFixed(2)}%`
    },
    {
      title: '胜率',
      dataIndex: 'metrics',
      key: 'win_rate',
      render: (m: Record<string, number>) => `${m.win_rate.toFixed(2)}%`
    }
  ]

  const COMPARE_COLORS = ['#0071e3', '#34c759', '#ff9500', '#ff3b30', '#af52de', '#5856d6', '#ff2d55', '#0a84ff']

  const getCompareChartOption = (): EChartsOption => {
    if (!compareResult || compareResult.results.length === 0) return {}

    // Collect all unique dates from all equity curves
    const dateSet = new Set<string>()
    const seriesData: { name: string; type: 'line'; data: [string, number][]; lineStyle: { color: string; width: number }; smooth: boolean; symbol: 'none' }[] = []

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
          params.map((p) => `${p.seriesName}: ¥${Number(p.value[1]).toLocaleString()}`).join('<br/>')
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
          handleStyle: { color: 'var(--color-accent)' },
        },
      ],
      series: seriesData,
    }
  }

  const compareColumns = [
    {
      title: '策略',
      dataIndex: 'strategy_name',
      key: 'strategy_name',
      render: (name: string, _: unknown, index: number) => (
        <span style={{ color: COMPARE_COLORS[index % COMPARE_COLORS.length], fontWeight: 600 }}>
          {name}
        </span>
      ),
    },
    {
      title: '总收益率',
      dataIndex: ['metrics', 'total_return'],
      key: 'total_return',
      sorter: (a: CompareStrategyResult, b: CompareStrategyResult) => a.metrics.total_return - b.metrics.total_return,
      render: (v: number) => <span style={{ color: v >= 0 ? '#34c759' : '#ff3b30', fontWeight: 600 }}>{v.toFixed(2)}%</span>,
    },
    {
      title: '夏普比率',
      dataIndex: ['metrics', 'sharpe_ratio'],
      key: 'sharpe_ratio',
      sorter: (a: CompareStrategyResult, b: CompareStrategyResult) => a.metrics.sharpe_ratio - b.metrics.sharpe_ratio,
      render: (v: number) => v.toFixed(4),
    },
    {
      title: '最大回撤',
      dataIndex: ['metrics', 'max_drawdown'],
      key: 'max_drawdown',
      sorter: (a: CompareStrategyResult, b: CompareStrategyResult) => a.metrics.max_drawdown - b.metrics.max_drawdown,
      render: (v: number) => <span style={{ color: '#ff3b30' }}>{v.toFixed(2)}%</span>,
    },
    {
      title: '胜率',
      dataIndex: ['metrics', 'win_rate'],
      key: 'win_rate',
      sorter: (a: CompareStrategyResult, b: CompareStrategyResult) => a.metrics.win_rate - b.metrics.win_rate,
      render: (v: number) => `${v.toFixed(2)}%`,
    },
    {
      title: '交易次数',
      dataIndex: ['metrics', 'total_trades'],
      key: 'total_trades',
      sorter: (a: CompareStrategyResult, b: CompareStrategyResult) => a.metrics.total_trades - b.metrics.total_trades,
    },
  ]

  return (
    <div className="fade-in">
      {/* Page Header */}
      <div className="page-header">
        <div className="flex flex-between" style={{ flexWrap: 'wrap', gap: 'var(--space-md)' }}>
          <div>
            <h1 className="page-title">策略研究</h1>
            <p className="page-subtitle">选择策略、配置参数、执行回测</p>
          </div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr 1fr', gap: 'var(--space-lg)', alignItems: 'start' }}>
        {/* Left: Strategy List */}
        <Card
          title={<><LineChartOutlined style={{ marginRight: 8 }} />策略列表</>}
          loading={loadingStrategies}
          style={{ position: 'sticky', top: 80 }}
          bodyStyle={{ padding: 'var(--space-sm)', maxHeight: 'calc(100vh - 180px)', overflowY: 'auto' }}
        >
          {strategies.map(strategy => {
            const meta = STRATEGY_METADATA[strategy.name] || { name: strategy.name, description: strategy.description, color: '#86868b' }
            const isSelected = selectedStrategy === strategy.name

            return (
              <div
                key={strategy.name}
                onClick={() => setSelectedStrategy(strategy.name)}
                style={{
                  padding: 'var(--space-md)',
                  marginBottom: 'var(--space-sm)',
                  borderRadius: 'var(--radius-md)',
                  cursor: 'pointer',
                  border: `2px solid ${isSelected ? meta.color : 'transparent'}`,
                  background: isSelected ? `${meta.color}10` : 'var(--color-bg-secondary)',
                  transition: 'all var(--transition-fast)'
                }}
              >
                <div style={{
                  fontWeight: 600,
                  fontSize: 'var(--font-size-sm)',
                  color: isSelected ? meta.color : 'var(--color-text-primary)',
                  marginBottom: 'var(--space-xs)'
                }}>
                  {meta.name}
                </div>
                <div style={{
                  fontSize: 'var(--font-size-xs)',
                  color: 'var(--color-text-secondary)',
                  lineHeight: 1.4
                }}>
                  {meta.description}
                </div>
              </div>
            )
          })}
        </Card>

        {/* Middle: Configuration */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-lg)' }}>
          {/* Strategy Parameters */}
          <Card
            title="策略参数"
            style={{ opacity: selectedStrategy ? 1 : 0.6 }}
          >
            {selectedStrategy ? (
              renderParameterInputs()
            ) : (
              <Empty description="请选择策略" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            )}
          </Card>

          {/* Backtest Configuration */}
          <Card title="回测配置">
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
              <div>
                <label style={{
                  display: 'block',
                  fontSize: 'var(--font-size-sm)',
                  color: 'var(--color-text-secondary)',
                  marginBottom: 'var(--space-xs)'
                }}>
                  股票代码
                </label>
                <StockSearch
                  value={stockCode ?? undefined}
                  onChange={(code) => setStockCode(code)}
                />
              </div>

              <div>
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
              </div>

              <div>
                <label style={{
                  display: 'block',
                  fontSize: 'var(--font-size-sm)',
                  color: 'var(--color-text-secondary)',
                  marginBottom: 'var(--space-xs)'
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
              </div>

              <div style={{ display: 'flex', gap: 'var(--space-sm)', marginTop: 'var(--space-md)' }}>
                <Button
                  type="primary"
                  icon={<LoadingOutlined spin={loadingSignals} />}
                  onClick={handleGenerateSignals}
                  loading={loadingSignals}
                  disabled={!selectedStrategy || !stockCode}
                  style={{ flex: 1 }}
                >
                  生成信号
                </Button>
                <Button
                  type="primary"
                  icon={<PlayCircleOutlined />}
                  onClick={handleRunBacktest}
                  loading={loadingBacktest}
                  disabled={!selectedStrategy || !stockCode}
                  style={{ flex: 1 }}
                >
                  执行回测
                </Button>
                <Button
                  icon={<ThunderboltOutlined />}
                  onClick={handleOptimize}
                  loading={loadingOptimize}
                  disabled={!selectedStrategy || !stockCode}
                >
                  参数优化
                </Button>
              </div>
              <div style={{ marginTop: 'var(--space-sm)' }}>
                <Button
                  type="primary"
                  danger
                  icon={<BarChartOutlined />}
                  onClick={handleCompare}
                  loading={loadingCompare}
                  disabled={!stockCode}
                  block
                >
                  一键对比所有策略
                </Button>
              </div>
            </div>
          </Card>
        </div>

        {/* Right: Results */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-lg)' }}>
          {/* Chart */}
          <Card
            title="信号预览"
            bodyStyle={{ padding: 0 }}
            style={{ minHeight: 400 }}
          >
            {(loadingSignals || loadingBacktest) ? (
              <div className="loading-container">
                <Spin indicator={<LoadingOutlined style={{ fontSize: 32 }} spin />} />
              </div>
            ) : (klineData.length > 0 || signals.length > 0 || backtestResult) ? (
              <ReactECharts
                ref={chartRef}
                option={getChartOption()}
                style={{ height: 400 }}
                opts={{ renderer: 'canvas' }}
              />
            ) : (
              <Empty
                description="点击「生成信号」查看K线图和信号标记"
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                style={{ padding: 'var(--space-2xl)' }}
              />
            )}
          </Card>

          {/* Signal Historical Stats */}
          {signalStats && (
            <Card title="信号历史表现" size="small" style={{ marginBottom: 'var(--space-lg)' }}>
              <Descriptions column={2} size="small" bordered>
                <Descriptions.Item label="买入信号">{signalStats.total_buy_signals}</Descriptions.Item>
                <Descriptions.Item label="卖出信号">{signalStats.total_sell_signals}</Descriptions.Item>
                <Descriptions.Item label="已完成交易">
                  <span style={{ fontWeight: 600 }}>{signalStats.total_trades}</span>
                </Descriptions.Item>
                <Descriptions.Item label="胜率">
                  <span style={{ color: signalStats.win_rate >= 50 ? '#34c759' : '#ff3b30', fontWeight: 600 }}>
                    {signalStats.win_rate}%
                  </span>
                </Descriptions.Item>
                <Descriptions.Item label="平均持仓天数">{signalStats.avg_holding_days}天</Descriptions.Item>
                <Descriptions.Item label="平均每笔收益">
                  <span style={{ color: signalStats.avg_return_per_trade >= 0 ? '#34c759' : '#ff3b30' }}>
                    {signalStats.avg_return_per_trade >= 0 ? '+' : ''}{signalStats.avg_return_per_trade}%
                  </span>
                </Descriptions.Item>
                <Descriptions.Item label="盈亏比">{signalStats.profit_ratio > 0 ? signalStats.profit_ratio.toFixed(2) : '-'}</Descriptions.Item>
                <Descriptions.Item label="最大单笔盈利">
                  <span style={{ color: '#34c759' }}>+{signalStats.max_win}%</span>
                </Descriptions.Item>
                <Descriptions.Item label="最大单笔亏损">
                  <span style={{ color: '#ff3b30' }}>{signalStats.max_loss}%</span>
                </Descriptions.Item>
                <Descriptions.Item label="最大连赢">{signalStats.consecutive_wins}次</Descriptions.Item>
                <Descriptions.Item label="最大连亏">{signalStats.consecutive_losses}次</Descriptions.Item>
              </Descriptions>
            </Card>
          )}

          {/* Backtest Results */}
          {backtestResult && (
            <Card title="回测结果">
              <Tabs
                items={[
                  {
                    key: 'metrics',
                    label: '绩效指标',
                    children: (
                      <Descriptions column={2} size="small" bordered>
                        <Descriptions.Item label="策略">{backtestResult.strategy_name}</Descriptions.Item>
                        <Descriptions.Item label="股票">{backtestResult.stock_code}</Descriptions.Item>
                        <Descriptions.Item label="初始资金">
                          {backtestResult.initial_capital.toLocaleString()}
                        </Descriptions.Item>
                        <Descriptions.Item label="最终资金">
                          {backtestResult.final_capital.toLocaleString()}
                        </Descriptions.Item>
                        <Descriptions.Item label="总收益率">
                          <span style={{ color: backtestResult.metrics.total_return >= 0 ? '#34c759' : '#ff3b30' }}>
                            {backtestResult.metrics.total_return.toFixed(2)}%
                          </span>
                        </Descriptions.Item>
                        <Descriptions.Item label="年化收益率">
                          <span style={{ color: backtestResult.metrics.annual_return >= 0 ? '#34c759' : '#ff3b30' }}>
                            {backtestResult.metrics.annual_return.toFixed(2)}%
                          </span>
                        </Descriptions.Item>
                        <Descriptions.Item label="夏普比率">{backtestResult.metrics.sharpe_ratio.toFixed(4)}</Descriptions.Item>
                        <Descriptions.Item label="最大回撤">
                          {backtestResult.metrics.max_drawdown.toFixed(2)}%
                        </Descriptions.Item>
                        <Descriptions.Item label="胜率">{backtestResult.metrics.win_rate.toFixed(2)}%</Descriptions.Item>
                        <Descriptions.Item label="交易次数">{backtestResult.metrics.total_trades}</Descriptions.Item>
                      </Descriptions>
                    )
                  },
                  {
                    key: 'trades',
                    label: '交易记录',
                    children: (
                      <Table
                        dataSource={backtestResult.trades}
                        columns={tradeColumns}
                        rowKey={(record, index) => `${record.date}-${index}`}
                        size="small"
                        pagination={{ pageSize: 10 }}
                        scroll={{ y: 300 }}
                      />
                    )
                  }
                ]}
              />
            </Card>
          )}

          {/* Optimize Results */}
          {optimizeResult && (
            <Card title="优化结果">
              <div style={{ marginBottom: 'var(--space-md)' }}>
                <Descriptions column={2} size="small" bordered>
                  <Descriptions.Item label="最优参数" span={2}>
                    {Object.entries(optimizeResult.best_params).map(([k, v]) => `${k}: ${v}`).join(', ')}
                  </Descriptions.Item>
                  <Descriptions.Item label="最优夏普比率">{optimizeResult.best_score.toFixed(4)}</Descriptions.Item>
                  <Descriptions.Item label="总收益">
                    {optimizeResult.best_metrics.total_return.toFixed(2)}%
                  </Descriptions.Item>
                </Descriptions>
              </div>
              <Table
                dataSource={optimizeResult.all_results}
                columns={optimizeColumns}
                rowKey={(record, index) => JSON.stringify(record.params) + index}
                size="small"
                pagination={{ pageSize: 20, showSizeChanger: true, showTotal: (t) => `共 ${t} 条` }}
                scroll={{ y: 300 }}
                title={() => `优化结果 (共${optimizeResult.total_combinations}种组合)`}
              />
            </Card>
          )}

          {/* Strategy Comparison Results */}
          {compareResult && (
            <Card
              title={
                <><BarChartOutlined style={{ marginRight: 8 }} />策略对比 ({compareResult.total_strategies} 个策略)</>
              }
            >
              {compareResult.failed_count > 0 && (
                <div style={{ marginBottom: 'var(--space-md)', padding: 'var(--space-sm)', background: '#fff2f0', borderRadius: 'var(--radius-sm)', color: '#ff4d4f', fontSize: 'var(--font-size-xs)' }}>
                  {compareResult.failed_count} 个策略执行失败
                </div>
              )}
              <Tabs
                items={[
                  {
                    key: 'table',
                    label: '指标对比',
                    children: (
                      <Table
                        dataSource={compareResult.results.filter(r => !r.error)}
                        columns={compareColumns}
                        rowKey="strategy_name"
                        size="small"
                        pagination={false}
                        scroll={{ y: 300 }}
                      />
                    ),
                  },
                  {
                    key: 'chart',
                    label: '资金曲线叠加',
                    children: (
                      <ReactECharts
                        option={getCompareChartOption()}
                        style={{ height: 400 }}
                        opts={{ renderer: 'canvas' }}
                      />
                    ),
                  },
                ]}
              />
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}

export default Strategies
