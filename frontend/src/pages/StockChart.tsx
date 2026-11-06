import { Prose } from '../components/Prose'
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
import { ChartResetButton } from '../components/charts/ChartResetButton'
import { QueryStatus } from '../components/research/QueryStatus'
import { formatNumber, formatPercent, numberTone } from '../utils/dataFormat'
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
    backgroundColor: 'transparent',
    animation: false,
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    tooltip: {
      trigger: 'axis',
      confine: true,
      axisPointer: { type: 'cross' },
      backgroundColor: 'transparent',
      borderColor: '#e8e8e8',
      textStyle: { color: '#242424' },
    },
    legend: {
      data: ['K线', '成交量'],
      top: 8,
      textStyle: { color: '#777777', fontSize: 13 },
    },
    grid: [
      { left: 48, right: 20, top: 42, height: '58%' },
      { left: 48, right: 20, top: '73%', height: '12%' },
    ],
    xAxis: [
      {
        type: 'category',
        data: dates,
        boundaryGap: true,
        axisLabel: { fontSize: 12, color: '#777777', hideOverlap: true },
      },
      { type: 'category', data: dates, gridIndex: 1, axisLabel: { show: false } },
    ],
    yAxis: [
      {
        scale: true,
        axisLabel: {
          fontSize: 12,
          color: '#777777',
          formatter: (value: number) => formatNumber(value),
        },
        splitLine: { lineStyle: { color: '#eeeeee' } },
      },
      { gridIndex: 1, axisLabel: { show: false }, splitLine: { show: false } },
    ],
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1] },
      {
        type: 'slider',
        moveHandleSize: 0,
        xAxisIndex: [0, 1],
        height: 24,
        bottom: 0,
        left: 48,
        right: 20,
        showDetail: false,
        borderColor: '#eeeeee',
        backgroundColor: '#f7f7f7',
        fillerColor: 'rgba(150, 150, 150, 0.12)',
        dataBackground: {
          lineStyle: { color: '#bbbbbb' },
          areaStyle: { color: '#eeeeee' },
        },
        selectedDataBackground: {
          lineStyle: { color: '#aaaaaa' },
          areaStyle: { color: '#dddddd' },
        },
      },
    ],
    series: [
      {
        name: 'K线',
        type: 'candlestick',
        data: data.map((item) => [item.open, item.close, item.low, item.high]),
        itemStyle: {
          color: '#c4242a',
          color0: '#1e7a4d',
          borderColor: '#c4242a',
          borderColor0: '#1e7a4d',
        },
      },
      {
        name: '成交量',
        type: 'bar',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: data.map((item) => ({
          value: item.volume,
          itemStyle: {
            color: item.close >= item.open ? '#c4242a' : '#1e7a4d',
            opacity: 0.5,
          },
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
  const [resetKey, setResetKey] = useState(0)
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
  const changeTone = numberTone(quote?.change_percent)

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
            <Prose as="h1" className="page-title">
              {overview?.stock.name || code}
            </Prose>
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
          <span className="stock-quote-label">最新价格</span>
          <strong>{formatNumber(quote?.current_price)}</strong>
          <span className={changeTone}>
            {quote
              ? `${numberTone(quote.change) === 'price-up' ? '+' : ''}${formatNumber(quote.change)} (${formatPercent(quote.change_percent, 2, true)})`
              : '等待行情'}
          </span>
        </div>
        <div className="stock-metric">
          <span>日内高点</span>
          <strong>{formatNumber(quote?.high)}</strong>
        </div>
        <div className="stock-metric">
          <span>日内低点</span>
          <strong>{formatNumber(quote?.low)}</strong>
        </div>
        <div className="stock-metric">
          <span>成交量</span>
          <strong>
            {quote ? `${formatNumber(quote.volume / 10000, 0)}万股` : '—'}
          </strong>
        </div>
      </section>

      <section className="stock-research-layout">
        <div className="research-panel stock-chart-panel">
          <div className="section-heading">
            <div>
              <div className="eyebrow">PRICE ACTION</div>
              <Prose as="h2">K 线与成交量</Prose>
            </div>
            <div className="research-chart-actions">
              <QueryStatus
                fetching={kline.loading && kline.data.length > 0}
                label="行情更新中"
              />
              <ChartResetButton onReset={() => setResetKey((value) => value + 1)} />
              <div className="period-switcher" role="group" aria-label="K线周期">
                {(['daily', 'weekly', 'monthly'] as PeriodType[]).map((value) => (
                  <button
                    key={value}
                    className={period === value ? 'active' : ''}
                    aria-pressed={period === value}
                    onClick={() => setPeriod(value)}
                  >
                    {value === 'daily' ? '日K' : value === 'weekly' ? '周K' : '月K'}
                  </button>
                ))}
              </div>
            </div>
          </div>
          {kline.error ? <Alert type="error" showIcon message={kline.error} /> : null}
          <Spin spinning={kline.loading && !kline.data.length}>
            {kline.data.length ? (
              <LazyECharts
                resetKey={resetKey}
                option={option}
                style={{ height: 440 }}
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
            {kline.freshness.stale ? (
              <Tag color="orange">
                行情延迟
                {kline.freshness.cache_age_ms != null
                  ? ` ${Math.round(kline.freshness.cache_age_ms / 1000)} 秒`
                  : ''}
              </Tag>
            ) : null}
          </div>
        </div>

        <aside className="stock-research-side">
          <div className="research-panel">
            <div className="eyebrow">SIGNAL SNAPSHOT</div>
            <Prose as="h2">
              <BulbOutlined /> 技术摘要
            </Prose>
            <div className="signal-placeholder">
              <Tag className={changeTone}>
                {!quote
                  ? '等待行情'
                  : changeTone === 'price-up'
                    ? '当日上涨'
                    : changeTone === 'price-down'
                      ? '当日下跌'
                      : '当日持平'}
              </Tag>
              <Prose as="p">基于最新行情和技术数据生成研究提示。</Prose>
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
            <Prose as="h2">验证一个假设</Prose>
            <Prose as="p" className="side-copy">
              将当前标的带入策略研究，比较不同参数下的收益和风险。
            </Prose>
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
