import { Button, Card, Descriptions, Table, Tabs } from 'antd'
import { BarChartOutlined } from '@ant-design/icons'
import ReactECharts from 'echarts-for-react'
import type {
  OptimizeResponse,
  CompareResponse,
  CompareStrategyResult,
} from '../../../types'
import { getCompareChartOption } from '../../../utils/chart'
import { COMPARE_COLORS } from '../../../constants/strategy'

interface BacktestDetailsProps {
  optimizeResult: OptimizeResponse | null
  compareResult: CompareResponse | null
  onRunBestBacktest?: () => void
  onSelectStrategy?: (strategyName: string) => void
}

const optimizeColumns = [
  {
    title: '参数',
    dataIndex: 'params',
    key: 'params',
    render: (params: Record<string, number>) => (
      <span>
        {Object.entries(params)
          .map(([k, v]) => `${k}: ${v}`)
          .join(', ')}
      </span>
    ),
  },
  {
    title: '夏普比率',
    dataIndex: 'score',
    key: 'score',
    render: (v: number) => v.toFixed(4),
  },
  {
    title: '收益率',
    dataIndex: 'metrics',
    key: 'total_return',
    render: (m: Record<string, number>) => `${m.total_return.toFixed(2)}%`,
  },
  {
    title: '胜率',
    dataIndex: 'metrics',
    key: 'win_rate',
    render: (m: Record<string, number>) => `${m.win_rate.toFixed(2)}%`,
  },
]

function getCompareColumns(onSelectStrategy?: (strategyName: string) => void): any[] {
  const columns: any[] = [
    {
      title: '策略',
      dataIndex: 'strategy_name',
      key: 'strategy_name',
      render: (name: string, _: unknown, index: number) => (
        <span
          style={{
            color: COMPARE_COLORS[index % COMPARE_COLORS.length],
            fontWeight: 600,
          }}
        >
          {name}
        </span>
      ),
    },
    {
      title: '总收益率',
      dataIndex: ['metrics', 'total_return'],
      key: 'total_return',
      sorter: (
        a: { metrics: { total_return: number } },
        b: { metrics: { total_return: number } },
      ) => a.metrics.total_return - b.metrics.total_return,
      render: (v: number) => (
        <span style={{ color: v >= 0 ? '#34c759' : '#ff3b30', fontWeight: 600 }}>
          {v.toFixed(2)}%
        </span>
      ),
    },
    {
      title: '夏普比率',
      dataIndex: ['metrics', 'sharpe_ratio'],
      key: 'sharpe_ratio',
      sorter: (
        a: { metrics: { sharpe_ratio: number } },
        b: { metrics: { sharpe_ratio: number } },
      ) => a.metrics.sharpe_ratio - b.metrics.sharpe_ratio,
      render: (v: number) => v.toFixed(4),
    },
    {
      title: '最大回撤',
      dataIndex: ['metrics', 'max_drawdown'],
      key: 'max_drawdown',
      sorter: (
        a: { metrics: { max_drawdown: number } },
        b: { metrics: { max_drawdown: number } },
      ) => a.metrics.max_drawdown - b.metrics.max_drawdown,
      render: (v: number) => <span style={{ color: '#ff3b30' }}>{v.toFixed(2)}%</span>,
    },
    {
      title: '胜率',
      dataIndex: ['metrics', 'win_rate'],
      key: 'win_rate',
      sorter: (
        a: { metrics: { win_rate: number } },
        b: { metrics: { win_rate: number } },
      ) => a.metrics.win_rate - b.metrics.win_rate,
      render: (v: number) => `${v.toFixed(2)}%`,
    },
    {
      title: '交易次数',
      dataIndex: ['metrics', 'total_trades'],
      key: 'total_trades',
      sorter: (
        a: { metrics: { total_trades: number } },
        b: { metrics: { total_trades: number } },
      ) => a.metrics.total_trades - b.metrics.total_trades,
    },
  ]
  if (onSelectStrategy) {
    columns.push({
      title: '操作',
      key: 'select',
      render: (_: unknown, record: CompareStrategyResult) => (
        <Button size="small" onClick={() => onSelectStrategy(record.strategy_name)}>
          选择策略
        </Button>
      ),
    })
  }
  return columns
}

export function BacktestDetails({
  optimizeResult,
  compareResult,
  onRunBestBacktest,
  onSelectStrategy,
}: BacktestDetailsProps) {
  if (!optimizeResult && !compareResult) {
    return null
  }

  return (
    <>
      {/* Optimize Results */}
      {optimizeResult && (
        <Card title="优化结果">
          <div style={{ marginBottom: 'var(--space-md)' }}>
            <Descriptions column={2} size="small" bordered>
              <Descriptions.Item label="最优参数" span={2}>
                {Object.entries(optimizeResult.best_params)
                  .map(([k, v]) => `${k}: ${v}`)
                  .join(', ')}
              </Descriptions.Item>
              <Descriptions.Item label="最优夏普比率">
                {optimizeResult.best_score.toFixed(4)}
              </Descriptions.Item>
              <Descriptions.Item label="总收益">
                {optimizeResult.best_metrics.total_return.toFixed(2)}%
              </Descriptions.Item>
            </Descriptions>
            {onRunBestBacktest && (
              <Button
                type="primary"
                style={{ marginTop: 'var(--space-md)' }}
                onClick={onRunBestBacktest}
              >
                用最优参数回测并保存
              </Button>
            )}
          </div>
          <Table
            dataSource={optimizeResult.all_results}
            columns={optimizeColumns}
            rowKey={(record, index) => JSON.stringify(record.params) + index}
            size="small"
            pagination={{
              pageSize: 20,
              showSizeChanger: true,
              showTotal: (t: number) => `共 ${t} 条`,
            }}
            scroll={{ y: 300 }}
            title={() => `优化结果 (共${optimizeResult.total_combinations}种组合)`}
          />
        </Card>
      )}

      {/* Strategy Comparison Results */}
      {compareResult && (
        <Card
          title={
            <>
              <BarChartOutlined style={{ marginRight: 8 }} />
              策略对比 ({compareResult.total_strategies} 个策略)
            </>
          }
        >
          {compareResult.failed_count > 0 && (
            <div
              style={{
                marginBottom: 'var(--space-md)',
                padding: 'var(--space-sm)',
                background: '#fff2f0',
                borderRadius: 'var(--radius-sm)',
                color: '#ff4d4f',
                fontSize: 'var(--font-size-xs)',
              }}
            >
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
                    dataSource={compareResult.results.filter((r) => !r.error)}
                    columns={getCompareColumns(onSelectStrategy)}
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
