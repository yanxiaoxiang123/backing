import { Prose } from '../components/Prose'
import { useMemo, useState } from 'react'
import { Button, Select } from 'antd'
import {
  ArrowRightOutlined,
  CheckCircleOutlined,
  ReloadOutlined,
} from '@ant-design/icons'
import { Link, useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import dayjs from 'dayjs'
import type { EChartsOption, TooltipComponentFormatterCallbackParams } from 'echarts'

import { LazyECharts } from '../components/charts/LazyECharts'
import { PageHeader } from '../components/research/ResearchPrimitives'
import {
  useDashboardIndices,
  useDashboardQuotes,
  useDashboardTrend,
  useDashboardWatchlist,
  useLatestAnalyses,
} from '../hooks/useDashboardData'
import { useSystemStatus } from '../hooks/useSystemStatus'
import { getApiErrorMessage } from '../services/api'
import type { AnalysisRecord, DashboardStock } from '../types'
import { buildStockIdentityMap, normalizeStockCode } from '../utils/stockIdentity'

const SIGNAL_MAP: Record<string, { label: string; tone: 'buy' | 'sell' | 'hold' }> = {
  buy: { label: '买入', tone: 'buy' },
  sell: { label: '卖出', tone: 'sell' },
  hold: { label: '持有', tone: 'hold' },
}

const MODE_LABELS: Record<string, string> = {
  quick: '快速',
  standard: '标准',
  full: '深度',
  strategy: '策略',
}

const TREND_RANGES = [
  { months: 1, label: '1月' },
  { months: 3, label: '3月' },
  { months: 6, label: '6月' },
  { months: 12, label: '1年' },
]

const OVERVIEW_VIEWS = [
  { id: 'chart', label: '走势' },
  { id: 'watchlist', label: '自选股' },
  { id: 'alerts', label: '任务告警' },
  { id: 'history', label: '最近分析' },
] as const

function signalOf(signal?: string) {
  return SIGNAL_MAP[signal ?? ''] ?? SIGNAL_MAP.hold
}

function confidencePct(value: number): number {
  const pct = value <= 1 ? value * 100 : value
  return Math.max(0, Math.min(100, Math.round(pct)))
}

function analysisTime(record: AnalysisRecord): string {
  const parsed = dayjs(record.created_at || record.analysis_date)
  if (!parsed.isValid()) return '时间未知'
  if (parsed.isSame(dayjs(), 'day')) return `今天 ${parsed.format('HH:mm')}`
  if (parsed.isSame(dayjs().subtract(1, 'day'), 'day')) {
    return `昨天 ${parsed.format('HH:mm')}`
  }
  return parsed.format('MM-DD HH:mm')
}

function alertTime(raw?: string | null): string {
  if (!raw) return '时间未知'
  const parsed = dayjs(raw)
  if (!parsed.isValid()) return '时间未知'
  if (parsed.isSame(dayjs(), 'day')) return parsed.format('HH:mm')
  if (parsed.isSame(dayjs().subtract(1, 'day'), 'day')) {
    return `昨天 ${parsed.format('HH:mm')}`
  }
  return parsed.format('MM-DD HH:mm')
}

function formatVolume(volume: number): string {
  if (!Number.isFinite(volume) || volume <= 0) return '—'
  if (volume >= 100_000_000) return `${(volume / 100_000_000).toFixed(2)} 亿`
  if (volume >= 10_000) return `${(volume / 10_000).toFixed(0)} 万`
  return volume.toLocaleString('zh-CN')
}

function formatIndex(value?: number): string {
  if (value == null || !Number.isFinite(value) || value <= 0) return '—'
  return value.toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

function InlineError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="dash-inline-error" role="alert">
      <span>{message}</span>
      <button type="button" onClick={onRetry}>
        重试
      </button>
    </div>
  )
}

function StockTable({
  stocks,
  onOpen,
}: {
  stocks: DashboardStock[]
  onOpen: (code: string) => void
}) {
  return (
    <div className="dash-table-wrap">
      <table className="dash-table">
        <thead>
          <tr>
            <th>标的</th>
            <th className="num">最新价</th>
            <th className="num">涨跌幅</th>
            <th className="num dash-col-volume">成交量</th>
          </tr>
        </thead>
        <tbody>
          {stocks.map((stock) => {
            const tone =
              stock.change_percent > 0
                ? 'is-up'
                : stock.change_percent < 0
                  ? 'is-down'
                  : 'is-flat'
            return (
              <tr key={stock.code} onClick={() => onOpen(stock.code)}>
                <td>
                  <Link
                    to={`/stocks/${stock.code}`}
                    className="dash-stock-link"
                    onClick={(event) => event.stopPropagation()}
                  >
                    <span className="dash-stock-name">{stock.name}</span>
                    <span className="dash-stock-code">
                      {stock.code}
                      <span className="dash-mobile-volume">
                        {' '}
                        · {formatVolume(stock.volume)}
                      </span>
                    </span>
                  </Link>
                </td>
                <td className="num dash-price">{stock.current_price.toFixed(2)}</td>
                <td className={`num dash-change ${tone}`}>
                  {stock.change_percent > 0 ? '+' : ''}
                  {stock.change_percent.toFixed(2)}%
                </td>
                <td className="num dash-volume">{formatVolume(stock.volume)}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function TableSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div aria-hidden="true">
      {Array.from({ length: rows }, (_, row) => (
        <div key={row} className="dash-skeleton dash-skeleton--row" />
      ))}
    </div>
  )
}

function HeroSkeleton() {
  return <div className="dash-skeleton dash-skeleton--title" aria-hidden="true" />
}

function EmptyChart() {
  return (
    <div className="dash-empty-chart" role="img" aria-label="暂无走势数据">
      <svg viewBox="0 0 100 40" preserveAspectRatio="none" aria-hidden="true">
        <line x1="0" y1="10" x2="100" y2="10" />
        <line x1="0" y1="20" x2="100" y2="20" />
        <line x1="0" y1="30" x2="100" y2="30" />
        <line x1="0" y1="39" x2="100" y2="39" className="baseline" />
      </svg>
      <span>暂无走势数据</span>
    </div>
  )
}

function Dashboard() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [selectedCode, setSelectedCode] = useState('')
  const [trendMonths, setTrendMonths] = useState(6)
  const [overviewView, setOverviewView] =
    useState<(typeof OVERVIEW_VIEWS)[number]['id']>('chart')

  const watchlistQuery = useDashboardWatchlist()
  const indicesQuery = useDashboardIndices()
  const analysesQuery = useLatestAnalyses(5)
  const system = useSystemStatus()

  const watchlistItems = useMemo(
    () => watchlistQuery.data?.items ?? [],
    [watchlistQuery.data],
  )
  const watchlistCodes = useMemo(
    () =>
      watchlistItems.map(
        (item) => normalizeStockCode(item.stock_code) ?? item.stock_code,
      ),
    [watchlistItems],
  )
  const quotesQuery = useDashboardQuotes(watchlistCodes)

  const identities = useMemo(() => {
    return buildStockIdentityMap(
      watchlistItems.map((item) => ({
        code: item.stock_code,
        name: item.stock_name || item.stock_code,
      })),
      (item) => item.code,
    )
  }, [watchlistItems])

  const stocks = useMemo<DashboardStock[]>(
    () =>
      (quotesQuery.data?.data ?? [])
        .map((quote) => {
          const identity = identities.get(quote.symbol)
          return {
            id: 0,
            code:
              normalizeStockCode(identity?.code || quote.symbol) ||
              identity?.code ||
              quote.symbol,
            name: identity?.name || quote.symbol,
            current_price: quote.close,
            high: quote.high,
            low: quote.low,
            volume: quote.volume,
            change: quote.change,
            change_percent: quote.change_percent,
          }
        })
        .sort((a, b) => b.change_percent - a.change_percent),
    [identities, quotesQuery.data],
  )

  const analyses = analysesQuery.data ?? []
  const latest = analyses[0]
  const analyzedCode = latest
    ? (normalizeStockCode(latest.stock_code) ?? latest.stock_code)
    : ''
  const chartDefault =
    analyzedCode && watchlistCodes.includes(analyzedCode)
      ? analyzedCode
      : stocks[0]?.code || watchlistCodes[0]
  const activeCode = selectedCode || chartDefault
  const trendQuery = useDashboardTrend(activeCode)
  const signal = signalOf(latest?.final_signal)
  const confidence = latest ? confidencePct(latest.final_confidence) : null
  const latestTime = latest ? analysisTime(latest) : null
  const latestIsToday = latest
    ? dayjs(latest.created_at || latest.analysis_date).isSame(dayjs(), 'day')
    : false
  const modeLabel = latest?.mode ? (MODE_LABELS[latest.mode] ?? latest.mode) : null
  const reasonLines = latest?.final_reason?.match(/[^。！？\n]+[。！？]?/g) ?? []
  const researchHeadline = reasonLines[0] || latest?.final_reason
  const researchDetail = reasonLines.slice(1).join('')

  const up = stocks.filter((stock) => stock.change_percent > 0).length
  const down = stocks.filter((stock) => stock.change_percent < 0).length
  const flat = stocks.length - up - down
  const visibleStocks = stocks.slice(0, 4)
  const trendBars = useMemo(() => {
    const bars = [...(trendQuery.data?.data ?? [])].sort((a, b) =>
      a.date.localeCompare(b.date),
    )
    if (!bars.length) return bars
    // Anchor the window to the last available trading day, including stale feeds.
    const start = dayjs(bars[bars.length - 1].date).subtract(trendMonths, 'month')
    return bars.filter((bar) => !dayjs(bar.date).isBefore(start, 'day'))
  }, [trendQuery.data, trendMonths])
  const latestClose = trendBars.length ? trendBars[trendBars.length - 1].close : null
  const previousClose =
    trendBars.length > 1 ? trendBars[trendBars.length - 2].close : null
  const latestChange =
    latestClose != null && previousClose != null && previousClose > 0
      ? ((latestClose - previousClose) / previousClose) * 100
      : null

  const trendOption = useMemo<EChartsOption>(() => {
    const bars = trendBars
    const labelStep = Math.max(0, Math.ceil(bars.length / 5) - 1)
    return {
      animation: false,
      grid: { left: 0, right: 6, top: 8, bottom: 2, containLabel: true },
      tooltip: {
        trigger: 'axis',
        backgroundColor: '#ffffff',
        borderWidth: 1,
        borderColor: '#e8e8e8',
        padding: [6, 8],
        textStyle: { color: '#242424', fontSize: 13 },
        formatter: (params: TooltipComponentFormatterCallbackParams) => {
          const list = Array.isArray(params) ? params : [params]
          const first = list[0] as { axisValue?: string; value?: number }
          return `${first.axisValue ?? ''}<br/>${Number(first.value ?? 0).toFixed(2)}`
        },
      },
      xAxis: {
        type: 'category',
        boundaryGap: false,
        data: bars.map((bar) => bar.date),
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: {
          color: '#6b6b6b',
          fontSize: 11,
          interval: labelStep,
          hideOverlap: true,
          formatter: (value: string) => dayjs(value).format('MM/DD'),
        },
      },
      yAxis: {
        type: 'value',
        scale: true,
        splitNumber: 4,
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { color: '#6b6b6b', fontSize: 11 },
        splitLine: { lineStyle: { color: '#eaeaea', width: 1 } },
      },
      series: [
        {
          type: 'line',
          data: bars.map((bar) => bar.close),
          smooth: false,
          symbol: 'none',
          lineStyle: { color: '#1677ff', width: 2 },
          areaStyle: { color: '#1677ff', opacity: 0.06 },
        },
      ],
      media: [
        {
          query: { maxHeight: 120 },
          option: {
            yAxis: { splitNumber: 2, axisLabel: { hideOverlap: true } },
          },
        },
      ],
    }
  }, [trendBars])

  const isRefreshing =
    indicesQuery.isFetching ||
    quotesQuery.isFetching ||
    watchlistQuery.isFetching ||
    trendQuery.isFetching ||
    analysesQuery.isFetching

  const handleRefresh = () => {
    void queryClient.invalidateQueries()
  }

  const heroTitle = analysesQuery.isLoading
    ? '今天的研究结论'
    : latest
      ? latestIsToday
        ? '今天的研究结论'
        : '最近的研究结论'
      : '今天还没有研究结论'

  return (
    <div className="dash">
      <PageHeader
        eyebrow="RESEARCH OVERVIEW"
        title="仪表盘"
        subtitle="跟踪市场、自选标的与研究进展"
        actions={
          <Button
            icon={<ReloadOutlined aria-hidden="true" spin={isRefreshing} />}
            onClick={handleRefresh}
            disabled={isRefreshing}
          >
            {isRefreshing ? '刷新中' : '刷新数据'}
          </Button>
        }
      />
      <section className="dash-panel dash-market" aria-labelledby="dash-market-title">
        <div className="dash-panel-head">
          <Prose as="h2" id="dash-market-title" className="dash-panel-title">
            市场概览
          </Prose>
          <span className="dash-panel-meta">
            {indicesQuery.isError
              ? '行情不可用'
              : indicesQuery.isFetching
                ? '更新中'
                : '较昨收'}
          </span>
        </div>

        {indicesQuery.isError ? (
          <InlineError
            message={getApiErrorMessage(indicesQuery.error)}
            onRetry={() => void indicesQuery.refetch()}
          />
        ) : indicesQuery.isLoading ? (
          <div className="dash-index-grid">
            {[0, 1, 2, 3].map((cell) => (
              <div key={cell} className="dash-index-cell">
                <div className="dash-skeleton dash-skeleton--line short" />
                <div className="dash-skeleton dash-skeleton--index" />
              </div>
            ))}
          </div>
        ) : (
          <div className="dash-index-grid">
            {(indicesQuery.data?.data ?? []).map((index) => {
              const tone =
                index.change_percent > 0
                  ? 'is-up'
                  : index.change_percent < 0
                    ? 'is-down'
                    : 'is-flat'
              const sign = index.change_percent > 0 ? '+' : ''
              return (
                <div className="dash-index-cell" key={index.symbol}>
                  <div className="dash-index-name">{index.name}</div>
                  <div className="dash-index-value">{formatIndex(index.close)}</div>
                  <div className={`dash-index-change ${tone}`}>
                    {sign}
                    {index.change.toFixed(2)} ({sign}
                    {index.change_percent.toFixed(2)}%)
                  </div>
                </div>
              )
            })}
          </div>
        )}

        <div className="dash-breadth">
          <span>自选股表现</span>
          <div
            className="dash-breadth-bar"
            role="img"
            aria-label={`上涨 ${up}，下跌 ${down}，平盘 ${flat}`}
          >
            {stocks.length ? (
              <>
                {up ? <span className="is-up" style={{ flexGrow: up }} /> : null}
                {down ? <span className="is-down" style={{ flexGrow: down }} /> : null}
                {flat ? <span className="is-flat" style={{ flexGrow: flat }} /> : null}
              </>
            ) : (
              <span className="is-empty" />
            )}
          </div>
          <span className="dash-breadth-legend">
            <span className="is-up">涨 {up}</span>
            <span className="is-down">跌 {down}</span>
            <span className="is-flat">平 {flat}</span>
          </span>
        </div>
      </section>

      <section className="dash-panel dash-hero" aria-labelledby="dash-title">
        <div className="dash-panel-head">
          <Prose as="h2" id="dash-title" className="dash-title">
            {heroTitle}
          </Prose>
          <div className="dash-meta">
            {latest ? (
              <span>
                {latest.stock_name || latest.stock_code} · {latest.stock_code}
              </span>
            ) : (
              <span>AI 研究</span>
            )}
            {latestTime ? (
              <>
                <span className="dash-meta-sep" />
                <span>{latestTime}</span>
              </>
            ) : null}
          </div>
        </div>
        <div className="dash-hero-content">
          <div className="dash-hero-main">
            {analysesQuery.isError ? (
              <InlineError
                message={getApiErrorMessage(analysesQuery.error)}
                onRetry={() => void analysesQuery.refetch()}
              />
            ) : analysesQuery.isLoading ? (
              <HeroSkeleton />
            ) : latest ? (
              latest.final_reason ? (
                <Prose as="p" className="dash-note" title={latest.final_reason}>
                  {researchHeadline}
                </Prose>
              ) : (
                <Prose as="p" className="dash-note dash-note--muted">
                  AI 没有给出文字理由，请打开完整分析查看依据。
                </Prose>
              )
            ) : (
              <Prose as="p" className="dash-note dash-note--muted">
                选一只自选股，让 AI 跑一次分析，这里会出现今天的结论、信号和置信度。
              </Prose>
            )}
            <Prose as="p" className="dash-research-caption">
              {latest
                ? researchDetail ||
                  `${modeLabel || 'AI'}研究 · 结合行情时效与完整报告中的证据判断。`
                : '从自选标的开始，跟踪信号与研究依据。'}
            </Prose>
            <div className="dash-hero-actions">
              <Button type="primary" onClick={() => navigate('/agent')}>
                {latest ? '打开分析报告' : '发起分析'}
              </Button>
              {latest ? (
                <button
                  type="button"
                  className="dash-text-action"
                  onClick={() => navigate(`/stocks/${latest.stock_code}`)}
                >
                  查看标的
                  <ArrowRightOutlined />
                </button>
              ) : null}
            </div>
          </div>

          <aside className="dash-hero-side" aria-label="本次结论">
            <div className="dash-hero-side-label">本次结论</div>
            {analysesQuery.isLoading ? (
              <>
                <div className="dash-skeleton dash-skeleton--side" />
              </>
            ) : latest ? (
              <>
                <span className={`dash-signal dash-signal--${signal.tone}`}>
                  {signal.label}
                </span>
                <div className="dash-hero-confidence">
                  <div className="dash-confidence">
                    {confidence}
                    <span>%</span>
                  </div>
                  <div className="dash-confidence-label">置信度</div>
                </div>
                <div className="dash-side-time">模型结论，仅供研究参考</div>
              </>
            ) : (
              <>
                <span className="dash-signal dash-signal--hold">未分析</span>
                <div className="dash-hero-confidence">
                  <div className="dash-confidence dash-confidence--empty">—</div>
                  <div className="dash-confidence-label">置信度</div>
                </div>
                <div className="dash-side-time">今天还没有新的分析</div>
              </>
            )}
          </aside>
        </div>
      </section>

      <nav className="dash-view-switch" aria-label="仪表盘内容">
        {OVERVIEW_VIEWS.map((view) => (
          <button
            key={view.id}
            type="button"
            aria-pressed={overviewView === view.id}
            onClick={() => setOverviewView(view.id)}
          >
            {view.label}
          </button>
        ))}
      </nav>
      <div className="dash-grid" data-view={overviewView}>
        <section
          className="dash-panel dash-watchlist"
          aria-labelledby="dash-watchlist-title"
        >
          <div className="dash-panel-head">
            <Prose as="h2" id="dash-watchlist-title" className="dash-panel-title">
              自选股 <span className="dash-panel-count">{stocks.length}</span>
              <span className="dash-panel-meta">按涨跌幅</span>
            </Prose>
            <Link to="/watchlist" className="dash-panel-link">
              管理自选 →
            </Link>
          </div>
          {watchlistQuery.isError ? (
            <InlineError
              message={getApiErrorMessage(watchlistQuery.error)}
              onRetry={() => void watchlistQuery.refetch()}
            />
          ) : watchlistQuery.isLoading ? (
            <TableSkeleton />
          ) : quotesQuery.isError ? (
            <InlineError
              message={getApiErrorMessage(quotesQuery.error)}
              onRetry={() => void quotesQuery.refetch()}
            />
          ) : quotesQuery.isLoading && !stocks.length ? (
            <TableSkeleton />
          ) : visibleStocks.length ? (
            <StockTable
              stocks={visibleStocks}
              onOpen={(code) => navigate(`/stocks/${code}`)}
            />
          ) : (
            <Prose as="p" className="dash-empty">
              自选股为空。<Link to="/watchlist">去添加自选股</Link>
            </Prose>
          )}
        </section>

        <section className="dash-panel dash-alerts" aria-labelledby="dash-alerts-title">
          <div className="dash-panel-head">
            <Prose as="h2" id="dash-alerts-title" className="dash-panel-title">
              任务与告警
            </Prose>
            <span className="dash-unread-count">
              {system.alertsError ? '—' : system.unreadAlerts} 未读
            </span>
          </div>
          <div className="dash-status-line">
            <CheckCircleOutlined />
            <span>本次运行</span>
            <strong>{system.metricsError ? '—' : system.completed}</strong>
            <span>完成</span>
            {!system.metricsError && system.failed ? (
              <>
                <span>·</span>
                <strong className="is-bad">{system.failed}</strong>
                <span>失败</span>
              </>
            ) : null}
          </div>
          {system.alertsError ? (
            <InlineError message="告警加载失败" onRetry={system.refetch} />
          ) : system.isLoading ? (
            <TableSkeleton rows={2} />
          ) : system.alerts.length ? (
            <div className="dash-alert-list">
              {system.alerts.slice(0, 3).map((alert) => (
                <button
                  key={alert.id}
                  type="button"
                  className={`dash-alert${alert.is_read ? ' is-read' : ''}`}
                  onClick={() => navigate('/workspace')}
                >
                  <span
                    className={`dash-alert-dot ${
                      alert.is_read ? 'is-read' : `is-${alert.severity || 'info'}`
                    }`}
                  />
                  <span className="dash-alert-body">
                    <span className="dash-alert-message" title={alert.message}>
                      {alert.message}
                    </span>
                    <span className="dash-alert-time">
                      {alertTime(alert.created_at)}
                    </span>
                  </span>
                </button>
              ))}
            </div>
          ) : (
            <Prose as="p" className="dash-empty">
              暂无告警。
            </Prose>
          )}
          <div className="dash-alert-actions">
            <Button onClick={() => navigate('/workspace')}>打开工作台 →</Button>
            <Link to="/workspace" className="dash-panel-link">
              查看全部告警
            </Link>
          </div>
        </section>

        <section className="dash-panel dash-chart" aria-labelledby="dash-chart-title">
          <div className="dash-panel-head">
            <Prose as="h2" id="dash-chart-title" className="dash-panel-title">
              自选股走势
            </Prose>
            <div className="dash-chart-controls">
              <Select
                aria-label="选择走势股票"
                className="dash-chart-select"
                placeholder="选择股票"
                value={activeCode || undefined}
                onChange={setSelectedCode}
                allowClear
                options={watchlistItems.map((item) => ({
                  value: normalizeStockCode(item.stock_code) ?? item.stock_code,
                  label: `${item.stock_name || item.stock_code} (${item.stock_code})`,
                }))}
              />
            </div>
            <div className="dash-range-switch" role="group" aria-label="走势时间范围">
              {TREND_RANGES.map((range) => (
                <button
                  type="button"
                  key={range.months}
                  aria-pressed={trendMonths === range.months}
                  onClick={() => setTrendMonths(range.months)}
                >
                  {range.label}
                </button>
              ))}
            </div>
          </div>
          <div className="dash-chart-quote">
            <strong>
              {!trendQuery.isError && latestClose != null
                ? latestClose.toFixed(2)
                : '—'}
            </strong>
            {!trendQuery.isError && latestChange != null ? (
              <span
                className={
                  latestChange > 0 ? 'is-up' : latestChange < 0 ? 'is-down' : 'is-flat'
                }
              >
                {latestChange > 0 ? '+' : ''}
                {latestChange.toFixed(2)}%<small>较前收</small>
              </span>
            ) : null}
            <span className="dash-chart-source">
              日线{trendQuery.data?.stale ? ' · 缓存行情' : ''}
            </span>
          </div>
          {trendQuery.isError ? (
            <InlineError
              message={getApiErrorMessage(trendQuery.error)}
              onRetry={() => void trendQuery.refetch()}
            />
          ) : trendQuery.isLoading ? (
            <div className="dash-skeleton dash-skeleton--chart" />
          ) : trendQuery.data?.data.length ? (
            <div className="dash-chart-card">
              <LazyECharts
                option={trendOption}
                revealKey={`${activeCode}:${trendMonths}`}
                style={{ height: '100%', minHeight: 0 }}
                summary={`${activeCode || '自选股'}近${trendMonths}个月收盘价走势，${trendBars.length}个交易日`}
                notMerge
                lazyUpdate
              />
            </div>
          ) : (
            <EmptyChart />
          )}
          <div className="dash-chart-foot">
            <span>
              {trendQuery.isError
                ? '行情暂不可用'
                : trendBars.length
                  ? `${trendBars[0].date} — ${trendBars[trendBars.length - 1].date}`
                  : '等待行情数据'}
            </span>
            <span>{!trendQuery.isError ? `${trendBars.length} 个交易日` : ''}</span>
          </div>
        </section>

        <section
          className="dash-panel dash-history"
          aria-labelledby="dash-history-title"
        >
          <div className="dash-panel-head">
            <Prose as="h2" id="dash-history-title" className="dash-panel-title">
              最近分析
            </Prose>
            <Link to="/agent" className="dash-panel-link">
              全部 →
            </Link>
          </div>
          {analysesQuery.isLoading ? (
            <TableSkeleton rows={2} />
          ) : analysesQuery.isError ? (
            <Prose as="p" className="dash-empty">
              分析记录暂不可用。
            </Prose>
          ) : analyses.length ? (
            <div className="dash-history-list">
              {analyses.slice(0, 2).map((record) => {
                const recordSignal = signalOf(record.final_signal)
                return (
                  <button
                    key={record.id}
                    type="button"
                    className="dash-history-row"
                    onClick={() => navigate('/agent')}
                  >
                    <span className="dash-history-stock">
                      <span className="dash-stock-name">
                        {record.stock_name || record.stock_code}
                      </span>
                      <span className="dash-stock-code">{record.stock_code}</span>
                    </span>
                    <span className={`dash-signal dash-signal--${recordSignal.tone}`}>
                      {recordSignal.label}
                    </span>
                    <span className="dash-history-meta">
                      <strong>{confidencePct(record.final_confidence)}%</strong>
                      <span>{analysisTime(record)}</span>
                    </span>
                  </button>
                )
              })}
            </div>
          ) : (
            <Prose as="p" className="dash-empty">
              还没有分析记录。<Link to="/agent">发起第一次分析</Link>
            </Prose>
          )}
          <Prose as="p" className="dash-history-note">
            研究结论可能受数据完整性影响
          </Prose>
        </section>
      </div>
      <footer className="dash-footer">
        行情与模型结果仅供研究，请结合数据时效与证据判断。
      </footer>
    </div>
  )
}

export default Dashboard
