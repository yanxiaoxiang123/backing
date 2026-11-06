import { Card, Descriptions, Empty, Spin, Table, Tabs, Tag } from 'antd'
import { LoadingOutlined } from '@ant-design/icons'
import { LazyECharts } from '../charts/LazyECharts'
import type { EChartsOption } from 'echarts'
import { Link } from 'react-router-dom'
import type {
  SignalDataPoint,
  SignalStats,
  StrategyBacktestResponse,
} from '../../types'
import { KlineData } from '../../utils/chart'
import { useState } from 'react'
import { FinancialValue } from '../research/FinancialValue'
import { QueryStatus } from '../research/QueryStatus'
import { ChartResetButton } from '../charts/ChartResetButton'
import {
  formatDate,
  formatNumber,
  formatPercent,
  isFiniteNumber,
  tradeAction,
} from '../../utils/dataFormat'

interface StrategyResultsProps {
  klineData: KlineData[]
  signals: SignalDataPoint[]
  signalStats: SignalStats | null
  backtestResult: StrategyBacktestResponse | null
  loading: { signals: boolean; backtest: boolean }
  chartRef: React.RefObject<HTMLDivElement>
  chartOption: EChartsOption
  portfolioChartOption: EChartsOption
  children?: React.ReactNode
}

const tradeColumns = [
  { title: '日期', dataIndex: 'date', key: 'date' },
  {
    title: '操作',
    dataIndex: 'action',
    key: 'action',
    render: (action: string) => (
      <Tag className={tradeAction(action).className}>{tradeAction(action).label}</Tag>
    ),
  },
  {
    title: '价格',
    dataIndex: 'price',
    key: 'price',
    align: 'right' as const,
    render: (v: number) => formatNumber(v),
  },
  {
    title: '数量 / 股',
    dataIndex: 'quantity',
    key: 'quantity',
    align: 'right' as const,
    render: (v: number) => formatNumber(v, 0),
  },
  {
    title: '金额',
    dataIndex: 'amount',
    key: 'amount',
    align: 'right' as const,
    render: (v: number) => formatNumber(v),
  },
]

function SignalStatsCard({ stats }: { stats: SignalStats }) {
  return (
    <Card title="信号历史表现" size="small">
      <Descriptions column={1} size="small" bordered>
        <Descriptions.Item label="买入信号">
          {stats.total_buy_signals}
        </Descriptions.Item>
        <Descriptions.Item label="卖出信号">
          {stats.total_sell_signals}
        </Descriptions.Item>
        <Descriptions.Item label="已完成交易">
          <span style={{ fontWeight: 600 }}>{stats.total_trades}</span>
        </Descriptions.Item>
        <Descriptions.Item label="胜率">
          {formatPercent(stats.win_rate)}
        </Descriptions.Item>
        <Descriptions.Item label="平均持仓天数">
          {stats.avg_holding_days}天
        </Descriptions.Item>
        <Descriptions.Item label="平均每笔收益">
          <FinancialValue value={stats.avg_return_per_trade} />
        </Descriptions.Item>
        <Descriptions.Item label="盈亏比">
          {formatNumber(stats.profit_ratio)}
        </Descriptions.Item>
        <Descriptions.Item label="最大单笔盈利">
          <FinancialValue value={stats.max_win} />
        </Descriptions.Item>
        <Descriptions.Item label="最大单笔亏损">
          <FinancialValue value={stats.max_loss} />
        </Descriptions.Item>
        <Descriptions.Item label="最大连赢">
          {stats.consecutive_wins}次
        </Descriptions.Item>
        <Descriptions.Item label="最大连亏">
          {stats.consecutive_losses}次
        </Descriptions.Item>
      </Descriptions>
    </Card>
  )
}

function MetricsCard({ result }: { result: StrategyBacktestResponse }) {
  const { metrics } = result
  const metadata = result.execution_metadata
  const lastValue = result.portfolio_values?.[result.portfolio_values.length - 1]
  return (
    <Card title="绩效指标" styles={{ body: { padding: 'var(--space-sm)' } }}>
      <Descriptions column={1} size="small" bordered>
        <Descriptions.Item label="历史记录">
          <Link to={`/history?result=${result.result_id}`}>
            #{result.result_id} · 查看历史
          </Link>
        </Descriptions.Item>
        <Descriptions.Item label="策略">{result.strategy_name}</Descriptions.Item>
        <Descriptions.Item label="股票">{result.stock_code}</Descriptions.Item>
        <Descriptions.Item label="行情口径">
          {metadata?.data_provenance?.adjustment === 'raw'
            ? '原始价格'
            : '旧行情，复权口径未知'}
        </Descriptions.Item>
        <Descriptions.Item label="收益口径">
          {metadata?.corporate_action_mode === 'verified'
            ? `含分红送转，分红税率假设 ${((metadata.dividend_tax_rate ?? 0) * 100).toFixed(1)}%`
            : '价格收益，未计分红送转'}
        </Descriptions.Item>
        <Descriptions.Item label="交易费用">
          {formatNumber(
            result.trades.every((trade) => isFiniteNumber(trade.fees))
              ? result.trades.reduce(
                  (total, trade) => total + (trade.fees as number),
                  0,
                )
              : null,
          )}{' '}
          元
        </Descriptions.Item>
        <Descriptions.Item label="期末应收分红">
          {formatNumber(lastValue?.receivable)} 元
        </Descriptions.Item>
        <Descriptions.Item label="回测区间">
          {result.start_date} 至 {result.end_date}
        </Descriptions.Item>
        <Descriptions.Item label="初始资金">
          {formatNumber(result.initial_capital)} 元
        </Descriptions.Item>
        <Descriptions.Item label="最终资金">
          {formatNumber(result.final_capital)} 元
        </Descriptions.Item>
        <Descriptions.Item label="总收益率">
          <FinancialValue value={metrics.total_return} />
        </Descriptions.Item>
        <Descriptions.Item label="年化收益率">
          <FinancialValue value={metrics.annual_return} />
        </Descriptions.Item>
        <Descriptions.Item label="夏普比率">
          {formatNumber(metrics.sharpe_ratio, 4)}
        </Descriptions.Item>
        <Descriptions.Item label="最大回撤">
          {formatPercent(metrics.max_drawdown)}
        </Descriptions.Item>
        <Descriptions.Item label="胜率">
          {formatPercent(metrics.win_rate)}
        </Descriptions.Item>
        <Descriptions.Item label="交易次数">{metrics.total_trades}</Descriptions.Item>
      </Descriptions>
    </Card>
  )
}

export function StrategyResults({
  klineData,
  signals,
  signalStats,
  backtestResult,
  loading,
  chartRef,
  chartOption,
  portfolioChartOption,
  children,
}: StrategyResultsProps) {
  const showChart =
    klineData.length > 0 || signals.length > 0 || Boolean(backtestResult)
  const isLoading = loading.signals || loading.backtest
  const [resetKey, setResetKey] = useState(0)

  return (
    <div className="strategy-results-panel" style={{ minWidth: 0 }}>
      <Card
        title="研究结果"
        extra={
          <div className="research-chart-actions">
            <QueryStatus fetching={isLoading && showChart} label="研究运行中" />
            <ChartResetButton onReset={() => setResetKey((value) => value + 1)} />
          </div>
        }
        styles={{ body: { padding: 'var(--space-md)' } }}
      >
        <Tabs
          items={[
            {
              key: 'market',
              label: '行情与信号',
              children: (
                <div
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 'var(--space-lg)',
                  }}
                >
                  <section className="strategy-chart-preview" aria-label="信号预览">
                    {klineData.length > 0 && (
                      <p className="research-data-context">
                        {formatDate(klineData[0].date)} —{' '}
                        {formatDate(klineData[klineData.length - 1].date)} · 价格 / 元 ·
                        成交量 / 股 · 买入红、卖出绿
                      </p>
                    )}
                    {isLoading && !showChart ? (
                      <div className="loading-container">
                        <Spin
                          indicator={<LoadingOutlined style={{ fontSize: 32 }} spin />}
                        />
                      </div>
                    ) : showChart ? (
                      <LazyECharts
                        resetKey={resetKey}
                        ref={chartRef}
                        option={chartOption}
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
                  </section>
                  {signalStats && <SignalStatsCard stats={signalStats} />}
                </div>
              ),
            },
            {
              key: 'equity',
              label: '资金曲线',
              disabled: !backtestResult,
              children: backtestResult?.portfolio_values?.length ? (
                <LazyECharts
                  resetKey={resetKey}
                  option={portfolioChartOption}
                  style={{ height: 420 }}
                  opts={{ renderer: 'canvas' }}
                />
              ) : (
                <Empty
                  description="当前回测没有保存资金曲线"
                  image={Empty.PRESENTED_IMAGE_SIMPLE}
                />
              ),
            },
            {
              key: 'metrics',
              label: '绩效指标',
              disabled: !backtestResult,
              children: backtestResult ? <MetricsCard result={backtestResult} /> : null,
            },
            {
              key: 'trades',
              label: '交易记录',
              disabled: !backtestResult,
              children: backtestResult ? (
                <Table
                  dataSource={backtestResult.trades}
                  columns={tradeColumns}
                  rowKey={(record) => `${record.date}-${record.action}-${record.price}`}
                  size="small"
                  pagination={{ pageSize: 10 }}
                  scroll={{ y: 320 }}
                />
              ) : null,
            },
          ]}
        />
      </Card>
      {children}
    </div>
  )
}
