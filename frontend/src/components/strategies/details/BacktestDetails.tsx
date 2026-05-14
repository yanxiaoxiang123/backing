import { Card, Descriptions, Table, Tabs, Tag } from 'antd'
import { BarChartOutlined } from '@ant-design/icons'
import ReactECharts from 'echarts-for-react'
import type { SignalStats, StrategyBacktestResponse, OptimizeResponse, CompareResponse } from '../../../types'
import { getCompareChartOption } from '../../../utils/chart'
import { COMPARE_COLORS } from '../../../constants/strategy'

interface BacktestDetailsProps {
  signalStats: SignalStats | null
  backtestResult: StrategyBacktestResponse | null
  optimizeResult: OptimizeResponse | null
  compareResult: CompareResponse | null
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
    )
  },
  { title: '价格', dataIndex: 'price', key: 'price', render: (v: number) => v.toFixed(2) },
  { title: '数量', dataIndex: 'quantity', key: 'quantity' },
  { title: '金额', dataIndex: 'amount', key: 'amount', render: (v: number) => v.toFixed(2) }
]

const optimizeColumns = [
  {
    title: '参数',
    dataIndex: 'params',
    key: 'params',
    render: (params: Record<string, number>) => (
      <span>
        {Object.entries(params).map(([k, v]) => `${k}: ${v}`).join(', ')}
      </span>
    )
  },
  { title: '夏普比率', dataIndex: 'score', key: 'score', render: (v: number) => v.toFixed(4) },
  {
    title: '收益率',
    dataIndex: 'metrics',
    key: 'total_return',
    render: (m: Record<string, number>) => `${m.total_return.toFixed(2)}%`
  },
  {
    title: '胜率',
    dataIndex: 'metrics',
    key: 'win_rate',
    render: (m: Record<string, number>) => `${m.win_rate.toFixed(2)}%`
  }
]

const compareColumns = [
  {
    title: '策略',
    dataIndex: 'strategy_name',
    key: 'strategy_name',
    render: (name: string, _: unknown, index: number) => (
      <span style={{ color: COMPARE_COLORS[index % COMPARE_COLORS.length], fontWeight: 600 }}>
        {name}
      </span>
    ),
  },
  {
    title: '总收益率',
    dataIndex: ['metrics', 'total_return'],
    key: 'total_return',
    sorter: (a: { metrics: { total_return: number } }, b: { metrics: { total_return: number } }) => a.metrics.total_return - b.metrics.total_return,
    render: (v: number) => <span style={{ color: v >= 0 ? '#34c759' : '#ff3b30', fontWeight: 600 }}>{v.toFixed(2)}%</span>,
  },
  {
    title: '夏普比率',
    dataIndex: ['metrics', 'sharpe_ratio'],
    key: 'sharpe_ratio',
    sorter: (a: { metrics: { sharpe_ratio: number } }, b: { metrics: { sharpe_ratio: number } }) => a.metrics.sharpe_ratio - b.metrics.sharpe_ratio,
    render: (v: number) => v.toFixed(4),
  },
  {
    title: '最大回撤',
    dataIndex: ['metrics', 'max_drawdown'],
    key: 'max_drawdown',
    sorter: (a: { metrics: { max_drawdown: number } }, b: { metrics: { max_drawdown: number } }) => a.metrics.max_drawdown - b.metrics.max_drawdown,
    render: (v: number) => <span style={{ color: '#ff3b30' }}>{v.toFixed(2)}%</span>,
  },
  {
    title: '胜率',
    dataIndex: ['metrics', 'win_rate'],
    key: 'win_rate',
    sorter: (a: { metrics: { win_rate: number } }, b: { metrics: { win_rate: number } }) => a.metrics.win_rate - b.metrics.win_rate,
    render: (v: number) => `${v.toFixed(2)}%`,
  },
  {
    title: '交易次数',
    dataIndex: ['metrics', 'total_trades'],
    key: 'total_trades',
    sorter: (a: { metrics: { total_trades: number } }, b: { metrics: { total_trades: number } }) => a.metrics.total_trades - b.metrics.total_trades,
  },
]

export function BacktestDetails({
  backtestResult,
  optimizeResult,
  compareResult
}: BacktestDetailsProps) {
  if (!backtestResult && !optimizeResult && !compareResult) {
    return null
  }

  return (
    <>
      {/* Backtest Results */}
      {backtestResult && (
        <Card title="回测结果">
          <Tabs
            items={[
              {
                key: 'metrics',
                label: '绩效指标',
                children: (
                  <Descriptions column={2} size="small" bordered>
                    <Descriptions.Item label="策略">{backtestResult.strategy_name}</Descriptions.Item>
                    <Descriptions.Item label="股票">{backtestResult.stock_code}</Descriptions.Item>
                    <Descriptions.Item label="初始资金">
                      {backtestResult.initial_capital.toLocaleString()}
                    </Descriptions.Item>
                    <Descriptions.Item label="最终资金">
                      {backtestResult.final_capital.toLocaleString()}
                    </Descriptions.Item>
                    <Descriptions.Item label="总收益率">
                      <span style={{ color: backtestResult.metrics.total_return >= 0 ? '#34c759' : '#ff3b30' }}>
                        {backtestResult.metrics.total_return.toFixed(2)}%
                      </span>
                    </Descriptions.Item>
                    <Descriptions.Item label="年化收益率">
                      <span style={{ color: backtestResult.metrics.annual_return >= 0 ? '#34c759' : '#ff3b30' }}>
                        {backtestResult.metrics.annual_return.toFixed(2)}%
                      </span>
                    </Descriptions.Item>
                    <Descriptions.Item label="夏普比率">{backtestResult.metrics.sharpe_ratio.toFixed(4)}</Descriptions.Item>
                    <Descriptions.Item label="最大回撤">
                      {backtestResult.metrics.max_drawdown.toFixed(2)}%
                    </Descriptions.Item>
                    <Descriptions.Item label="胜率">{backtestResult.metrics.win_rate.toFixed(2)}%</Descriptions.Item>
                    <Descriptions.Item label="交易次数">{backtestResult.metrics.total_trades}</Descriptions.Item>
                  </Descriptions>
                )
              },
              {
                key: 'trades',
                label: '交易记录',
                children: (
                  <Table
                    dataSource={backtestResult.trades}
                    columns={tradeColumns}
                    rowKey={(record, index) => `${record.date}-${index}`}
                    size="small"
                    pagination={{ pageSize: 10 }}
                    scroll={{ y: 300 }}
                  />
                )
              }
            ]}
          />
        </Card>
      )}

      {/* Optimize Results */}
      {optimizeResult && (
        <Card title="优化结果">
          <div style={{ marginBottom: 'var(--space-md)' }}>
            <Descriptions column={2} size="small" bordered>
              <Descriptions.Item label="最优参数" span={2}>
                {Object.entries(optimizeResult.best_params).map(([k, v]) => `${k}: ${v}`).join(', ')}
              </Descriptions.Item>
              <Descriptions.Item label="最优夏普比率">{optimizeResult.best_score.toFixed(4)}</Descriptions.Item>
              <Descriptions.Item label="总收益">
                {optimizeResult.best_metrics.total_return.toFixed(2)}%
              </Descriptions.Item>
            </Descriptions>
          </div>
          <Table
            dataSource={optimizeResult.all_results}
            columns={optimizeColumns}
            rowKey={(record, index) => JSON.stringify(record.params) + index}
            size="small"
            pagination={{ pageSize: 20, showSizeChanger: true, showTotal: (t: number) => `共 ${t} 条` }}
            scroll={{ y: 300 }}
            title={() => `优化结果 (共${optimizeResult.total_combinations}种组合)`}
          />
        </Card>
      )}

      {/* Strategy Comparison Results */}
      {compareResult && (
        <Card
          title={
            <><BarChartOutlined style={{ marginRight: 8 }} />策略对比 ({compareResult.total_strategies} 个策略)</>
          }
        >
          {compareResult.failed_count > 0 && (
            <div style={{ marginBottom: 'var(--space-md)', padding: 'var(--space-sm)', background: '#fff2f0', borderRadius: 'var(--radius-sm)', color: '#ff4d4f', fontSize: 'var(--font-size-xs)' }}>
              {compareResult.failed_count} 个策略执行失败
            </div>
          )}
          <Tabs
            items={[
              {
                key: 'table',
                label: '指标对比',
                children: (
                  <Table
                    dataSource={compareResult.results.filter(r => !r.error)}
                    columns={compareColumns}
                    rowKey="strategy_name"
                    size="small"
                    pagination={false}
                    scroll={{ y: 300 }}
                  />
                ),
              },
              {
                key: 'chart',
                label: '资金曲线叠加',
                children: (
                  <ReactECharts
                    option={getCompareChartOption(compareResult)}
                    style={{ height: 400 }}
                    opts={{ renderer: 'canvas' }}
                  />
                ),
              },
            ]}
          />
        </Card>
      )}
    </>
  )
}