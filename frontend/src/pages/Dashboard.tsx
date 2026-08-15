import { useEffect, useState, useCallback, useMemo } from 'react'
import { Alert, Button, Spin, Select } from 'antd'
import { LineChartOutlined, ReloadOutlined, TableOutlined } from '@ant-design/icons'
import ReactECharts from 'echarts-for-react'
import { useNavigate } from 'react-router-dom'
import {
  getRealtimeQuotes,
  getRealtimeIndices,
  getWatchlist,
  getRealtimeBars,
} from '../services/api'
import { getApiErrorMessage } from '../services/api'
import type { DashboardIndex, DashboardStock } from '../types'
import { logger } from '../utils/logger'

interface TrendData {
  name: string
  dates: string[]
  values: number[]
}

type BlockState<T> =
  | { status: 'idle' | 'loading' }
  | { status: 'ok'; data: T }
  | { status: 'error'; error: string; retryable: boolean }

function initialBlockState(): BlockState<never> {
  return { status: 'idle' }
}

interface WatchlistEntry {
  code: string
  name: string
}

function Dashboard() {
  const navigate = useNavigate()
  const [watchlistEntries, setWatchlistEntries] = useState<
    Array<{ code: string; name: string }>
  >([])
  const [watchlistError, setWatchlistError] = useState<string | null>(null)

  const [indicesState, setIndicesState] =
    useState<BlockState<DashboardIndex[]>>(initialBlockState)
  const [quotesState, setQuotesState] =
    useState<BlockState<DashboardStock[]>>(initialBlockState)
  const [trendState, setTrendState] = useState<BlockState<TrendData>>(initialBlockState)

  const [selectedTrendStock, setSelectedTrendStock] = useState<string>('')
  const [reloadCounter, setReloadCounter] = useState(0)

  const reloadIndices = useCallback(async () => {
    setIndicesState({ status: 'loading' })
    try {
      const res = await getRealtimeIndices()
      const data: DashboardIndex[] = res.data.map((idx: any) => ({
        code: idx.symbol,
        name: idx.name,
        value: idx.close,
        change: idx.change,
        change_percent: idx.change_percent,
      }))
      setIndicesState({ status: 'ok', data })
    } catch (error) {
      const message = getApiErrorMessage(error)
      logger.error('Failed to load indices:', error)
      const apiError = error as {
        response?: {
          data?: { error?: { retryable?: boolean } }
        }
      }
      const retryable = apiError?.response?.data?.error?.retryable ?? true
      setIndicesState({ status: 'error', error: message, retryable })
    }
  }, [])

  const reloadQuotes = useCallback(async () => {
    setQuotesState({ status: 'loading' })
    try {
      const codes = watchlistEntries.map((entry) => entry.code)
      if (codes.length === 0) {
        setQuotesState({ status: 'ok', data: [] })
        return
      }
      const res = await getRealtimeQuotes(codes)
      const nameMap: Record<string, string> = {}
      watchlistEntries.forEach((entry) => {
        nameMap[entry.code] = entry.name
      })
      const data: DashboardStock[] = res.data.map((q: any) => ({
        id: 0,
        code: q.symbol,
        name: nameMap[q.symbol] || q.symbol,
        current_price: q.close,
        high: q.high,
        low: q.low,
        volume: q.volume,
        change: q.change,
        change_percent: q.change_percent,
      }))
      setQuotesState({ status: 'ok', data })
    } catch (error) {
      const message = getApiErrorMessage(error)
      logger.error('Failed to load watchlist quotes:', error)
      const apiError = error as {
        response?: {
          data?: { error?: { retryable?: boolean } }
        }
      }
      const retryable = apiError?.response?.data?.error?.retryable ?? true
      setQuotesState({ status: 'error', error: message, retryable })
    }
  }, [watchlistEntries])

  const reloadWatchlist = useCallback(async () => {
    setWatchlistError(null)
    try {
      const watchlistRes = await getWatchlist()
      const entries: WatchlistEntry[] = watchlistRes.items.map((item: any) => ({
        code: item.stock_code,
        name: item.stock_name || item.stock_code,
      }))
      setWatchlistEntries(entries)
    } catch (error) {
      const message = getApiErrorMessage(error)
      logger.error('Failed to load watchlist:', error)
      setWatchlistError(message)
    }
  }, [])

  // Initial fan-out: three independent loads, no shared failure surface.
  useEffect(() => {
    reloadWatchlist()
    reloadIndices()
  }, [reloadWatchlist, reloadIndices])

  useEffect(() => {
    if (watchlistEntries.length > 0) {
      reloadQuotes()
    }
  }, [watchlistEntries, reloadQuotes])

  const loadTrendData = useCallback(
    async (stockCode: string) => {
      setTrendState({ status: 'loading' })
      try {
        const klines = await getRealtimeBars(stockCode, 'daily')
        if (klines.data.length > 0) {
          const stockName =
            watchlistEntries.find((entry) => entry.code === stockCode)?.name ||
            stockCode
          const trend: TrendData = {
            name: stockName !== stockCode ? `${stockName} (${stockCode})` : stockCode,
            dates: klines.data.map((k: any) => k.date),
            values: klines.data.map((k: any) => k.close),
          }
          setTrendState({ status: 'ok', data: trend })
          return
        }
        setTrendState({
          status: 'error',
          error: '暂无走势数据',
          retryable: true,
        })
      } catch (error) {
        const message = getApiErrorMessage(error)
        logger.error('Failed to load trend data:', error)
        const apiError = error as {
          response?: {
            data?: { error?: { retryable?: boolean } }
          }
        }
        const retryable = apiError?.response?.data?.error?.retryable ?? true
        setTrendState({ status: 'error', error: message, retryable })
      }
    },
    [watchlistEntries],
  )

  // Auto-pick the first watchlist entry once it loads.
  useEffect(() => {
    if (selectedTrendStock === '' && watchlistEntries.length > 0) {
      setSelectedTrendStock(watchlistEntries[0].code)
    }
  }, [watchlistEntries, selectedTrendStock])

  // Load the trend whenever the selected symbol changes (and we have one).
  useEffect(() => {
    if (selectedTrendStock && watchlistEntries.length > 0) {
      loadTrendData(selectedTrendStock)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedTrendStock, reloadCounter])

  const handleTrendStockChange = useCallback(
    (stockCode: string) => {
      setSelectedTrendStock(stockCode)
      if (stockCode) {
        loadTrendData(stockCode)
      } else {
        setTrendState(initialBlockState())
      }
    },
    [loadTrendData],
  )

  const handleRetryAll = useCallback(() => {
    setReloadCounter((c) => c + 1)
    reloadIndices()
    if (watchlistEntries.length > 0) {
      reloadQuotes()
    }
    if (selectedTrendStock) {
      loadTrendData(selectedTrendStock)
    }
  }, [reloadIndices, reloadQuotes, loadTrendData, selectedTrendStock, watchlistEntries])

  const anyLoading =
    indicesState.status === 'loading' || quotesState.status === 'loading'

  const IndexCard = ({ name, value, change, change_percent }: DashboardIndex) => {
    const isUp = change >= 0
    if (value === 0 && change === 0) {
      return (
        <div
          style={{
            background: 'var(--color-canvas-lifted)',
            borderRadius: 'var(--radius-card)',
            padding: 'var(--space-lg)',
          }}
        >
          <div
            style={{
              color: 'var(--color-text-secondary)',
              fontSize: 'var(--font-size-sm)',
              marginBottom: 4,
            }}
          >
            {name}
          </div>
          <div
            style={{
              color: 'var(--color-text-tertiary)',
              fontSize: 'var(--font-size-sm)',
            }}
          >
            暂无数据
          </div>
        </div>
      )
    }
    return (
      <div
        style={{
          background: 'var(--color-canvas-lifted)',
          borderRadius: 'var(--radius-card)',
          padding: 'var(--space-lg)',
        }}
      >
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
          }}
        >
          <div>
            <div
              style={{
                color: 'var(--color-text-secondary)',
                fontSize: 'var(--font-size-sm)',
                marginBottom: 4,
              }}
            >
              {name}
            </div>
            <div
              style={{
                color: 'var(--color-text-primary)',
                fontSize: 'var(--font-size-2xl)',
                fontWeight: 700,
                letterSpacing: '-0.03em',
              }}
            >
              {value.toLocaleString()}
            </div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div
              className={isUp ? 'price-up' : 'price-down'}
              style={{ fontSize: 'var(--font-size-sm)', fontWeight: 500 }}
            >
              {isUp ? '+' : ''}
              {Math.abs(change).toFixed(2)}
            </div>
            <div
              className={isUp ? 'price-up' : 'price-down'}
              style={{ fontSize: 'var(--font-size-xs)' }}
            >
              {isUp ? '+' : ''}
              {change_percent.toFixed(2)}%
            </div>
          </div>
        </div>
      </div>
    )
  }

  const BlockError = ({
    message,
    onRetry,
  }: {
    message: string
    onRetry: () => void
  }) => (
    <Alert
      type="error"
      showIcon
      message={message}
      description="行情服务暂时不可达，可点击重试。"
      action={
        <Button size="small" icon={<ReloadOutlined />} onClick={onRetry}>
          重试
        </Button>
      }
      style={{ marginBottom: 'var(--space-md)' }}
    />
  )

  const getTrendChartOption = useMemo(() => {
    const currentTrend = trendState.status === 'ok' ? trendState.data : null
    if (!currentTrend || currentTrend.values.length === 0) return {}
    return {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        backgroundColor: '#fff',
        borderColor: 'var(--color-border)',
        textStyle: { color: 'var(--color-text-primary)' },
      },
      grid: { left: '8%', right: '5%', bottom: '10%', top: '15%', containLabel: true },
      xAxis: {
        type: 'category',
        data: currentTrend.dates.map((date) => date.slice(5)),
        axisLine: { lineStyle: { color: 'var(--color-border)' } },
        axisLabel: { color: 'var(--color-text-tertiary)', fontSize: 10 },
      },
      yAxis: {
        type: 'value',
        axisLine: { show: false },
        axisLabel: { color: 'var(--color-text-tertiary)', fontSize: 10 },
        splitLine: {
          lineStyle: { color: 'var(--color-border-light)', type: 'dashed' },
        },
      },
      series: [
        {
          name: currentTrend.name,
          type: 'line',
          data: currentTrend.values,
          smooth: true,
          symbol: 'none',
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
  }, [trendState])

  const indicesData = indicesState.status === 'ok' ? indicesState.data : []
  const watchlistData = quotesState.status === 'ok' ? quotesState.data : []
  const up = watchlistData.filter((s) => s.change_percent > 0).length
  const down = watchlistData.filter((s) => s.change_percent < 0).length
  const flat = Math.max(watchlistData.length - up - down, 0)

  const WatchlistTable = ({ stocks }: { stocks: DashboardStock[] }) => (
    <div
      style={{
        background: 'var(--color-canvas-lifted)',
        borderRadius: 'var(--radius-card)',
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          padding: 'var(--space-lg)',
          borderBottom: '1px solid var(--color-border)',
        }}
      >
        <span
          style={{
            fontSize: 'var(--font-size-md)',
            fontWeight: 600,
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--space-sm)',
          }}
        >
          <TableOutlined />
          自选股走势
        </span>
      </div>
      {!stocks || stocks.length === 0 ? (
        <div
          style={{
            padding: 'var(--space-xl)',
            textAlign: 'center',
            color: 'var(--color-text-tertiary)',
          }}
        >
          暂无自选股数据，请先在设置中添加自选股
        </div>
      ) : (
        <table className="mc-table">
          <thead>
            <tr>
              <th>代码</th>
              <th>名称</th>
              <th style={{ textAlign: 'right' }}>最新价</th>
              <th style={{ textAlign: 'right' }}>涨跌</th>
              <th style={{ textAlign: 'right' }}>涨跌幅</th>
              <th style={{ textAlign: 'right' }}>最高</th>
              <th style={{ textAlign: 'right' }}>最低</th>
              <th style={{ textAlign: 'right' }}>成交量</th>
            </tr>
          </thead>
          <tbody>
            {stocks.map((stock) => {
              const isUp = stock.change_percent >= 0
              return (
                <tr
                  key={stock.id || stock.code}
                  onClick={() => navigate(`/stocks/${stock.code}`)}
                  style={{ cursor: 'pointer' }}
                >
                  <td style={{ color: 'var(--color-ink)', fontWeight: 500 }}>
                    {stock.code}
                  </td>
                  <td>{stock.name}</td>
                  <td style={{ textAlign: 'right', fontWeight: 500 }}>
                    {stock.current_price.toFixed(2)}
                  </td>
                  <td
                    style={{ textAlign: 'right' }}
                    className={isUp ? 'price-up' : 'price-down'}
                  >
                    {isUp ? '+' : ''}
                    {stock.change.toFixed(2)}
                  </td>
                  <td style={{ textAlign: 'right' }}>
                    <span
                      className={`mc-badge ${isUp ? 'mc-badge-up' : 'mc-badge-down'}`}
                    >
                      {isUp ? '+' : ''}
                      {stock.change_percent.toFixed(2)}%
                    </span>
                  </td>
                  <td style={{ textAlign: 'right' }}>{stock.high.toFixed(2)}</td>
                  <td style={{ textAlign: 'right' }}>{stock.low.toFixed(2)}</td>
                  <td style={{ textAlign: 'right' }}>
                    {(stock.volume / 10000).toFixed(0)}万
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}
    </div>
  )

  if (anyLoading && indicesState.status === 'idle' && quotesState.status === 'idle') {
    return (
      <div className="loading-container" style={{ minHeight: '60vh' }}>
        <Spin size="large" />
      </div>
    )
  }

  const trendName = trendState.status === 'ok' ? trendState.data.name : '行情走势'

  return (
    <div className="fade-in">
      <div className="page-header">
        <div>
          <h1 className="page-title">欢迎回来</h1>
          <p className="page-subtitle">
            {new Date().toLocaleDateString('zh-CN', {
              weekday: 'long',
              month: 'long',
              day: 'numeric',
            })}
          </p>
        </div>
        <Button icon={<ReloadOutlined />} onClick={handleRetryAll} size="small">
          刷新
        </Button>
      </div>

      {watchlistError && (
        <BlockError
          message={watchlistError}
          onRetry={() => {
            reloadWatchlist()
            setReloadCounter((c) => c + 1)
          }}
        />
      )}

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(3, 1fr)',
          gap: 'var(--space-lg)',
          marginBottom: 'var(--space-lg)',
        }}
      >
        {indicesState.status === 'loading' && indicesData.length === 0 ? (
          <div
            style={{
              gridColumn: '1 / -1',
              display: 'flex',
              justifyContent: 'center',
              padding: 'var(--space-lg)',
            }}
          >
            <Spin />
          </div>
        ) : indicesState.status === 'error' ? (
          <div style={{ gridColumn: '1 / -1' }}>
            <BlockError message={indicesState.error} onRetry={reloadIndices} />
          </div>
        ) : (
          indicesData
            .filter((index) => !(index.value === 0 && index.change === 0))
            .map((index) => <IndexCard key={index.code} {...index} />)
        )}
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '2fr 1fr',
          gap: 'var(--space-lg)',
          marginBottom: 'var(--space-lg)',
        }}
      >
        <div
          style={{
            background: 'var(--color-canvas-lifted)',
            borderRadius: 'var(--radius-card)',
            padding: 'var(--space-lg)',
          }}
        >
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: 'var(--space-sm)',
            }}
          >
            <div
              style={{
                fontSize: 'var(--font-size-sm)',
                fontWeight: 600,
                color: 'var(--color-text-secondary)',
                display: 'flex',
                alignItems: 'center',
                gap: 'var(--space-sm)',
              }}
            >
              <LineChartOutlined />
              {trendName}
            </div>
            <Select
              placeholder="选择股票"
              allowClear
              value={selectedTrendStock || undefined}
              onChange={handleTrendStockChange}
              style={{ width: 160 }}
              loading={trendState.status === 'loading'}
              options={watchlistEntries.map((w) => ({
                value: w.code,
                label: w.name !== w.code ? `${w.name} (${w.code})` : w.code,
              }))}
            />
          </div>
          {trendState.status === 'error' ? (
            <BlockError
              message={trendState.error}
              onRetry={() => selectedTrendStock && loadTrendData(selectedTrendStock)}
            />
          ) : (
            <ReactECharts
              option={getTrendChartOption}
              style={{ height: 280 }}
              notMerge
              lazyUpdate
            />
          )}
        </div>
        <div
          style={{
            background: 'var(--color-canvas-lifted)',
            borderRadius: 'var(--radius-card)',
            padding: 'var(--space-lg)',
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
            自选股统计
          </div>
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: 'var(--space-md)',
              padding: 'var(--space-md) 0',
            }}
          >
            <div
              style={{
                background: 'var(--color-canvas-lifted)',
                borderRadius: 'var(--radius-btn)',
                padding: 'var(--space-lg)',
                textAlign: 'center',
              }}
            >
              <div className="stat-value" style={{ color: 'var(--color-danger)' }}>
                {up}
              </div>
              <div className="stat-label">上涨</div>
            </div>
            <div
              style={{
                background: 'var(--color-canvas-lifted)',
                borderRadius: 'var(--radius-btn)',
                padding: 'var(--space-lg)',
                textAlign: 'center',
              }}
            >
              <div
                className="stat-value"
                style={{ color: 'var(--color-text-secondary)' }}
              >
                {flat}
              </div>
              <div className="stat-label">平盘</div>
            </div>
            <div
              style={{
                background: 'var(--color-canvas-lifted)',
                borderRadius: 'var(--radius-btn)',
                padding: 'var(--space-lg)',
                textAlign: 'center',
              }}
            >
              <div className="stat-value" style={{ color: 'var(--color-success)' }}>
                {down}
              </div>
              <div className="stat-label">下跌</div>
            </div>
          </div>
        </div>
      </div>

      {quotesState.status === 'error' ? (
        <BlockError message={quotesState.error} onRetry={reloadQuotes} />
      ) : (
        <WatchlistTable stocks={watchlistData} />
      )}

      <div
        style={{
          textAlign: 'center',
          marginTop: 'var(--space-xl)',
          padding: 'var(--space-lg) 0',
          color: 'var(--color-text-tertiary)',
          fontSize: 'var(--font-size-xs)',
        }}
      >
        量化交易系统 v1.0 ·{' '}
        <a
          onClick={() => navigate('/watchlist')}
          style={{ cursor: 'pointer', color: 'var(--color-ink)' }}
        >
          管理自选股
        </a>
      </div>
    </div>
  )
}

export default Dashboard
