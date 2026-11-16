import { Button, Card, Descriptions, Table, Tabs } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { BarChartOutlined } from '@ant-design/icons'
import { LazyECharts } from '../../charts/LazyECharts'
import type {
  OptimizeResponse,
  CompareResponse,
  CompareStrategyResult,
} from '../../../types'
import { getCompareChartOption } from '../../../utils/chart'
import { COMPARE_COLORS } from '../../../constants/strategy'
import { FinancialValue } from '../../research/FinancialValue'
import { formatNumber, formatPercent } from '../../../utils/dataFormat'
import { ParameterSnapshot } from '../../research/ParameterSnapshot'

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
      <ParameterSnapshot parameters={params} />
    ),
  },
  {
    title: '夏普比率',
    dataIndex: 'score',
    key: 'score',
    render: (v: number) => formatNumber(v, 4),
  },
  {
    title: '收益率',
    dataIndex: 'metrics',
    key: 'total_return',
    render: (m: Record<string, number>) => <FinancialValue value={m.total_return} />,
  },
  {
    title: '胜率',
    dataIndex: 'metrics',
    key: 'win_rate',
    render: (m: Record<string, number>) => formatPercent(m.win_rate),
  },
]

function getCompareColumns(
  onSelectStrategy?: (strategyName: string) => void,
): ColumnsType<CompareStrategyResult> {
  const columns: ColumnsType<CompareStrategyResult> = [
    {
      title: '策略',
      dataIndex: 'strategy_name',
      key: 'strategy_name',
      render: (name: string, _: unknown, index?: number) => (
        <span
          style={{
            color: COMPARE_COLORS[(index ?? 0) % COMPARE_COLORS.length],
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
      render: (v: number) => <FinancialValue value={v} />,
    },
    {
      title: '夏普比率',
      dataIndex: ['metrics', 'sharpe_ratio'],
      key: 'sharpe_ratio',
      sorter: (
        a: { metrics: { sharpe_ratio: number } },
        b: { metrics: { sharpe_ratio: number } },
      ) => a.metrics.sharpe_ratio - b.metrics.sharpe_ratio,
      render: (v: number) => formatNumber(v, 4),
    },
    {
      title: '最大回撤',
      dataIndex: ['metrics', 'max_drawdown'],
      key: 'max_drawdown',
      sorter: (
        a: { metrics: { max_drawdown: number } },
        b: { metrics: { max_drawdown: number } },
      ) => a.metrics.max_drawdown - b.metrics.max_drawdown,
      render: (v: number) => formatPercent(v),
    },
    {
      title: '胜率',
      dataIndex: ['metrics', 'win_rate'],
      key: 'win_rate',
      sorter: (
        a: { metrics: { win_rate: number } },
        b: { metrics: { win_rate: number } },
      ) => a.metrics.win_rate - b.metrics.win_rate,
      render: (v: number) => formatPercent(v),
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
                <ParameterSnapshot parameters={optimizeResult.best_params} />
              </Descriptions.Item>
              <Descriptions.Item label="最优夏普比率">
                {formatNumber(optimizeResult.best_score, 4)}
              </Descriptions.Item>
              <Descriptions.Item label="总收益">
                <FinancialValue value={optimizeResult.best_metrics.total_return} />
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
            rowKey={(record) => JSON.stringify(record.params)}
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
                  <LazyECharts
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

export default BacktestDetails
