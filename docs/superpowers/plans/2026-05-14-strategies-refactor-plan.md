# Strategies.tsx 重构实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 1084 行的 Strategies.tsx 拆分为 5 个职责清晰的子组件

**Architecture:** 采用属性穿透 + 回调函数模式，Strategies.tsx 作为容器管理所有共享 state，子组件各司其职

**Tech Stack:** React + TypeScript + Ant Design + ECharts

---

## 文件结构

```
frontend/src/
├── pages/
│   └── Strategies.tsx          # 主容器 (~100行)
├── components/strategies/
│   ├── StrategyList.tsx        # 策略列表 (~80行)
│   ├── StrategyConfig.tsx      # 参数配置+回测设置 (~200行)
│   └── StrategyResults.tsx     # 结果容器 (~100行)
├── components/strategies/details/
│   └── BacktestDetails.tsx     # 回测/优化/对比结果 (~250行)
├── constants/
│   └── strategy.ts             # 策略元数据常量 (~40行)
└── utils/
    └── chart.ts                # 图表工具函数 (~120行)
```

---

## Task 1: 提取策略常量

**Files:**
- Create: `frontend/src/constants/strategy.ts`

- [ ] **Step 1: 创建常量文件**

```typescript
// frontend/src/constants/strategy.ts

export const STRATEGY_METADATA: Record<string, { name: string; description: string; color: string }> = {
  'MA Cross': {
    name: 'MA Cross',
    description: 'Moving Average Crossover strategy using short and long period MA signals',
    color: '#0071e3'
  },
  'Mean Reversion': {
    name: 'Mean Reversion',
    description: 'Buy when price deviates below moving average, sell when above',
    color: '#34c759'
  },
  'Momentum': {
    name: 'Momentum',
    description: 'Follow strong price trends using momentum indicators',
    color: '#ff9500'
  },
  'Breakout': {
    name: 'Breakout',
    description: 'Trade price breakouts above resistance or below support levels',
    color: '#ff3b30'
  },
  'RSI Reversal': {
    name: 'RSI Reversal',
    description: 'Buy oversold (RSI<30) and sell overbought (RSI>70) conditions',
    color: '#af52de'
  },
  'MACD Cross': {
    name: 'MACD Cross',
    description: 'Trade MACD line crossovers with signal line',
    color: '#5856d6'
  },
  'Dual Thrust': {
    name: 'Dual Thrust',
    description: 'Classic breakout strategy using yesterday\'s price range',
    color: '#ff2d55'
  },
  'lstm_5d': {
    name: 'LSTM 5D',
    description: 'Predict 5-day close price and generate threshold-based signals',
    color: '#0a84ff'
  }
}

export const COMPARE_COLORS = ['#0071e3', '#34c759', '#ff9500', '#ff3b30', '#af52de', '#5856d6', '#ff2d55', '#0a84ff']
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/constants/strategy.ts
git commit -m "feat(frontend): extract strategy constants to separate file"
```

---

## Task 2: 提取图表工具函数

**Files:**
- Create: `frontend/src/utils/chart.ts`

- [ ] **Step 1: 创建图表工具文件**

新建 `frontend/src/utils/chart.ts`，包含：
- `getChartOption()` - K线图表配置（从 Strategies.tsx 第 303-473 行迁移）
- `getCompareChartOption()` - 策略对比图表配置（从 Strategies.tsx 第 586-665 行迁移）

关键迁移点：
- `getChartOption(klineData, signals, backtestResult)` - 接收参数而非依赖外部 state
- `getCompareChartOption(compareResult)` - 接收参数

```typescript
// frontend/src/utils/chart.ts
import type { EChartsOption } from 'echarts'
import type { SignalDataPoint, StrategyBacktestResponse, CompareResponse } from '../types'
import { COMPARE_COLORS } from '../constants/strategy'

interface KlineData {
  date: string
  open: number
  close: number
  high: number
  low: number
  volume: number
}

export function getChartOption(
  klineData: KlineData[],
  signals: SignalDataPoint[],
  backtestResult: StrategyBacktestResponse | null
): EChartsOption {
  if (klineData.length === 0 && signals.length === 0) {
    return {}
  }

  const dates = klineData.map(d => d.date)
  const ohlc = klineData.map(d => [d.open, d.close, d.low, d.high])

  // ... 完整的图表配置逻辑（从 Strategies.tsx 迁移）
  // 保持原有逻辑不变
}

export function getCompareChartOption(compareResult: CompareResponse): EChartsOption {
  if (!compareResult || compareResult.results.length === 0) {
    return {}
  }
  // ... 完整的对比图表配置逻辑（从 Strategies.tsx 迁移）
  // 保持原有逻辑不变
}
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/utils/chart.ts
git commit -m "feat(frontend): extract chart utilities to separate file"
```

---

## Task 3: 创建 StrategyList.tsx

**Files:**
- Create: `frontend/src/components/strategies/StrategyList.tsx`

- [ ] **Step 1: 创建组件**

```typescript
// frontend/src/components/strategies/StrategyList.tsx
import { Card, Spin, Empty } from 'antd'
import { LineChartOutlined } from '@ant-design/icons'
import type { StrategyInfo } from '../../types'
import { STRATEGY_METADATA } from '../../constants/strategy'

interface StrategyListProps {
  strategies: StrategyInfo[]
  selectedStrategy: string | null
  loading: boolean
  onSelect: (name: string) => void
}

export function StrategyList({ strategies, selectedStrategy, loading, onSelect }: StrategyListProps) {
  return (
    <Card
      title={<><LineChartOutlined style={{ marginRight: 8 }} />策略列表</>}
      loading={loading}
      style={{ position: 'sticky', top: 80 }}
      bodyStyle={{ padding: 'var(--space-sm)', maxHeight: 'calc(100vh - 180px)', overflowY: 'auto' }}
    >
      {strategies.map(strategy => {
        const meta = STRATEGY_METADATA[strategy.name] || { name: strategy.name, description: strategy.description, color: '#86868b' }
        const isSelected = selectedStrategy === strategy.name

        return (
          <div
            key={strategy.name}
            onClick={() => onSelect(strategy.name)}
            style={{
              padding: 'var(--space-md)',
              marginBottom: 'var(--space-sm)',
              borderRadius: 'var(--radius-md)',
              cursor: 'pointer',
              border: `2px solid ${isSelected ? meta.color : 'transparent'}`,
              background: isSelected ? `${meta.color}10` : 'var(--color-bg-secondary)',
              transition: 'all var(--transition-fast)'
            }}
          >
            <div style={{
              fontWeight: 600,
              fontSize: 'var(--font-size-sm)',
              color: isSelected ? meta.color : 'var(--color-text-primary)',
              marginBottom: 'var(--space-xs)'
            }}>
              {meta.name}
            </div>
            <div style={{
              fontSize: 'var(--font-size-xs)',
              color: 'var(--color-text-secondary)',
              lineHeight: 1.4
            }}>
              {meta.description}
            </div>
          </div>
        )
      })}
    </Card>
  )
}
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/components/strategies/StrategyList.tsx
git commit -m "feat(frontend): create StrategyList component"
```

---

## Task 4: 创建 StrategyConfig.tsx

**Files:**
- Create: `frontend/src/components/strategies/StrategyConfig.tsx`

- [ ] **Step 1: 创建参数渲染辅助函数**

在组件内定义 `renderParameterInputs` 函数（从 Strategies.tsx 第 475-539 行迁移）

- [ ] **Step 2: 创建完整组件**

```typescript
// frontend/src/components/strategies/StrategyConfig.tsx
import { Card, InputNumber, DatePicker, Button, Empty, Slider, Select } from 'antd'
import { LoadingOutlined, PlayCircleOutlined, ThunderboltOutlined, BarChartOutlined } from '@ant-design/icons'
import type { StrategyInfo } from '../../types'
import { usePersistedState } from '../../hooks/usePersistedState'
import StockSearch from '../StockSearch'
import dayjs from 'dayjs'

const { RangePicker } = DatePicker

interface StrategyConfigProps {
  strategies: StrategyInfo[]
  selectedStrategy: string | null
  stockCode: string | null
  dateRange: [string, string]
  initialCapital: number
  parameters: Record<string, number | string>
  loading: { signals: boolean; backtest: boolean; optimize: boolean }
  onStockCodeChange: (code: string) => void
  onDateRangeChange: (range: [string, string]) => void
  onCapitalChange: (capital: number) => void
  onParameterChange: (params: Record<string, number | string>) => void
  onGenerateSignals: () => void
  onRunBacktest: () => void
  onOptimize: () => void
  onCompare: () => void
}

function renderParameterInputs(
  strategy: StrategyInfo,
  parameters: Record<string, number | string>,
  onChange: (params: Record<string, number | string>) => void
) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
      {Object.entries(strategy.parameters).map(([key, config]) => (
        <div key={key}>
          <label style={{
            display: 'block',
            fontSize: 'var(--font-size-sm)',
            color: 'var(--color-text-secondary)',
            marginBottom: 'var(--space-xs)'
          }}>
            {key}
            {config.description && <span style={{ marginLeft: 8, fontWeight: 400 }}>({config.description})</span>}
          </label>
          {config.type === 'slider' && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-md)' }}>
              <Slider
                min={config.min}
                max={config.max}
                step={config.step}
                value={Number(parameters[key] ?? config.default)}
                onChange={(value) => onChange({ ...parameters, [key]: Number(value) })}
                style={{ flex: 1 }}
              />
              <InputNumber
                min={config.min}
                max={config.max}
                step={config.step}
                value={Number(parameters[key] ?? config.default)}
                onChange={(value) => onChange({ ...parameters, [key]: Number(value ?? 0) })}
                style={{ width: 80 }}
              />
            </div>
          )}
          {config.type === 'input' && (
            <InputNumber
              min={config.min}
              max={config.max}
              step={config.step}
              value={Number(parameters[key] ?? config.default)}
              onChange={(value) => onChange({ ...parameters, [key]: Number(value ?? 0) })}
              style={{ width: '100%' }}
            />
          )}
          {config.type === 'select' && config.options && (
            <Select
              value={parameters[key] ?? config.default}
              onChange={(value) => onChange({ ...parameters, [key]: value })}
              style={{ width: '100%' }}
              options={config.options.map(opt => ({
                value: opt.value,
                label: opt.label
              }))}
            />
          )}
        </div>
      ))}
    </div>
  )
}

export function StrategyConfig({
  strategies,
  selectedStrategy,
  stockCode,
  dateRange,
  initialCapital,
  parameters,
  loading,
  onStockCodeChange,
  onDateRangeChange,
  onCapitalChange,
  onParameterChange,
  onGenerateSignals,
  onRunBacktest,
  onOptimize,
  onCompare
}: StrategyConfigProps) {
  const selectedStrategyInfo = strategies.find(s => s.name === selectedStrategy)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-lg)' }}>
      {/* Strategy Parameters */}
      <Card
        title="策略参数"
        style={{ opacity: selectedStrategy ? 1 : 0.6 }}
      >
        {selectedStrategyInfo ? (
          renderParameterInputs(selectedStrategyInfo, parameters, onParameterChange)
        ) : (
          <Empty description="请选择策略" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        )}
      </Card>

      {/* Backtest Configuration */}
      <Card title="回测配置">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
          <div>
            <label style={{
              display: 'block',
              fontSize: 'var(--font-size-sm)',
              color: 'var(--color-text-secondary)',
              marginBottom: 'var(--space-xs)'
            }}>
              股票代码
            </label>
            <StockSearch
              value={stockCode ?? undefined}
              onChange={onStockCodeChange}
            />
          </div>

          <div>
            <label style={{
              display: 'block',
              fontSize: 'var(--font-size-sm)',
              color: 'var(--color-text-secondary)',
              marginBottom: 'var(--space-xs)'
            }}>
              回测区间
            </label>
            <RangePicker
              value={[dayjs(dateRange[0]), dayjs(dateRange[1])]}
              onChange={(dates) => {
                if (dates) {
                  onDateRangeChange([dates[0]!.format('YYYY-MM-DD'), dates[1]!.format('YYYY-MM-DD')])
                }
              }}
              style={{ width: '100%' }}
            />
          </div>

          <div>
            <label style={{
              display: 'block',
              fontSize: 'var(--font-size-sm)',
              color: 'var(--color-text-secondary)',
              marginBottom: 'var(--space-xs)'
            }}>
              初始资金
            </label>
            <InputNumber
              value={initialCapital}
              onChange={(value) => onCapitalChange(value ?? 100000)}
              min={10000}
              step={10000}
              style={{ width: '100%' }}
              formatter={(value) => `${value}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}
              parser={(value) => Number(value!.replace(/\$\s?|(,*)/g, ''))}
            />
          </div>

          <div style={{ display: 'flex', gap: 'var(--space-sm)', marginTop: 'var(--space-md)' }}>
            <Button
              type="primary"
              icon={<LoadingOutlined spin={loading.signals} />}
              onClick={onGenerateSignals}
              loading={loading.signals}
              disabled={!selectedStrategy || !stockCode}
              style={{ flex: 1 }}
            >
              生成信号
            </Button>
            <Button
              type="primary"
              icon={<PlayCircleOutlined />}
              onClick={onRunBacktest}
              loading={loading.backtest}
              disabled={!selectedStrategy || !stockCode}
              style={{ flex: 1 }}
            >
              执行回测
            </Button>
            <Button
              icon={<ThunderboltOutlined />}
              onClick={onOptimize}
              loading={loading.optimize}
              disabled={!selectedStrategy || !stockCode}
            >
              参数优化
            </Button>
          </div>
          <div style={{ marginTop: 'var(--space-sm)' }}>
            <Button
              type="primary"
              danger
              icon={<BarChartOutlined />}
              onClick={onCompare}
              loading={loading.optimize}
              disabled={!stockCode}
              block
            >
              一键对比所有策略
            </Button>
          </div>
        </div>
      </Card>
    </div>
  )
}
```

- [ ] **Step 3: 提交**

```bash
git add frontend/src/components/strategies/StrategyConfig.tsx
git commit -m "feat(frontend): create StrategyConfig component"
```

---

## Task 5: 创建 StrategyResults.tsx

**Files:**
- Create: `frontend/src/components/strategies/StrategyResults.tsx`

- [ ] **Step 1: 创建组件**

```typescript
// frontend/src/components/strategies/StrategyResults.tsx
import { Card, Spin, Empty } from 'antd'
import { LoadingOutlined } from '@ant-design/icons'
import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'
import type { SignalDataPoint, SignalStats, StrategyBacktestResponse, KlineData } from '../../types'

interface StrategyResultsProps {
  klineData: KlineData[]
  signals: SignalDataPoint[]
  signalStats: SignalStats | null
  backtestResult: StrategyBacktestResponse | null
  loading: { signals: boolean; backtest: boolean }
  chartRef: React.RefObject<ReactECharts>
  getChartOption: () => EChartsOption
  children?: React.ReactNode
}

export function StrategyResults({
  klineData,
  signals,
  signalStats,
  backtestResult,
  loading,
  chartRef,
  getChartOption,
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
            option={getChartOption()}
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
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/components/strategies/StrategyResults.tsx
git commit -m "feat(frontend): create StrategyResults component"
```

---

## Task 6: 创建 BacktestDetails.tsx

**Files:**
- Create: `frontend/src/components/strategies/details/BacktestDetails.tsx`

- [ ] **Step 1: 迁移表格列定义**

从 Strategies.tsx 迁移：
- `tradeColumns` (第 541-556 行)
- `optimizeColumns` (第 558-582 行)
- `compareColumns` (第 667-712 行)

- [ ] **Step 2: 创建完整组件**

```typescript
// frontend/src/components/strategies/details/BacktestDetails.tsx
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

// 迁移的 tradeColumns
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

// 迁移的 optimizeColumns
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

// 迁移的 compareColumns
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
    sorter: (a: any, b: any) => a.metrics.total_return - b.metrics.total_return,
    render: (v: number) => <span style={{ color: v >= 0 ? '#34c759' : '#ff3b30', fontWeight: 600 }}>{v.toFixed(2)}%</span>,
  },
  {
    title: '夏普比率',
    dataIndex: ['metrics', 'sharpe_ratio'],
    key: 'sharpe_ratio',
    sorter: (a: any, b: any) => a.metrics.sharpe_ratio - b.metrics.sharpe_ratio,
    render: (v: number) => v.toFixed(4),
  },
  {
    title: '最大回撤',
    dataIndex: ['metrics', 'max_drawdown'],
    key: 'max_drawdown',
    sorter: (a: any, b: any) => a.metrics.max_drawdown - b.metrics.max_drawdown,
    render: (v: number) => <span style={{ color: '#ff3b30' }}>{v.toFixed(2)}%</span>,
  },
  {
    title: '胜率',
    dataIndex: ['metrics', 'win_rate'],
    key: 'win_rate',
    sorter: (a: any, b: any) => a.metrics.win_rate - b.metrics.win_rate,
    render: (v: number) => `${v.toFixed(2)}%`,
  },
  {
    title: '交易次数',
    dataIndex: ['metrics', 'total_trades'],
    key: 'total_trades',
    sorter: (a: any, b: any) => a.metrics.total_trades - b.metrics.total_trades,
  },
]

export function BacktestDetails({
  signalStats,
  backtestResult,
  optimizeResult,
  compareResult
}: BacktestDetailsProps) {
  // 空状态检查
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
            pagination={{ pageSize: 20, showSizeChanger: true, showTotal: (t) => `共 ${t} 条` }}
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
```

- [ ] **Step 3: 提交**

```bash
git add frontend/src/components/strategies/details/BacktestDetails.tsx
git commit -m "feat(frontend): create BacktestDetails component"
```

---

## Task 7: 重构 Strategies.tsx 为容器组件

**Files:**
- Modify: `frontend/src/pages/Strategies.tsx`

- [ ] **Step 1: 精简为容器组件**

保留：
- 所有 state 和 useEffect
- 所有 API 调用逻辑
- waitForJob 工具函数
- 入口 JSX 结构（3 列 grid 布局）

删除并替换为子组件：
- StrategyList.tsx
- StrategyConfig.tsx
- StrategyResults.tsx + BacktestDetails.tsx

```typescript
// frontend/src/pages/Strategies.tsx (精简后 ~100 行)
import { useState, useEffect, useRef } from 'react'
import { message } from 'antd'
import { LineChartOutlined } from '@ant-design/icons'
import ReactECharts from 'echarts-for-react'
import {
  getStrategies,
  generateSignals,
  runStrategyBacktest,
  submitOptimizeParameters,
  getJobStatus,
  getStockIndicators,
  compareStrategies,
} from '../services/api'
import { logger } from '../utils/logger'
import { usePersistedState } from '../hooks/usePersistedState'
import dayjs from 'dayjs'
import { StrategyList } from '../components/strategies/StrategyList'
import { StrategyConfig } from '../components/strategies/StrategyConfig'
import { StrategyResults } from '../components/strategies/StrategyResults'
import { BacktestDetails } from '../components/strategies/details/BacktestDetails'
import { getChartOption } from '../utils/chart'
import type { StrategyInfo, SignalDataPoint, SignalStats, StrategyBacktestResponse, OptimizeResponse, CompareResponse } from '../types'

function Strategies() {
  const chartRef = useRef<ReactECharts>(null)

  // State - 管理所有共享状态
  const [strategies, setStrategies] = useState<StrategyInfo[]>([])
  const [selectedStrategy, setSelectedStrategy] = usePersistedState<string | null>('strategies_selectedStrategy', null)
  const [loadingStrategies, setLoadingStrategies] = useState(true)
  const [loadingSignals, setLoadingSignals] = useState(false)
  const [loadingBacktest, setLoadingBacktest] = useState(false)
  const [loadingOptimize, setLoadingOptimize] = useState(false)
  const [stockCode, setStockCode] = usePersistedState<string | null>('strategies_stockCode', null)
  const [dateRange, setDateRange] = usePersistedState<[string, string]>('strategies_dateRange', [
    dayjs().subtract(1, 'year').format('YYYY-MM-DD'),
    dayjs().format('YYYY-MM-DD')
  ])
  const [initialCapital, setInitialCapital] = usePersistedState('strategies_initialCapital', 100000)
  const [parameters, setParameters] = useState<Record<string, number | string>>({})
  const [signals, setSignals] = useState<SignalDataPoint[]>([])
  const [signalStats, setSignalStats] = useState<SignalStats | null>(null)
  const [backtestResult, setBacktestResult] = useState<StrategyBacktestResponse | null>(null)
  const [optimizeResult, setOptimizeResult] = useState<OptimizeResponse | null>(null)
  const [klineData, setKlineData] = useState<KlineData[]>([])
  const [compareResult, setCompareResult] = useState<CompareResponse | null>(null)

  interface KlineData { date: string; open: number; close: number; high: number; low: number; volume: number }

  // ... 所有 API 调用逻辑保持不变 ...
  // (handleGenerateSignals, handleRunBacktest, handleOptimize, handleCompare, waitForJob)

  const getCurrentChartOption = () => getChartOption(klineData, signals, backtestResult)

  return (
    <div className="fade-in">
      <div className="page-header">
        <div className="flex flex-between" style={{ flexWrap: 'wrap', gap: 'var(--space-md)' }}>
          <div>
            <h1 className="page-title">策略研究</h1>
            <p className="page-subtitle">选择策略、配置参数、执行回测</p>
          </div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr 1fr', gap: 'var(--space-lg)', alignItems: 'start' }}>
        {/* Left: Strategy List */}
        <StrategyList
          strategies={strategies}
          selectedStrategy={selectedStrategy}
          loading={loadingStrategies}
          onSelect={setSelectedStrategy}
        />

        {/* Middle: Configuration */}
        <StrategyConfig
          strategies={strategies}
          selectedStrategy={selectedStrategy}
          stockCode={stockCode}
          dateRange={dateRange}
          initialCapital={initialCapital}
          parameters={parameters}
          loading={{ signals: loadingSignals, backtest: loadingBacktest, optimize: loadingOptimize }}
          onStockCodeChange={setStockCode}
          onDateRangeChange={setDateRange}
          onCapitalChange={setInitialCapital}
          onParameterChange={setParameters}
          onGenerateSignals={handleGenerateSignals}
          onRunBacktest={handleRunBacktest}
          onOptimize={handleOptimize}
          onCompare={handleCompare}
        />

        {/* Right: Results */}
        <StrategyResults
          klineData={klineData}
          signals={signals}
          signalStats={signalStats}
          backtestResult={backtestResult}
          loading={{ signals: loadingSignals, backtest: loadingBacktest }}
          chartRef={chartRef}
          getChartOption={getCurrentChartOption}
        >
          <BacktestDetails
            signalStats={signalStats}
            backtestResult={backtestResult}
            optimizeResult={optimizeResult}
            compareResult={compareResult}
          />
        </StrategyResults>
      </div>
    </div>
  )
}

export default Strategies
```

- [ ] **Step 2: 添加 KlineData 类型导出**

在 `frontend/src/types/index.ts` 中确认或添加 KlineData 类型

- [ ] **Step 3: 运行 TypeScript 检查**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 4: 提交**

```bash
git add frontend/src/pages/Strategies.tsx
git commit -m "refactor(frontend): extract StrategyList, StrategyConfig, StrategyResults components"
```

---

## Task 8: 创建目录结构并最终验证

- [ ] **Step 1: 确保目录存在**

```bash
mkdir -p frontend/src/components/strategies/details
```

- [ ] **Step 2: 验证构建**

```bash
cd frontend && npm run build
```

- [ ] **Step 3: 最终提交**

```bash
git add -A
git commit -m "feat(frontend): complete Strategies page refactoring into smaller components"
```

---

## 自我检查清单

- [ ] Spec 覆盖：设计文档中的每个需求都有对应任务
- [ ] 无占位符：所有步骤都包含实际代码
- [ ] 类型一致性：Props 类型在任务间保持一致
- [ ] 目录结构：所有文件路径正确
- [ ] 测试计划涵盖所有功能