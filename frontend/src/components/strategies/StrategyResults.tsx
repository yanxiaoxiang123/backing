import { Card, Spin, Empty, Descriptions } from 'antd'
import { LoadingOutlined } from '@ant-design/icons'
import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'
import type { SignalDataPoint, SignalStats, StrategyBacktestResponse } from '../../types'
import { KlineData } from '../../utils/chart'

interface StrategyResultsProps {
  klineData: KlineData[]
  signals: SignalDataPoint[]
  signalStats: SignalStats | null
  backtestResult: StrategyBacktestResponse | null
  loading: { signals: boolean; backtest: boolean }
  chartRef: React.RefObject<ReactECharts>
  chartOption: EChartsOption
  children?: React.ReactNode
}

export function StrategyResults({
  klineData,
  signals,
  signalStats,
  backtestResult,
  loading,
  chartRef,
  chartOption,
  children
}: StrategyResultsProps) {
  const showChart = klineData.length > 0 || signals.length > 0 || backtestResult
  const isLoading = loading.signals || loading.backtest

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-lg)' }}>
      {/* Chart */}
      <Card
        title="信号预览"
        bodyStyle={{ padding: 0 }}
        style={{ minHeight: 400 }}
      >
        {isLoading ? (
          <div className="loading-container">
            <Spin indicator={<LoadingOutlined style={{ fontSize: 32 }} spin />} />
          </div>
        ) : showChart ? (
          <ReactECharts
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

      {/* Signal Stats */}
      {signalStats && (
        <Card title="信号历史表现" size="small">
          <Descriptions column={2} size="small" bordered>
            <Descriptions.Item label="买入信号">{signalStats.total_buy_signals}</Descriptions.Item>
            <Descriptions.Item label="卖出信号">{signalStats.total_sell_signals}</Descriptions.Item>
            <Descriptions.Item label="已完成交易">
              <span style={{ fontWeight: 600 }}>{signalStats.total_trades}</span>
            </Descriptions.Item>
            <Descriptions.Item label="胜率">
              <span style={{ color: signalStats.win_rate >= 50 ? '#34c759' : '#ff3b30', fontWeight: 600 }}>
                {signalStats.win_rate}%
              </span>
            </Descriptions.Item>
            <Descriptions.Item label="平均持仓天数">{signalStats.avg_holding_days}天</Descriptions.Item>
            <Descriptions.Item label="平均每笔收益">
              <span style={{ color: signalStats.avg_return_per_trade >= 0 ? '#34c759' : '#ff3b30' }}>
                {signalStats.avg_return_per_trade >= 0 ? '+' : ''}{signalStats.avg_return_per_trade}%
              </span>
            </Descriptions.Item>
            <Descriptions.Item label="盈亏比">{signalStats.profit_ratio > 0 ? signalStats.profit_ratio.toFixed(2) : '-'}</Descriptions.Item>
            <Descriptions.Item label="最大单笔盈利">
              <span style={{ color: '#34c759' }}>+{signalStats.max_win}%</span>
            </Descriptions.Item>
            <Descriptions.Item label="最大单笔亏损">
              <span style={{ color: '#ff3b30' }}>{signalStats.max_loss}%</span>
            </Descriptions.Item>
            <Descriptions.Item label="最大连赢">{signalStats.consecutive_wins}次</Descriptions.Item>
            <Descriptions.Item label="最大连亏">{signalStats.consecutive_losses}次</Descriptions.Item>
          </Descriptions>
        </Card>
      )}

      {/* Children (BacktestDetails) */}
      {children}
    </div>
  )
}