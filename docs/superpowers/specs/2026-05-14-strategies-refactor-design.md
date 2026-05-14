# Strategies.tsx 重构设计文档

**日期：** 2026-05-14
**状态：** 已批准

## 1. 背景

`frontend/src/pages/Strategies.tsx` 现有 1084 行，承担了所有职责：策略选择、参数配置、回测执行、信号生成、优化、对比。这是典型的上帝组件（God Component）反模式。

## 2. 重构目标

将 Strategies.tsx 拆分为职责清晰的多个小组件：
- 提高可维护性（每文件 < 400 行）
- 提高可测试性（独立组件可单独测试）
- 提高可读性（组件名即职责）

## 3. 拆分方案

### 3.1 组件结构

```
Strategies.tsx (主容器，~100 行)
├── StrategyList.tsx (策略列表，~80 行)
├── StrategyConfig.tsx (参数配置+回测设置，~200 行)
└── StrategyResults.tsx (结果容器，~100 行)
    ├── BacktestDetails.tsx (回测/优化/对比结果，~250 行)
    └── [共享] SignalChart 逻辑提取为独立 renderChart 函数
```

### 3.2 State 管理

使用**属性穿透 + 回调函数**方式：
- `Strategies.tsx` 作为容器，管理所有共享 state
- 通过 props 向下传递
- 子组件通过 callback 向上报告事件

共享 props：
```typescript
interface StrategiesSharedProps {
  // 状态
  strategies: StrategyInfo[]
  selectedStrategy: string | null
  stockCode: string | null
  dateRange: [string, string]
  initialCapital: number
  parameters: Record<string, number | string>
  loading: { strategies: boolean; signals: boolean; backtest: boolean; optimize: boolean }
  // 结果
  signals: SignalDataPoint[]
  signalStats: SignalStats | null
  backtestResult: StrategyBacktestResponse | null
  optimizeResult: OptimizeResponse | null
  compareResult: CompareResponse | null
  klineData: KlineData[]
  // 操作
  onStrategySelect: (name: string) => void
  onParameterChange: (params: Record<string, number | string>) => void
  onGenerateSignals: () => void
  onRunBacktest: () => void
  onOptimize: () => void
  onCompare: () => void
}
```

### 3.3 StrategyList.tsx

**职责：** 展示策略列表，处理策略选择

**Props：**
```typescript
interface StrategyListProps {
  strategies: StrategyInfo[]
  selectedStrategy: string | null
  loading: boolean
  onSelect: (name: string) => void
}
```

**实现要点：**
- 使用 STRATEGY_METADATA 显示颜色和描述
- 选中态样式（边框 + 背景色）
- 滚动区域（maxHeight + overflowY: auto）

### 3.4 StrategyConfig.tsx

**职责：** 策略参数输入、回测配置（股票、日期、资金）、操作按钮

**Props：**
```typescript
interface StrategyConfigProps {
  strategies: StrategyInfo[]
  selectedStrategy: string | null
  stockCode: string | null
  dateRange: [string, string]
  initialCapital: number
  parameters: Record<string, number | string>
  loading: { signals: boolean; backtest: boolean; optimize: boolean }
  onStrategySelect: (name: string) => void
  onParameterChange: (params: Record<string, number | string>) => void
  onStockCodeChange: (code: string) => void
  onDateRangeChange: (range: [string, string]) => void
  onCapitalChange: (capital: number) => void
  onGenerateSignals: () => void
  onRunBacktest: () => void
  onOptimize: () => void
  onCompare: () => void
}
```

**实现要点：**
- `renderParameterInputs()` 提取为组件内函数
- StockSearch 组件嵌入
- 4 个操作按钮（生成信号、执行回测、参数优化、对比）
- 按钮 disabled 条件一致

### 3.5 StrategyResults.tsx

**职责：** 结果展示容器，包含 K线图表

**Props：**
```typescript
interface StrategyResultsProps {
  klineData: KlineData[]
  signals: SignalDataPoint[]
  backtestResult: StrategyBacktestResponse | null
  loading: { signals: boolean; backtest: boolean }
  chartRef: RefObject<ReactECharts>
  getChartOption: () => EChartsOption
}
```

**实现要点：**
- 保持现有的 `getChartOption()` 逻辑（抽取为 utils/echarts.ts）
- 图表区域 + 下方信号统计（条件渲染）
- 使用 `ReactECharts` + ref

### 3.6 BacktestDetails.tsx

**职责：** 回测结果、优化结果、策略对比的展示

**Props：**
```typescript
interface BacktestDetailsProps {
  signalStats: SignalStats | null
  backtestResult: StrategyBacktestResponse | null
  optimizeResult: OptimizeResponse | null
  compareResult: CompareResponse | null
}
```

**实现要点：**
- `tradeColumns`、`optimizeColumns`、`compareColumns` 迁移
- `getCompareChartOption()` 迁移到 utils
- 使用 Tabs 组织：回测结果（指标 + 交易记录）、优化结果、策略对比（指标 + 曲线）

### 3.7 共享常量迁移

新建 `frontend/src/constants/strategy.ts`：
```typescript
export const STRATEGY_METADATA: Record<string, { name: string; description: string; color: string }> = { ... }
export const COMPARE_COLORS = ['#0071e3', '#34c759', '#ff9500', '#ff3b30', '#af52de', '#5856d6', '#ff2d55', '#0a84ff']
```

### 3.8 工具函数迁移

新建 `frontend/src/utils/chart.ts`：
- `getChartOption()` - K线图表配置
- `getCompareChartOption()` - 策略对比图表配置

## 4. 文件清单

| 文件 | 行数（预估） |
|------|-------------|
| `Strategies.tsx` | ~100 |
| `StrategyList.tsx` | ~80 |
| `StrategyConfig.tsx` | ~200 |
| `StrategyResults.tsx` | ~100 |
| `BacktestDetails.tsx` | ~250 |
| `constants/strategy.ts` | ~40 |
| `utils/chart.ts` | ~120 |
| **总计** | ~890（净减少 ~200 行） |

## 5. 实现顺序

1. 提取常量到 `constants/strategy.ts`
2. 提取图表工具函数到 `utils/chart.ts`
3. 创建 `StrategyList.tsx`
4. 创建 `StrategyConfig.tsx`
5. 创建 `StrategyResults.tsx`
6. 创建 `BacktestDetails.tsx`
7. 重构 `Strategies.tsx` 为容器组件
8. 验证功能完整性

## 6. 测试计划

- [ ] 策略选择功能正常
- [ ] 参数配置保存和回显
- [ ] 生成信号正确显示
- [ ] 回测执行和结果展示
- [ ] 参数优化流程
- [ ] 策略对比功能
- [ ] 图表缩放和交互

## 7. 风险与注意事项

1. **API 调用顺序**：确保回测依赖的 state 顺序正确
2. **Loading 状态**：各操作的 loading 状态独立
3. **Chart Ref**：通过 ref 传递，保持现有功能
4. **usePersistedState**：保持现有持久化行为