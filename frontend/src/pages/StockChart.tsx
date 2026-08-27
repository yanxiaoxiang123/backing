import { useMemo, useState } from 'react'
import { Alert, Button, Empty, Spin, Tag } from 'antd'
import {
  ArrowLeftOutlined,
  BulbOutlined,
  RobotOutlined,
  StarFilled,
  StarOutlined,
} from '@ant-design/icons'
import { LazyECharts } from '../components/charts/LazyECharts'
import { useNavigate, useParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { getStockOverview, addToWatchlist, removeFromWatchlist } from '../services/api'
import { useRealtimeKline } from '../hooks/useRealtimeKline'
import type { DashboardStock, KlineIndicator } from '../types'
import { stockKeys } from '../services/queryKeys'
import { normalizeStockCode } from '../utils/stockIdentity'

type PeriodType = 'daily' | 'weekly' | 'monthly'

function chartOption(data: KlineIndicator[]) {
  const dates = data.map((item) => item.date)
  return {
    animation: false,
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
    legend: { data: ['K线', '成交量'], top: 8 },
    grid: [
      { left: 44, right: 20, top: 42, height: '62%' },
      { left: 44, right: 20, top: '76%', height: '14%' },
    ],
    xAxis: [
      { type: 'category', data: dates, boundaryGap: true, axisLabel: { fontSize: 10 } },
      { type: 'category', data: dates, gridIndex: 1, axisLabel: { show: false } },
    ],
    yAxis: [
      { scale: true, axisLabel: { fontSize: 10 } },
      { gridIndex: 1, axisLabel: { show: false }, splitLine: { show: false } },
    ],
    dataZoom: [{ type: 'inside', xAxisIndex: [0, 1] }],
    series: [
      {
        name: 'K线',
        type: 'candlestick',
        data: data.map((item) => [item.open, item.close, item.low, item.high]),
        itemStyle: {
          color: '#eb001b',
          color0: '#52c41a',
          borderColor: '#eb001b',
          borderColor0: '#52c41a',
        },
      },
      {
        name: '成交量',
        type: 'bar',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: data.map((item) => ({
          value: item.volume,
          itemStyle: { color: item.close >= item.open ? '#eb001b' : '#52c41a' },
        })),
      },
    ],
  }
}

function StockChart() {
  const { code: routeCode } = useParams<{ code: string }>()
  const code = normalizeStockCode(routeCode) ?? routeCode
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [period, setPeriod] = useState<PeriodType>('daily')
  const [updatingWatchlist, setUpdatingWatchlist] = useState(false)
  const overviewQuery = useQuery({
    queryKey: stockKeys.overview(code || ''),
    queryFn: () => getStockOverview(code as string),
    enabled: Boolean(code),
  })
  const kline = useRealtimeKline(code, period)
  const overview = overviewQuery.data
  const quote = useMemo<DashboardStock | null>(() => {
    if (overview?.quote) return overview.quote
    const latest = kline.data[kline.data.length - 1]
    if (!latest) return null
    const previous = kline.data[kline.data.length - 2]
    const change = previous ? latest.close - previous.close : 0
    const changePercent = previous?.close ? (change / previous.close) * 100 : 0
    return {
      id: 0,
      code: overview?.stock.code || code || '',
      name: overview?.stock.name || code || '',
      current_price: latest.close,
      high: latest.high,
      low: latest.low,
      volume: latest.volume,
      change,
      change_percent: changePercent,
    }
  }, [code, kline.data, overview?.quote, overview?.stock.code, overview?.stock.name])
  const positive = (quote?.change_percent ?? 0) >= 0

  const option = useMemo(() => chartOption(kline.data), [kline.data])
  const toggleWatchlist = async () => {
    if (!code || updatingWatchlist) return
    setUpdatingWatchlist(true)
    try {
      if (overview?.watchlisted) await removeFromWatchlist(code)
      else await addToWatchlist(code)
      await queryClient.invalidateQueries({ queryKey: stockKeys.overview(code) })
      await queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    } finally {
      setUpdatingWatchlist(false)
    }
  }

  if (!code) return <Empty description="缺少股票代码" />

  return (
    <div className="fade-in stock-research-page">
      <header className="page-header stock-research-header">
        <div className="stock-research-heading">
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/stocks')}>
            返回
          </Button>
          <div>
            <div className="eyebrow">STOCK RESEARCH</div>
            <h1 className="page-title">{overview?.stock.name || code}</h1>
            <span className="stock-code-label">{code}</span>
          </div>
        </div>
        <div className="stock-research-actions">
          <Button
            icon={overview?.watchlisted ? <StarFilled /> : <StarOutlined />}
            loading={updatingWatchlist}
            onClick={() => void toggleWatchlist()}
          >
            {overview?.watchlisted ? '已自选' : '加入自选'}
          </Button>
          <Button
            type="primary"
            icon={<RobotOutlined />}
            onClick={() => navigate(`/workspace?stock=${encodeURIComponent(code)}`)}
          >
            让 AI 研究
          </Button>
        </div>
      </header>

      {overviewQuery.isError && (
        <Alert
          type="warning"
          showIcon
          message="股票摘要暂不可用"
          description="K 线仍会尝试独立加载。"
        />
      )}

      <section className="stock-metrics-grid">
        <div className="stock-price-card">
          <span className="eyebrow">LATEST PRICE</span>
          <strong>{quote ? quote.current_price.toFixed(2) : '—'}</strong>
          <span className={positive ? 'price-up' : 'price-down'}>
            {quote
              ? `${positive ? '+' : ''}${quote.change.toFixed(2)} (${positive ? '+' : ''}${quote.change_percent.toFixed(2)}%)`
              : '等待行情'}
          </span>
        </div>
        <div className="stock-metric">
          <span>日内高点</span>
          <strong>{quote?.high?.toFixed(2) || '—'}</strong>
        </div>
        <div className="stock-metric">
          <span>日内低点</span>
          <strong>{quote?.low?.toFixed(2) || '—'}</strong>
        </div>
        <div className="stock-metric">
          <span>成交量</span>
          <strong>{quote ? `${(quote.volume / 10000).toFixed(0)}万` : '—'}</strong>
        </div>
      </section>

      <section className="stock-research-layout">
        <div className="research-panel stock-chart-panel">
          <div className="section-heading">
            <div>
              <div className="eyebrow">PRICE ACTION</div>
              <h2>K 线与成交量</h2>
            </div>
            <div className="period-switcher" role="group" aria-label="K线周期">
              {(['daily', 'weekly', 'monthly'] as PeriodType[]).map((value) => (
                <button
                  key={value}
                  className={period === value ? 'active' : ''}
                  onClick={() => setPeriod(value)}
                >
                  {value === 'daily' ? '日K' : value === 'weekly' ? '周K' : '月K'}
                </button>
              ))}
            </div>
          </div>
          {kline.error ? <Alert type="error" showIcon message={kline.error} /> : null}
          <Spin spinning={kline.loading}>
            {kline.data.length ? (
              <LazyECharts
                option={option}
                style={{ height: 'min(62vh, 680px)' }}
                notMerge
                lazyUpdate
              />
            ) : (
              <Empty description="暂无 K 线数据，请先同步行情" />
            )}
          </Spin>
          <div className="chart-status">
            <span
              className={kline.connected ? 'status-dot status-dot--live' : 'status-dot'}
            />
            {kline.connected ? '实时连接' : kline.fallback ? 'HTTP 降级' : '等待连接'}
          </div>
        </div>

        <aside className="stock-research-side">
          <div className="research-panel">
            <div className="eyebrow">SIGNAL SNAPSHOT</div>
            <h2>
              <BulbOutlined /> 技术摘要
            </h2>
            <div className="signal-placeholder">
              <Tag color={positive ? 'red' : 'green'}>{positive ? '偏强' : '偏弱'}</Tag>
              <p>基于最新行情和技术数据生成研究提示。</p>
            </div>
            <Button
              block
              icon={<RobotOutlined />}
              onClick={() => navigate(`/workspace?stock=${encodeURIComponent(code)}`)}
            >
              生成 AI 研究摘要
            </Button>
          </div>
          <div className="research-panel">
            <div className="eyebrow">NEXT ACTION</div>
            <h2>验证一个假设</h2>
            <p className="side-copy">
              将当前标的带入策略研究，比较不同参数下的收益和风险。
            </p>
            <Button
              block
              onClick={() => navigate(`/strategies?stock=${encodeURIComponent(code)}`)}
            >
              进入策略验证
            </Button>
          </div>
        </aside>
      </section>
    </div>
  )
}

export default StockChart
