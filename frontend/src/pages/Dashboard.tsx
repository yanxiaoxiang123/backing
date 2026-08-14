import { useEffect, useState, useCallback, useMemo } from 'react'
import { Spin, Select } from 'antd'
import { LineChartOutlined, TableOutlined } from '@ant-design/icons'
import ReactECharts from 'echarts-for-react'
import { useNavigate } from 'react-router-dom'
import {
  getRealtimeQuotes,
  getRealtimeIndices,
  getWatchlist,
  getRealtimeBars,
} from '../services/api'
import type { DashboardIndex, DashboardSummary, DashboardStock } from '../types'
import { logger } from '../utils/logger'

interface TrendData {
  name: string
  dates: string[]
  values: number[]
}

function Dashboard() {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(true)
  const [summary, setSummary] = useState<DashboardSummary | null>(null)
  const [selectedTrendStock, setSelectedTrendStock] = useState<string>('')
  const [trendData, setTrendData] = useState<TrendData | null>(null)
  const [trendLoading, setTrendLoading] = useState(false)

  useEffect(() => {
    loadData()
  }, [])

  useEffect(() => {
    if (summary && summary.watchlist.length > 0 && !trendData) {
      const firstCode = summary.watchlist[0].code
      setSelectedTrendStock(firstCode)
      loadTrendData(firstCode)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [summary])

  const loadData = useCallback(async () => {
    try {
      setLoading(true)
      // 从 DB 获取自选股列表（代码+名称）
      const watchlistRes = await getWatchlist()
      const codes = watchlistRes.items.map((item: any) => item.stock_code)
      const nameMap: Record<string, string> = {}
      watchlistRes.items.forEach((item: any) => {
        nameMap[item.stock_code] = item.stock_name || item.stock_code
      })

      const [quotesRes, indicesRes] = await Promise.all([
        codes.length > 0
          ? getRealtimeQuotes(codes)
          : Promise.resolve({ success: true, data: [] }),
        getRealtimeIndices(),
      ])

      const watchlistData = quotesRes.data.map((q: any) => ({
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

      const indicesData = indicesRes.data.map((idx: any) => ({
        code: idx.symbol,
        name: idx.name,
        value: idx.close,
        change: idx.change,
        change_percent: idx.change_percent,
      }))

      const up = watchlistData.filter((s: any) => s.change_percent > 0).length
      const down = watchlistData.filter((s: any) => s.change_percent < 0).length
      const flat = watchlistData.length - up - down

      setSummary((prev) => ({
        watchlist: watchlistData,
        indices: indicesData,
        market_stats: { up, down, flat, total: watchlistData.length },
        trend: prev?.trend || {
          name: watchlistData[0]?.name || '',
          dates: [],
          values: [],
        },
      }))
    } catch (error) {
      logger.error('Failed to load dashboard data:', error)
    } finally {
      setLoading(false)
    }
  }, [summary?.watchlist?.length])

  const loadTrendData = useCallback(
    async (stockCode: string) => {
      try {
        setTrendLoading(true)
        const klines = await getRealtimeBars(stockCode, 'daily')

        if (klines.data.length > 0) {
          const stockName =
            summary?.watchlist.find((w: any) => w.code === stockCode)?.name || stockCode
          setTrendData({
            name: stockName !== stockCode ? `${stockName} (${stockCode})` : stockCode,
            dates: klines.data.map((k: any) => k.date),
            values: klines.data.map((k: any) => k.close),
          })
        }
      } catch (error) {
        logger.error('Failed to load trend data:', error)
      } finally {
        setTrendLoading(false)
      }
    },
    [summary],
  )

  const handleTrendStockChange = useCallback(
    (stockCode: string) => {
      setSelectedTrendStock(stockCode)
      if (stockCode) {
        loadTrendData(stockCode)
      } else {
        setTrendData(null)
      }
    },
    [loadTrendData],
  )

  const IndexCard = ({ name, value, change, change_percent }: DashboardIndex) => {
    const isUp = change >= 0
    // Skip rendering if no valid data
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
          cursor: 'pointer',
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

  const getTrendChartOption = useMemo(() => {
    // Use selected trend data if available, otherwise fall back to summary trend
    const currentTrend = trendData || (summary ? summary.trend : null)
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
        data: currentTrend.dates.map((date: string) => date.slice(5)),
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
  }, [trendData, summary])

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
                  key={stock.id}
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

  if (loading) {
    return (
      <div className="loading-container" style={{ minHeight: '60vh' }}>
        <Spin size="large" />
      </div>
    )
  }

  if (!summary) {
    return <div className="empty-state">仪表盘数据加载失败</div>
  }

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
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(3, 1fr)',
          gap: 'var(--space-lg)',
          marginBottom: 'var(--space-lg)',
        }}
      >
        {summary.indices
          .filter((index) => !(index.value === 0 && index.change === 0))
          .map((index) => (
            <IndexCard key={index.code} {...index} />
          ))}
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
              {(trendData || summary.trend).name}
            </div>
            <Select
              placeholder="选择股票"
              allowClear
              value={selectedTrendStock || undefined}
              onChange={handleTrendStockChange}
              style={{ width: 160 }}
              loading={trendLoading}
              options={summary.watchlist.map((w) => ({
                value: w.code,
                label: w.name !== w.code ? `${w.name} (${w.code})` : w.code,
              }))}
            />
          </div>
          <ReactECharts option={getTrendChartOption} style={{ height: 280 }} />
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
                {summary.market_stats.up}
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
                {summary.market_stats.flat}
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
                {summary.market_stats.down}
              </div>
              <div className="stat-label">下跌</div>
            </div>
          </div>
        </div>
      </div>

      <WatchlistTable stocks={summary.watchlist} />

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
