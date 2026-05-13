import { useState, useEffect } from 'react'
import { Table, Button, message, Modal, Spin } from 'antd'
import { EyeOutlined } from '@ant-design/icons'
import ReactECharts from 'echarts-for-react'
import { getBacktestResults, getBacktestResult, getStock } from '../services/api'
import type { BacktestListItem, BacktestResult, Stock } from '../types'

function BacktestHistory() {
  const [loading, setLoading] = useState(false)
  const [results, setResults] = useState<BacktestListItem[]>([])
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [detailVisible, setDetailVisible] = useState(false)
  const [detailLoading, setDetailLoading] = useState(false)
  const [currentResult, setCurrentResult] = useState<BacktestResult | null>(null)
  const [stockInfo, setStockInfo] = useState<Stock | null>(null)

  useEffect(() => {
    loadResults()
  }, [page, pageSize])

  const loadResults = async () => {
    setLoading(true)
    try {
      const data = await getBacktestResults(undefined, (page - 1) * pageSize, pageSize)
      setResults(data)
    } catch (error) {
      message.error('加载历史记录失败')
    } finally {
      setLoading(false)
    }
  }

  const handleViewDetail = async (id: number) => {
    setDetailVisible(true)
    setDetailLoading(true)
    setCurrentResult(null)
    try {
      const result = await getBacktestResult(id)
      setCurrentResult(result)

      const stock = await getStock(result.stock_code)
      setStockInfo(stock)
    } catch (error) {
      message.error('加载详情失败')
    } finally {
      setDetailLoading(false)
    }
  }

  const getChartOption = () => {
    if (!currentResult || !currentResult.trades.length) return {}

    const trades = currentResult.trades
    const dates: string[] = []
    const capital: number[] = []
    let currentCapital = currentResult.initial_capital

    trades.forEach((trade) => {
      dates.push(trade.trade_date || trade.date || '')
      if (trade.action === 'buy') {
        currentCapital -= trade.amount
      } else {
        currentCapital += trade.amount
      }
      capital.push(currentCapital)
    })

    dates.push(currentResult.end_date)
    capital.push(currentResult.final_capital)

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

  const columns = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 60
    },
    {
      title: '股票代码',
      dataIndex: 'stock_code',
      key: 'stock_code',
      width: 100,
      render: (code: string) => <span style={{ color: 'var(--color-accent)', fontWeight: 500 }}>{code}</span>
    },
    {
      title: '开始日期',
      dataIndex: 'start_date',
      key: 'start_date',
      width: 100
    },
    {
      title: '结束日期',
      dataIndex: 'end_date',
      key: 'end_date',
      width: 100
    },
    {
      title: '收益率',
      dataIndex: 'total_return',
      key: 'total_return',
      width: 100,
      render: (value: number) => {
        const isUp = value > 0
        return (
          <span className={`price-badge ${isUp ? 'up' : 'down'}`}>
            {isUp ? '+' : ''}{value?.toFixed(2)}%
          </span>
        )
      }
    },
    {
      title: '交易次数',
      dataIndex: 'total_trades',
      key: 'total_trades',
      width: 80
    },
    {
      title: '回测时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (text: string) => new Date(text).toLocaleString()
    },
    {
      title: '操作',
      key: 'action',
      width: 80,
      render: (_: any, record: BacktestListItem) => (
        <Button
          type="text"
          icon={<EyeOutlined />}
          onClick={() => handleViewDetail(record.id)}
          style={{ color: 'var(--color-accent)' }}
        >
          查看
        </Button>
      )
    }
  ]

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

  // Stat display component
  const StatBox = ({ label, value, suffix = '', color }: {
    label: string
    value: number | string
    suffix?: string
    color?: string
  }) => (
    <div className="stat-card" style={{ padding: 'var(--space-md)' }}>
      <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-secondary)', marginBottom: 4 }}>
        {label}
      </div>
      <div className="stat-value" style={{ fontSize: 'var(--font-size-lg)', color: color || 'var(--color-text-primary)' }}>
        {typeof value === 'number' ? value.toLocaleString() : value}{suffix}
      </div>
    </div>
  )

  return (
    <div className="fade-in">
      {/* 页面标题 */}
      <div className="page-header">
        <h1 className="page-title">回测历史</h1>
        <p className="page-subtitle">查看历史回测记录</p>
      </div>

      {/* 历史记录列表 */}
      <div style={{ background: 'var(--color-canvas-lifted)', borderRadius: 'var(--radius-card)' }}>
        <Table
          columns={columns}
          dataSource={results}
          rowKey="id"
          loading={loading}
          pagination={{
            current: page,
            pageSize: pageSize,
            onChange: (p, ps) => {
              setPage(p)
              setPageSize(ps)
            },
            showSizeChanger: true,
            showTotal: (t) => `共 ${t} 条`
          }}
        />
      </div>

      {/* 详情 Modal */}
      <Modal
        title={
          <span style={{ fontWeight: 600 }}>
            回测详情 {stockInfo && <span style={{ color: 'var(--color-text-secondary)', fontWeight: 400 }}>- {stockInfo.name}</span>}
          </span>
        }
        open={detailVisible}
        onCancel={() => setDetailVisible(false)}
        footer={null}
        width={900}
        centered
      >
        {detailLoading && (
          <div className="loading-container" style={{ minHeight: 200 }}>
            <Spin size="large" />
          </div>
        )}

        {currentResult && !detailLoading && (
          <>
            {/* 统计指标 */}
            <div className="grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)', marginBottom: 'var(--space-md)' }}>
              <StatBox
                label="总收益率"
                value={currentResult.total_return.toFixed(2)}
                suffix="%"
                color={currentResult.total_return > 0 ? 'var(--color-success)' : 'var(--color-danger)'}
              />
              <StatBox
                label="年化收益率"
                value={currentResult.annual_return.toFixed(2)}
                suffix="%"
                color={currentResult.annual_return > 0 ? 'var(--color-success)' : 'var(--color-danger)'}
              />
              <StatBox
                label="夏普比率"
                value={(currentResult.sharpe_ratio || 0).toFixed(2)}
              />
              <StatBox
                label="最大回撤"
                value={(currentResult.max_drawdown || 0).toFixed(2)}
                suffix="%"
                color="var(--color-danger)"
              />
            </div>

            {/* 资金曲线 */}
            <div style={{ marginBottom: 'var(--space-md)', padding: 'var(--space-md)', background: 'var(--color-canvas-lifted)', borderRadius: 'var(--radius-card)' }}>
              <div style={{ fontSize: 'var(--font-size-sm)', fontWeight: 600, marginBottom: 'var(--space-sm)', color: 'var(--color-text-secondary)' }}>
                资金曲线
              </div>
              <ReactECharts option={getChartOption()} style={{ height: 280 }} />
            </div>

            {/* 交易记录 */}
            <div style={{ background: 'var(--color-canvas-lifted)', borderRadius: 'var(--radius-card)' }}>
              <div style={{ fontSize: 'var(--font-size-md)', fontWeight: 600, marginBottom: 'var(--space-md)' }}>
                交易记录
              </div>
              <Table
                columns={tradeColumns}
                dataSource={currentResult.trades}
                rowKey="id"
                pagination={{ pageSize: 10 }}
                size="small"
              />
            </div>
          </>
        )}
      </Modal>
    </div>
  )
}

export default BacktestHistory
