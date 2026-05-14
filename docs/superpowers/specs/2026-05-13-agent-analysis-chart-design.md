# AI 分析结果页技术图表设计

## 目标

在 AI 分析结果顶部展示轻量级 K 线图，让用户在看到 AI 结论前先了解股票走势。

## 设计决策

**轻量版优先**：只展示 K 线 + MA5/MA10/MA20，不重复完整技术指标面板。完整图表用户可进股票详情页看。

## 数据流

```
AgentAnalysis.tsx
  └─ 分析完成后
      ├─ 结果区顶部
      │   └─ ReactECharts (轻量 K 线图)
      │       └─ 调用 getStockIndicators(stock_code, 'daily', 180天)
      └─ 下方决策卡片 + 阶段卡片
```

## 前端改动

### 文件：frontend/src/pages/AgentAnalysis.tsx

在 `renderAnalysisPanel()` 的结果区（`result &&` 块内），在决策卡片之前插入图表卡片：

```tsx
{result && (
  <div className="fade-in">
    {/* K线图表 - 轻量版 */}
    <Card
      style={{ marginBottom: 16 }}
      title={`${result.stock_name} (${result.stock_code}) 走势`}
      extra={
        <a href={`/stocks/${result.stock_code}`} target="_blank" rel="noreferrer">
          查看完整图表 →
        </a>
      }
    >
      <ReactECharts
        option={getLightChartOption(stockIndicators)}
        style={{ height: 300 }}
        opts={{ renderer: 'canvas' }}
      />
    </Card>

    {/* 决策卡片 */}
    <Card ...>
    ...
```

### 新增函数：getLightChartOption()

```typescript
const getLightChartOption = (data: KlineIndicator[]): EChartsOption => {
  const dates = data.map(d => d.date)
  const ohlc = data.map(d => [d.open, d.close, d.low, d.high])
  const ma5 = data.map(d => d.ma5)
  const ma10 = data.map(d => d.ma10)
  const ma20 = data.map(d => d.ma20)

  return {
    backgroundColor: '#fff',
    animation: false,
    legend: {
      top: 10, left: 'center',
      textStyle: { color: 'var(--color-text-secondary)', fontSize: 11 },
      data: ['K线', 'MA5', 'MA10', 'MA20']
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      backgroundColor: '#fff',
      borderColor: 'var(--color-border)',
      textStyle: { color: 'var(--color-text-primary)' },
    },
    grid: { left: '10%', right: '8%', top: 50, bottom: 60 },
    xAxis: [{
      type: 'category', data: dates,
      boundaryGap: false,
      axisLine: { onZero: false },
      axisLabel: { color: 'var(--color-text-tertiary)', fontSize: 10 },
    }],
    yAxis: [{
      scale: true,
      axisLabel: { color: 'var(--color-text-tertiary)', fontSize: 10 },
    }],
    dataZoom: [{
      type: 'inside', start: 70, end: 100
    }, {
      show: true, type: 'slider',
      bottom: 10, start: 70, end: 100, height: 20,
    }],
    series: [
      {
        name: 'K线', type: 'candlestick', data: ohlc,
        itemStyle: { color: '#ff3b30', color0: '#34c759', borderColor: '#ff3b30', borderColor0: '#34c759' }
      },
      { name: 'MA5', type: 'line', data: ma5, smooth: true, lineStyle: { opacity: 0.5 } },
      { name: 'MA10', type: 'line', data: ma10, smooth: true, lineStyle: { opacity: 0.5 } },
      { name: 'MA20', type: 'line', data: ma20, smooth: true, lineStyle: { opacity: 0.5 } },
    ]
  }
}
```

### 数据获取

在 `handleAnalyze()` 完成后、`setResult(data)` 之前：

```typescript
// 获取 K 线数据用于图表
const indicatorsRes = await getStockIndicators(
  selectedStock,
  'daily',
  new Date(Date.now() - 180 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
  new Date().toISOString().split('T')[0],
)
setStockIndicators(indicatorsRes.data)
```

## 实现顺序

1. `AgentStage` 类型已更新（thinking 字段）
2. `AgentAnalysis.tsx` - 添加图表卡片 + `getLightChartOption` + 数据获取状态
3. 测试：运行分析，观察结果页是否显示 K 线图

## 验证

- [ ] 分析完成后图表显示在结果区顶部
- [ ] 图表包含 K 线 + MA5 + MA10 + MA20
- [ ] 点击"查看完整图表"链接到股票详情页