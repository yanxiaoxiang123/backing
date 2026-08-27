import { useMemo, useState } from 'react'
import { Alert, Button, Input, Modal, Select, Spin, Table } from 'antd'
import { useQuery } from '@tanstack/react-query'
import { EyeOutlined } from '@ant-design/icons'
import { LazyECharts } from '../components/charts/LazyECharts'
import { getBacktestResults, getBacktestResult, getStock } from '../services/api'
import type { BacktestListItem } from '../types'
import { backtestKeys, stockKeys } from '../services/queryKeys'
import { MetricCard, PageHeader } from '../components/research/ResearchPrimitives'

function BacktestHistory() {
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [detailVisible, setDetailVisible] = useState(false)
  const [selectedResultId, setSelectedResultId] = useState<number | null>(null)
  const [stockFilter, setStockFilter] = useState('')
  const [strategyFilter, setStrategyFilter] = useState('')
  const [sortOrder, setSortOrder] = useState<'newest' | 'return'>('newest')

  const resultsQuery = useQuery({
    queryKey: backtestKeys.list({ cursor: (page - 1) * pageSize, limit: pageSize }),
    queryFn: () => getBacktestResults(undefined, (page - 1) * pageSize, pageSize),
    placeholderData: (previous) => previous,
    staleTime: 30_000,
  })
  const detailQuery = useQuery({
    queryKey: backtestKeys.detail(selectedResultId ?? 0),
    queryFn: () => getBacktestResult(selectedResultId as number),
    enabled: detailVisible && selectedResultId !== null,
    staleTime: 5 * 60_000,
  })
  const stockQuery = useQuery({
    queryKey: stockKeys.detail(detailQuery.data?.stock_code ?? ''),
    queryFn: () => getStock(detailQuery.data?.stock_code as string),
    enabled: detailVisible && Boolean(detailQuery.data?.stock_code),
    staleTime: 5 * 60_000,
  })
  const results = useMemo(() => resultsQuery.data ?? [], [resultsQuery.data])
  const currentResult = detailQuery.data ?? null
  const stockInfo = stockQuery.data ?? null
  const visibleResults = useMemo(() => {
    const stockQuery = stockFilter.trim().toLowerCase()
    const strategyQuery = strategyFilter.trim().toLowerCase()
    return [...results]
      .filter((item) => {
        const matchesStock =
          !stockQuery || item.stock_code.toLowerCase().includes(stockQuery)
        const matchesStrategy =
          !strategyQuery ||
          (item.strategy_name ?? '').toLowerCase().includes(strategyQuery)
        return matchesStock && matchesStrategy
      })
      .sort((left, right) =>
        sortOrder === 'return'
          ? right.total_return - left.total_return
          : right.created_at.localeCompare(left.created_at),
      )
  }, [results, sortOrder, stockFilter, strategyFilter])
  const summary = useMemo(() => {
    const totalReturn = visibleResults.reduce((sum, item) => sum + item.total_return, 0)
    const positive = visibleResults.filter((item) => item.total_return > 0).length
    return {
      runs: visibleResults.length,
      averageReturn: visibleResults.length ? totalReturn / visibleResults.length : 0,
      positive,
    }
  }, [visibleResults])

  const handleViewDetail = (id: number) => {
    setDetailVisible(true)
    setSelectedResultId(id)
  }

  const getChartOption = () => {
    if (!currentResult) return {}

    if (currentResult.portfolio_values?.length) {
      const values = currentResult.portfolio_values
      return {
        tooltip: { trigger: 'axis' },
        grid: { left: '10%', right: '5%', bottom: '10%', top: '15%' },
        xAxis: { type: 'category', data: values.map((item) => item.date) },
        yAxis: { type: 'value', name: '资金(元)' },
        series: [
          {
            name: '组合价值',
            data: values.map((item) => item.total_value),
            type: 'line',
            smooth: true,
          },
        ],
      }
    }

    if (!currentResult.trades.length) return {}

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
        textStyle: { color: 'var(--color-text-primary)' },
      },
      grid: { left: '10%', right: '5%', bottom: '10%', top: '15%' },
      xAxis: {
        type: 'category',
        data: dates,
        axisLine: { lineStyle: { color: 'var(--color-border)' } },
        axisLabel: { color: 'var(--color-text-tertiary)', fontSize: 10 },
      },
      yAxis: {
        type: 'value',
        name: '资金(元)',
        axisLine: { show: false },
        axisLabel: { color: 'var(--color-text-tertiary)', fontSize: 10 },
        splitLine: {
          lineStyle: { color: 'var(--color-border-light)', type: 'dashed' },
        },
      },
      series: [
        {
          data: capital,
          type: 'line',
          smooth: true,
          lineStyle: { color: '#0071e3', width: 2 },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(0, 113, 227, 0.15)' },
                { offset: 1, color: 'rgba(0, 113, 227, 0)' },
              ],
            },
          },
        },
      ],
    }
  }

  const columns = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 60,
    },
    {
      title: '策略',
      dataIndex: 'strategy_name',
      key: 'strategy_name',
      width: 120,
      render: (name?: string) => name || '历史策略',
    },
    {
      title: '股票代码',
      dataIndex: 'stock_code',
      key: 'stock_code',
      width: 100,
      render: (code: string) => (
        <span style={{ color: 'var(--color-accent)', fontWeight: 500 }}>{code}</span>
      ),
    },
    {
      title: '开始日期',
      dataIndex: 'start_date',
      key: 'start_date',
      width: 100,
    },
    {
      title: '结束日期',
      dataIndex: 'end_date',
      key: 'end_date',
      width: 100,
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
            {isUp ? '+' : ''}
            {value?.toFixed(2)}%
          </span>
        )
      },
    },
    {
      title: '交易次数',
      dataIndex: 'total_trades',
      key: 'total_trades',
      width: 80,
    },
    {
      title: '回测时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (text: string) => new Date(text).toLocaleString(),
    },
    {
      title: '操作',
      key: 'action',
      width: 80,
      render: (_: unknown, record: BacktestListItem) => (
        <Button
          type="text"
          icon={<EyeOutlined />}
          onClick={() => handleViewDetail(record.id)}
          style={{ color: 'var(--color-accent)' }}
        >
          查看
        </Button>
      ),
    },
  ]

  const tradeColumns = [
    {
      title: '日期',
      dataIndex: 'trade_date',
      key: 'trade_date',
      width: 120,
      render: (_: string, record: { trade_date?: string; date?: string }) =>
        record.trade_date || record.date || '-',
    },
    {
      title: '操作',
      dataIndex: 'action',
      key: 'action',
      width: 80,
      render: (action: string) => (
        <span
          style={{
            color: action === 'buy' ? 'var(--color-danger)' : 'var(--color-success)',
            fontWeight: 500,
          }}
        >
          {action === 'buy' ? '买入' : '卖出'}
        </span>
      ),
    },
    { title: '价格', dataIndex: 'price', key: 'price', width: 100 },
    { title: '数量', dataIndex: 'quantity', key: 'quantity', width: 100 },
    { title: '金额', dataIndex: 'amount', key: 'amount', width: 120 },
  ]

  // Stat display component
  const StatBox = ({
    label,
    value,
    suffix = '',
    color,
  }: {
    label: string
    value: number | string
    suffix?: string
    color?: string
  }) => (
    <div className="stat-card" style={{ padding: 'var(--space-md)' }}>
      <div
        style={{
          fontSize: 'var(--font-size-xs)',
          color: 'var(--color-text-secondary)',
          marginBottom: 4,
        }}
      >
        {label}
      </div>
      <div
        className="stat-value"
        style={{
          fontSize: 'var(--font-size-lg)',
          color: color || 'var(--color-text-primary)',
        }}
      >
        {typeof value === 'number' ? value.toLocaleString() : value}
        {suffix}
      </div>
    </div>
  )

  return (
    <div className="fade-in">
      <PageHeader
        eyebrow="BACKTEST HISTORY"
        title="回测历史"
        subtitle="查看历史运行、绩效指标和交易记录"
      />

      <div className="backtest-history-summary" aria-label="回测摘要">
        <MetricCard label="当前页运行" value={summary.runs} detail="按当前筛选条件" />
        <MetricCard
          label="平均收益率"
          value={`${summary.averageReturn >= 0 ? '+' : ''}${summary.averageReturn.toFixed(2)}%`}
          tone={
            summary.averageReturn > 0
              ? 'up'
              : summary.averageReturn < 0
                ? 'down'
                : 'neutral'
          }
        />
        <MetricCard
          label="盈利运行"
          value={summary.positive}
          detail={
            summary.runs
              ? `占 ${Math.round((summary.positive / summary.runs) * 100)}%`
              : '暂无记录'
          }
          tone={summary.positive > 0 ? 'up' : 'neutral'}
        />
      </div>

      {/* 历史记录列表 */}
      <div className="research-panel backtest-history-panel">
        <div className="backtest-history-toolbar" aria-label="回测历史筛选">
          <Input
            allowClear
            placeholder="筛选股票代码"
            aria-label="筛选股票代码"
            value={stockFilter}
            onChange={(event) => setStockFilter(event.target.value)}
          />
          <Input
            allowClear
            placeholder="筛选策略"
            aria-label="筛选策略"
            value={strategyFilter}
            onChange={(event) => setStrategyFilter(event.target.value)}
          />
          <Select
            aria-label="回测排序"
            value={sortOrder}
            onChange={setSortOrder}
            options={[
              { value: 'newest', label: '最新运行' },
              { value: 'return', label: '收益率优先' },
            ]}
          />
        </div>
        {resultsQuery.isError && (
          <Alert
            type="error"
            showIcon
            message="加载历史记录失败"
            action={<Button onClick={() => void resultsQuery.refetch()}>重试</Button>}
          />
        )}
        <Table
          columns={columns}
          dataSource={visibleResults}
          rowKey="id"
          loading={resultsQuery.isLoading || resultsQuery.isFetching}
          pagination={{
            current: page,
            pageSize: pageSize,
            onChange: (p, ps) => {
              setPage(p)
              setPageSize(ps)
            },
            showSizeChanger: true,
            showTotal: (t) => `共 ${t} 条`,
          }}
        />
      </div>

      {/* 详情 Modal */}
      <Modal
        title={
          <span style={{ fontWeight: 600 }}>
            回测详情{' '}
            {stockInfo && (
              <span style={{ color: 'var(--color-text-secondary)', fontWeight: 400 }}>
                - {stockInfo.name}
              </span>
            )}
          </span>
        }
        open={detailVisible}
        onCancel={() => setDetailVisible(false)}
        footer={null}
        width={900}
        centered
      >
        {(detailQuery.isLoading || stockQuery.isLoading) && (
          <div className="loading-container" style={{ minHeight: 200 }}>
            <Spin size="large" />
          </div>
        )}

        {detailQuery.isError && (
          <Alert
            type="error"
            showIcon
            message="加载详情失败"
            action={<Button onClick={() => void detailQuery.refetch()}>重试</Button>}
          />
        )}

        {currentResult && !detailQuery.isLoading && !stockQuery.isLoading && (
          <>
            {/* 统计指标 */}
            <div
              className="grid"
              style={{
                gridTemplateColumns: 'repeat(4, 1fr)',
                marginBottom: 'var(--space-md)',
              }}
            >
              <StatBox
                label="总收益率"
                value={currentResult.total_return.toFixed(2)}
                suffix="%"
                color={
                  currentResult.total_return > 0
                    ? 'var(--color-success)'
                    : 'var(--color-danger)'
                }
              />
              <StatBox
                label="年化收益率"
                value={currentResult.annual_return.toFixed(2)}
                suffix="%"
                color={
                  currentResult.annual_return > 0
                    ? 'var(--color-success)'
                    : 'var(--color-danger)'
                }
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

            <div
              style={{
                marginBottom: 'var(--space-md)',
                color: 'var(--color-text-secondary)',
              }}
            >
              参数快照：
              {currentResult.parameters
                ? JSON.stringify(currentResult.parameters)
                : '未保存（旧记录）'}
            </div>

            {/* 资金曲线 */}
            <div
              style={{
                marginBottom: 'var(--space-md)',
                padding: 'var(--space-md)',
                background: 'var(--color-canvas-lifted)',
                borderRadius: 'var(--radius-card)',
              }}
            >
              <div
                style={{
                  fontSize: 'var(--font-size-sm)',
                  fontWeight: 600,
                  marginBottom: 'var(--space-sm)',
                  color: 'var(--color-text-secondary)',
                }}
              >
                资金曲线
              </div>
              <LazyECharts option={getChartOption()} style={{ height: 280 }} />
            </div>

            {/* 交易记录 */}
            <div
              style={{
                background: 'var(--color-canvas-lifted)',
                borderRadius: 'var(--radius-card)',
              }}
            >
              <div
                style={{
                  fontSize: 'var(--font-size-md)',
                  fontWeight: 600,
                  marginBottom: 'var(--space-md)',
                }}
              >
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
