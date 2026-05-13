import { useState, useEffect } from 'react'
import { Form, InputNumber, Button, Spin, Table, DatePicker, Select, Input } from 'antd'
import { PlayCircleOutlined } from '@ant-design/icons'
import ReactECharts from 'echarts-for-react'
import dayjs from 'dayjs'
import { getStrategies, runStrategyBacktest } from '../services/api'
import StockSearch from '../components/StockSearch'
import { logger } from '../utils/logger'
import type { StrategyInfo, StrategyBacktestResponse, StrategyParamConfig } from '../types'

const { RangePicker } = DatePicker

interface BacktestFormValues {
  stockCode: string
  strategyName: string
  dateRange: [dayjs.Dayjs, dayjs.Dayjs]
  initialCapital: number
  [key: string]: unknown
}

function Backtest() {
  const [form] = Form.useForm()
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState<StrategyBacktestResponse | null>(null)
  const [strategies, setStrategies] = useState<StrategyInfo[]>([])
  const [selectedStrategy, setSelectedStrategy] = useState<StrategyInfo | null>(null)

  useEffect(() => {
    getStrategies()
      .then((list) => {
        setStrategies(list)
        if (list.length > 0) {
          const maCross = list.find((s) => s.name === 'ma_cross')
          const initial = maCross || list[0]
          setSelectedStrategy(initial)
          form.setFieldsValue({ strategyName: initial.name })
        }
      })
      .catch((err) => logger.error('Failed to load strategies', err))
  }, [form])

  const handleStrategyChange = (name: string) => {
    const s = strategies.find((st) => st.name === name) || null
    setSelectedStrategy(s)
    // Reset parameter fields
    if (s) {
      const paramValues: Record<string, unknown> = {}
      Object.entries(s.parameters).forEach(([key, cfg]) => {
        paramValues[key] = cfg.default
      })
      form.setFieldsValue(paramValues)
    }
  }

  const handleSubmit = async (values: BacktestFormValues) => {
    if (!selectedStrategy) return

    setRunning(true)
    setResult(null)
    try {
      // Collect dynamic parameters
      const parameters: Record<string, number | string> = {}
      Object.keys(selectedStrategy.parameters).forEach((key) => {
        const val = values[key]
        if (val !== undefined && val !== null) {
          parameters[key] = val as number | string
        }
      })

      const request = {
        strategy_name: selectedStrategy.name,
        stock_code: values.stockCode,
        start_date: values.dateRange[0].format('YYYY-MM-DD'),
        end_date: values.dateRange[1].format('YYYY-MM-DD'),
        initial_capital: values.initialCapital || 100000,
        parameters,
      }

      const backtestResult = await runStrategyBacktest(request)
      setResult(backtestResult)
    } catch (error: unknown) {
      logger.error('回测失败', error)
    } finally {
      setRunning(false)
    }
  }

  const renderParamField = (name: string, config: StrategyParamConfig) => {
    const commonProps = {
      style: { width: '100%' },
      placeholder: config.description,
    }

    switch (config.type) {
      case 'slider': {
        const isFloat = (config.step || 1) < 1 || typeof config.default === 'number' && !Number.isInteger(config.default)
        return (
          <Form.Item key={name} name={name} label={name} initialValue={config.default}>
            <InputNumber
              {...commonProps}
              min={config.min}
              max={config.max}
              step={config.step || (isFloat ? 0.1 : 1)}
            />
          </Form.Item>
        )
      }
      case 'select':
        return (
          <Form.Item key={name} name={name} label={name} initialValue={config.default}>
            <Select {...commonProps}>
              {(config.options || []).map((opt) => (
                <Select.Option key={String(opt.value)} value={opt.value}>
                  {opt.label}
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
        )
      case 'input':
      default:
        return (
          <Form.Item key={name} name={name} label={name} initialValue={config.default}>
            <Input {...commonProps} />
          </Form.Item>
        )
    }
  }

  const getChartOption = () => {
    if (!result || !result.trades.length) return {}

    const trades = result.trades
    const dates: string[] = []
    const capital: number[] = []
    let currentCapital = result.initial_capital

    trades.forEach((trade) => {
      dates.push(trade.trade_date || trade.date || '')
      if (trade.action === 'buy') {
        currentCapital -= trade.amount
      } else {
        currentCapital += trade.amount
      }
      capital.push(currentCapital)
    })

    dates.push(result.end_date)
    capital.push(result.final_capital)

    return {
      tooltip: {
        trigger: 'axis',
        backgroundColor: '#fff',
        borderColor: 'var(--color-border)',
        textStyle: { color: 'var(--color-text-primary)' }
      },
      grid: { left: '10%', right: '5%', bottom: '10%', top: '15%' },
      xAxis: {
        type: 'category',
        data: dates,
        axisLine: { lineStyle: { color: 'var(--color-border)' } },
        axisLabel: { color: 'var(--color-text-tertiary)', fontSize: 10 }
      },
      yAxis: {
        type: 'value',
        name: '资金(元)',
        axisLine: { show: false },
        axisLabel: { color: 'var(--color-text-tertiary)', fontSize: 10 },
        splitLine: { lineStyle: { color: 'var(--color-border-light)', type: 'dashed' } }
      },
      series: [{
        data: capital,
        type: 'line',
        smooth: true,
        lineStyle: { color: '#0071e3', width: 2 },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(0, 113, 227, 0.15)' },
              { offset: 1, color: 'rgba(0, 113, 227, 0)' }
            ]
          }
        }
      }]
    }
  }

  const tradeColumns = [
    {
      title: '日期',
      dataIndex: 'trade_date',
      key: 'trade_date',
      width: 120,
      render: (_: string, record: { trade_date?: string; date?: string }) => record.trade_date || record.date || '-'
    },
    {
      title: '操作',
      dataIndex: 'action',
      key: 'action',
      width: 80,
      render: (action: string) => (
        <span style={{
          color: action === 'buy' ? 'var(--color-danger)' : 'var(--color-success)',
          fontWeight: 500
        }}>
          {action === 'buy' ? '买入' : '卖出'}
        </span>
      )
    },
    { title: '价格', dataIndex: 'price', key: 'price', width: 100 },
    { title: '数量', dataIndex: 'quantity', key: 'quantity', width: 100 },
    { title: '金额', dataIndex: 'amount', key: 'amount', width: 120 }
  ]

  const StatBox = ({ label, value, suffix = '', color }: {
    label: string
    value: number | string
    suffix?: string
    color?: string
  }) => (
    <div className="stat-card">
      <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-secondary)', marginBottom: 4 }}>
        {label}
      </div>
      <div className="stat-value" style={{ fontSize: 'var(--font-size-xl)', color: color || 'var(--color-text-primary)' }}>
        {typeof value === 'number' ? value.toLocaleString() : value}{suffix}
      </div>
    </div>
  )

  // Use either new-style (metrics) or legacy (top-level) result fields
  const m = result?.metrics
  const totalReturn = m?.total_return ?? 0
  const annualReturn = m?.annual_return ?? 0
  const sharpeRatio = m?.sharpe_ratio ?? 0
  const maxDrawdown = m?.max_drawdown ?? 0
  const winRate = m?.win_rate ?? 0
  const profitFactor = m?.profit_factor ?? 0
  const totalTrades = m?.total_trades ?? 0

  return (
    <div className="fade-in">
      <div className="page-header">
        <h1 className="page-title">策略回测</h1>
        <p className="page-subtitle">
          {selectedStrategy
            ? `${selectedStrategy.description}`
            : '选择策略并运行回测'}
        </p>
      </div>

      <div className="grid" style={{ gridTemplateColumns: '340px 1fr', gap: 'var(--space-lg)' }}>
        {/* 参数配置 */}
        <div style={{ background: 'var(--color-canvas-lifted)', borderRadius: '40px' }}>
          <div style={{ fontSize: 'var(--font-size-md)', fontWeight: 600, marginBottom: 'var(--space-lg)' }}>
            回测参数
          </div>
          <Form
            form={form}
            layout="vertical"
            onFinish={handleSubmit}
            initialValues={{
              stockCode: undefined,
              strategyName: strategies[0]?.name || 'ma_cross',
              dateRange: [dayjs('2020-01-01'), dayjs('2025-12-31')],
              initialCapital: 100000,
            }}
          >
            <Form.Item name="strategyName" label="策略" rules={[{ required: true }]}>
              <Select onChange={handleStrategyChange} placeholder="选择策略">
                {strategies.map((s) => (
                  <Select.Option key={s.name} value={s.name}>
                    {s.name} - {s.description.slice(0, 40)}...
                  </Select.Option>
                ))}
              </Select>
            </Form.Item>

            <Form.Item name="stockCode" label="股票" rules={[{ required: true }]}>
              <StockSearch />
            </Form.Item>

            <Form.Item name="dateRange" label="回测区间" rules={[{ required: true }]}>
              <RangePicker style={{ width: '100%' }} />
            </Form.Item>

            <Form.Item name="initialCapital" label="初始资金">
              <InputNumber min={10000} max={10000000} style={{ width: '100%' }} />
            </Form.Item>

            {/* Dynamic strategy parameters */}
            {selectedStrategy && Object.entries(selectedStrategy.parameters).map(([name, config]) =>
              renderParamField(name, config)
            )}

            <Form.Item>
              <Button
                type="primary"
                htmlType="submit"
                icon={<PlayCircleOutlined />}
                loading={running}
                block
                size="large"
              >
                运行回测
              </Button>
            </Form.Item>
          </Form>
        </div>

        {/* 结果展示 */}
        <div>
          {running && (
            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 400, background: 'var(--color-canvas-lifted)', borderRadius: '40px' }}>
              <Spin size="large" tip="回测运行中..." />
            </div>
          )}

          {!running && result && (
            <div>
              {/* 统计指标 */}
              <div className="grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)', marginBottom: 'var(--space-md)' }}>
                <StatBox
                  label="总收益率"
                  value={totalReturn.toFixed(2)}
                  suffix="%"
                  color={totalReturn > 0 ? 'var(--color-success)' : 'var(--color-danger)'}
                />
                <StatBox
                  label="年化收益率"
                  value={annualReturn.toFixed(2)}
                  suffix="%"
                  color={annualReturn > 0 ? 'var(--color-success)' : 'var(--color-danger)'}
                />
                <StatBox
                  label="夏普比率"
                  value={sharpeRatio.toFixed(2)}
                />
                <StatBox
                  label="最大回撤"
                  value={maxDrawdown.toFixed(2)}
                  suffix="%"
                  color="var(--color-danger)"
                />
              </div>

              <div className="grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)', marginBottom: 'var(--space-lg)' }}>
                <StatBox label="胜率" value={winRate.toFixed(2)} suffix="%" />
                <StatBox label="交易次数" value={totalTrades} />
                <StatBox label="盈亏比" value={profitFactor.toFixed(2)} />
                <StatBox label="最终资金" value={result.final_capital} suffix="元" color="var(--color-ink)" />
              </div>

              {/* 资金曲线 */}
              <div style={{ marginBottom: 'var(--space-md)', padding: 'var(--space-md)', background: 'var(--color-canvas-lifted)', borderRadius: '40px' }}>
                <div style={{ fontSize: 'var(--font-size-sm)', fontWeight: 600, marginBottom: 'var(--space-sm)', color: 'var(--color-text-secondary)' }}>
                  资金曲线
                </div>
                <ReactECharts option={getChartOption()} style={{ height: 280 }} />
              </div>

              {/* 交易记录 */}
              <div style={{ background: 'var(--color-canvas-lifted)', borderRadius: '40px' }}>
                <div style={{ fontSize: 'var(--font-size-md)', fontWeight: 600, marginBottom: 'var(--space-md)' }}>
                  交易记录
                </div>
                <Table
                  columns={tradeColumns}
                  dataSource={result.trades}
                  rowKey="id"
                  pagination={{ pageSize: 10 }}
                  size="small"
                />
              </div>
            </div>
          )}

          {!running && !result && (
            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 400, background: 'var(--color-canvas-lifted)', borderRadius: '40px' }}>
              <div style={{ textAlign: 'center', color: 'var(--color-text-secondary)' }}>
                <div style={{ fontSize: 48, marginBottom: 'var(--space-md)' }}>📊</div>
                <div>选择策略和参数，然后点击"运行回测"</div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default Backtest