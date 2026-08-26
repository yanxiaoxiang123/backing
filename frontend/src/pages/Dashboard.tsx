import { useMemo, useState } from 'react'
import { Alert, Button, Empty, Select, Skeleton, Tag } from 'antd'
import {
  ArrowUpOutlined,
  LineChartOutlined,
  ReloadOutlined,
  SearchOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons'
import ReactECharts from 'echarts-for-react'
import { useNavigate } from 'react-router-dom'
import {
  useDashboardIndices,
  useDashboardQuotes,
  useDashboardTrend,
  useDashboardWatchlist,
  useRefreshDashboard,
} from '../hooks/useDashboardData'
import { getApiErrorMessage } from '../services/api'
import type { DashboardIndex, DashboardStock } from '../types'

function ErrorBlock({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
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
    />
  )
}

function MarketIndexCard({ index }: { index: DashboardIndex }) {
  const positive = index.change >= 0
  return (
    <article className="research-index-card">
      <div className="research-index-card__label">{index.name}</div>
      <div className="research-index-card__value">
        {index.value ? index.value.toLocaleString() : '—'}
      </div>
      <div className={positive ? 'price-up' : 'price-down'}>
        {positive ? '+' : ''}
        {index.change.toFixed(2)} ({positive ? '+' : ''}
        {index.change_percent.toFixed(2)}%)
      </div>
    </article>
  )
}

function StockTable({ stocks }: { stocks: DashboardStock[] }) {
  const navigate = useNavigate()
  if (!stocks.length) {
    return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="还没有自选股" />
  }
  return (
    <div className="research-table-wrap">
      <table className="mc-table research-table">
        <thead>
          <tr>
            <th>标的</th>
            <th className="numeric">最新价</th>
            <th className="numeric">涨跌幅</th>
            <th className="numeric hide-on-narrow">成交量</th>
          </tr>
        </thead>
        <tbody>
          {stocks.map((stock) => {
            const positive = stock.change_percent >= 0
            return (
              <tr key={stock.code} onClick={() => navigate(`/stocks/${stock.code}`)}>
                <td>
                  <div className="stock-cell">
                    <strong>{stock.name}</strong>
                    <span>{stock.code}</span>
                  </div>
                </td>
                <td className="numeric price-value">
                  {stock.current_price.toFixed(2)}
                </td>
                <td className={`numeric ${positive ? 'price-up' : 'price-down'}`}>
                  {positive ? '+' : ''}
                  {stock.change_percent.toFixed(2)}%
                </td>
                <td className="numeric hide-on-narrow">
                  {(stock.volume / 10000).toFixed(0)}万
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function Dashboard() {
  const navigate = useNavigate()
  const refreshDashboard = useRefreshDashboard()
  const [selectedCode, setSelectedCode] = useState('')
  const watchlistQuery = useDashboardWatchlist()
  const indicesQuery = useDashboardIndices()
  const watchlistItems = useMemo(
    () => watchlistQuery.data?.items ?? [],
    [watchlistQuery.data],
  )
  const watchlistCodes = useMemo(
    () => watchlistItems.map((item) => item.stock_code),
    [watchlistItems],
  )
  const quotesQuery = useDashboardQuotes(watchlistCodes)
  const activeCode = selectedCode || watchlistCodes[0]
  const trendQuery = useDashboardTrend(activeCode)

  const names = useMemo(
    () =>
      new Map(
        watchlistItems.map((item) => [
          item.stock_code,
          item.stock_name || item.stock_code,
        ]),
      ),
    [watchlistItems],
  )
  const stocks = useMemo<DashboardStock[]>(
    () =>
      (quotesQuery.data?.data ?? []).map((quote) => ({
        id: 0,
        code: quote.symbol,
        name: names.get(quote.symbol) || quote.symbol,
        current_price: quote.close,
        high: quote.high,
        low: quote.low,
        volume: quote.volume,
        change: quote.change,
        change_percent: quote.change_percent,
      })),
    [names, quotesQuery.data],
  )
  const trendOption = useMemo(() => {
    const bars = trendQuery.data?.data ?? []
    return {
      animation: false,
      grid: { left: 44, right: 16, top: 16, bottom: 28, containLabel: true },
      tooltip: { trigger: 'axis' },
      xAxis: {
        type: 'category',
        data: bars.map((bar) => bar.date.slice(5)),
        axisLabel: { color: '#77716b', fontSize: 10 },
        axisLine: { lineStyle: { color: 'rgba(20,20,19,.12)' } },
      },
      yAxis: {
        type: 'value',
        scale: true,
        axisLabel: { color: '#77716b', fontSize: 10 },
        splitLine: { lineStyle: { color: 'rgba(20,20,19,.08)', type: 'dashed' } },
      },
      series: [
        {
          type: 'line',
          data: bars.map((bar) => bar.close),
          smooth: true,
          symbol: 'none',
          lineStyle: { color: '#145bd7', width: 2 },
          areaStyle: { color: 'rgba(20,91,215,.10)' },
        },
      ],
    }
  }, [trendQuery.data])
  const up = stocks.filter((stock) => stock.change_percent > 0).length
  const down = stocks.filter((stock) => stock.change_percent < 0).length
  const flat = stocks.length - up - down

  const handleRefresh = () => {
    void refreshDashboard()
  }

  return (
    <div className="fade-in research-dashboard">
      <header className="page-header research-page-header">
        <div>
          <div className="eyebrow">MARKET BRIEFING</div>
          <h1 className="page-title">今天该研究什么</h1>
          <p className="page-subtitle">
            {new Date().toLocaleDateString('zh-CN', {
              weekday: 'long',
              month: 'long',
              day: 'numeric',
            })}{' '}
            · 从自选异动开始，快速进入下一步判断
          </p>
        </div>
        <div className="page-actions">
          <Button icon={<SearchOutlined />} onClick={() => navigate('/screener')}>
            找标的
          </Button>
          <Button
            icon={<ReloadOutlined />}
            onClick={handleRefresh}
            loading={indicesQuery.isFetching || quotesQuery.isFetching}
          >
            刷新行情
          </Button>
        </div>
      </header>

      <section className="research-section" aria-labelledby="market-overview-title">
        <div className="section-heading">
          <div>
            <div className="eyebrow">OVERVIEW</div>
            <h2 id="market-overview-title">市场概览</h2>
          </div>
          <span className="data-freshness">行情按需更新</span>
        </div>
        {indicesQuery.isError ? (
          <ErrorBlock
            message={getApiErrorMessage(indicesQuery.error)}
            onRetry={() => void indicesQuery.refetch()}
          />
        ) : indicesQuery.isLoading ? (
          <div className="research-index-grid">
            <Skeleton active />
            <Skeleton active />
            <Skeleton active />
          </div>
        ) : (
          <div className="research-index-grid">
            {(indicesQuery.data?.data ?? []).map((index) => (
              <MarketIndexCard
                key={index.symbol}
                index={{
                  code: index.symbol,
                  name: index.name,
                  value: index.close,
                  change: index.change,
                  change_percent: index.change_percent,
                }}
              />
            ))}
          </div>
        )}
      </section>

      <section
        className="research-section research-discovery-grid"
        aria-labelledby="discovery-title"
      >
        <div className="research-panel">
          <div className="section-heading">
            <div>
              <div className="eyebrow">WATCHLIST</div>
              <h2 id="discovery-title">自选股异动</h2>
            </div>
            <Tag icon={<ArrowUpOutlined />} color="red">
              {up} 上涨 · {down} 下跌 · {flat} 平盘
            </Tag>
          </div>
          {watchlistQuery.isError ? (
            <ErrorBlock
              message={getApiErrorMessage(watchlistQuery.error)}
              onRetry={() => void watchlistQuery.refetch()}
            />
          ) : watchlistQuery.isLoading ? (
            <Skeleton active />
          ) : quotesQuery.isError ? (
            <ErrorBlock
              message={getApiErrorMessage(quotesQuery.error)}
              onRetry={() => void quotesQuery.refetch()}
            />
          ) : quotesQuery.isLoading && !stocks.length ? (
            <Skeleton active />
          ) : (
            <StockTable stocks={stocks} />
          )}
          <Button type="link" onClick={() => navigate('/watchlist')}>
            管理自选股 →
          </Button>
        </div>

        <div className="research-panel research-panel--accent">
          <div className="section-heading">
            <div>
              <div className="eyebrow">RESEARCH QUEUE</div>
              <h2>下一步</h2>
            </div>
            <ThunderboltOutlined className="panel-icon" />
          </div>
          <div className="research-queue">
            {stocks.length ? (
              stocks.slice(0, 4).map((stock) => (
                <button
                  key={stock.code}
                  className="research-queue-item"
                  onClick={() => navigate(`/stocks/${stock.code}`)}
                >
                  <span>
                    <strong>{stock.name}</strong>
                    <small>
                      {stock.code} ·{' '}
                      {stock.change_percent >= 0 ? '自选股异动' : '关注回撤'}
                    </small>
                  </span>
                  <span
                    className={stock.change_percent >= 0 ? 'price-up' : 'price-down'}
                  >
                    {stock.change_percent >= 0 ? '+' : ''}
                    {stock.change_percent.toFixed(2)}%
                  </span>
                </button>
              ))
            ) : (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description="暂无待研究标的"
              />
            )}
          </div>
          <Button type="primary" block onClick={() => navigate('/screener')}>
            运行一次筛选
          </Button>
        </div>
      </section>

      <section
        className="research-section research-chart-grid"
        aria-labelledby="trend-title"
      >
        <div className="research-panel">
          <div className="section-heading">
            <div>
              <div className="eyebrow">PRICE ACTION</div>
              <h2 id="trend-title">
                <LineChartOutlined />{' '}
                {activeCode ? names.get(activeCode) || activeCode : '走势预览'}
              </h2>
            </div>
            <Select
              aria-label="选择走势股票"
              placeholder="选择股票"
              value={activeCode || undefined}
              onChange={setSelectedCode}
              allowClear
              options={watchlistItems.map((item) => ({
                value: item.stock_code,
                label: `${item.stock_name || item.stock_code} (${item.stock_code})`,
              }))}
              style={{ minWidth: 180 }}
            />
          </div>
          {trendQuery.isError ? (
            <ErrorBlock
              message={getApiErrorMessage(trendQuery.error)}
              onRetry={() => void trendQuery.refetch()}
            />
          ) : trendQuery.isLoading ? (
            <Skeleton active paragraph={{ rows: 6 }} />
          ) : trendQuery.data?.data.length ? (
            <ReactECharts
              option={trendOption}
              style={{ height: 300 }}
              notMerge
              lazyUpdate
            />
          ) : (
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无走势数据" />
          )}
        </div>

        <div className="research-panel research-panel--summary">
          <div className="eyebrow">QUICK STATS</div>
          <h2>研究节奏</h2>
          <div className="research-stat-list">
            <div>
              <span>自选股</span>
              <strong>{watchlistItems.length}</strong>
            </div>
            <div>
              <span>上涨</span>
              <strong className="price-up">{up}</strong>
            </div>
            <div>
              <span>下跌</span>
              <strong className="price-down">{down}</strong>
            </div>
            <div>
              <span>待研究</span>
              <strong>{Math.min(stocks.length, 4)}</strong>
            </div>
          </div>
          <Button onClick={() => navigate('/workspace')} block>
            打开 AI 工作台
          </Button>
        </div>
      </section>
    </div>
  )
}

export default Dashboard
