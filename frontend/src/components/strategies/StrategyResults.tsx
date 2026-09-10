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
      <Tag color={action === 'buy' ? 'green' : 'red'}>
        {action === 'buy' ? '买入' : '卖出'}
      </Tag>
    ),
  },
  {
    title: '价格',
    dataIndex: 'price',
    key: 'price',
    render: (v: number) => v.toFixed(2),
  },
  { title: '数量', dataIndex: 'quantity', key: 'quantity' },
  {
    title: '金额',
    dataIndex: 'amount',
    key: 'amount',
    render: (v: number) => v.toFixed(2),
  },
]

function SignalStatsCard({ stats }: { stats: SignalStats }) {
  return (
    <Card title="信号历史表现" size="small">
      <Descriptions column={2} size="small" bordered>
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
          <span
            style={{
              color: stats.win_rate >= 50 ? '#34c759' : '#ff3b30',
              fontWeight: 600,
            }}
          >
            {stats.win_rate}%
          </span>
        </Descriptions.Item>
        <Descriptions.Item label="平均持仓天数">
          {stats.avg_holding_days}天
        </Descriptions.Item>
        <Descriptions.Item label="平均每笔收益">
          <span
            style={{ color: stats.avg_return_per_trade >= 0 ? '#34c759' : '#ff3b30' }}
          >
            {stats.avg_return_per_trade >= 0 ? '+' : ''}
            {stats.avg_return_per_trade}%
          </span>
        </Descriptions.Item>
        <Descriptions.Item label="盈亏比">
          {stats.profit_ratio > 0 ? stats.profit_ratio.toFixed(2) : '-'}
        </Descriptions.Item>
        <Descriptions.Item label="最大单笔盈利">
          <span style={{ color: '#34c759' }}>+{stats.max_win}%</span>
        </Descriptions.Item>
        <Descriptions.Item label="最大单笔亏损">
          <span style={{ color: '#ff3b30' }}>{stats.max_loss}%</span>
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
  return (
    <Card title="绩效指标">
      <Descriptions column={2} size="small" bordered>
        <Descriptions.Item label="历史记录">
          <Link to="/history">#{result.result_id} · 查看历史</Link>
        </Descriptions.Item>
        <Descriptions.Item label="策略">{result.strategy_name}</Descriptions.Item>
        <Descriptions.Item label="股票">{result.stock_code}</Descriptions.Item>
        <Descriptions.Item label="回测区间">
          {result.start_date} 至 {result.end_date}
        </Descriptions.Item>
        <Descriptions.Item label="初始资金">
          {result.initial_capital.toLocaleString()}
        </Descriptions.Item>
        <Descriptions.Item label="最终资金">
          {result.final_capital.toLocaleString()}
        </Descriptions.Item>
        <Descriptions.Item label="总收益率">
          <span style={{ color: metrics.total_return >= 0 ? '#34c759' : '#ff3b30' }}>
            {metrics.total_return.toFixed(2)}%
          </span>
        </Descriptions.Item>
        <Descriptions.Item label="年化收益率">
          <span style={{ color: metrics.annual_return >= 0 ? '#34c759' : '#ff3b30' }}>
            {metrics.annual_return.toFixed(2)}%
          </span>
        </Descriptions.Item>
        <Descriptions.Item label="夏普比率">
          {metrics.sharpe_ratio.toFixed(4)}
        </Descriptions.Item>
        <Descriptions.Item label="最大回撤">
          {metrics.max_drawdown.toFixed(2)}%
        </Descriptions.Item>
        <Descriptions.Item label="胜率">
          {metrics.win_rate.toFixed(2)}%
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

  return (
    <div className="strategy-results-panel" style={{ minWidth: 0 }}>
      <Card title="研究结果" styles={{ body: { padding: 'var(--space-md)' } }}>
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
                  <Card
                    title="信号预览"
                    styles={{ body: { padding: 0 } }}
                    style={{ minHeight: 400 }}
                  >
                    {isLoading ? (
                      <div className="loading-container">
                        <Spin
                          indicator={<LoadingOutlined style={{ fontSize: 32 }} spin />}
                        />
                      </div>
                    ) : showChart ? (
                      <LazyECharts
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
                  </Card>
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
