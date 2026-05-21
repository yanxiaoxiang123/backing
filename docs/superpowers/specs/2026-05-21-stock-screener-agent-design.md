# 股票筛选 AI Agent 设计

> **Goal:** 将 AI 选股能力融入 `/screener` 页面，参考 a-stock-screener skill，无需用户输入参数，按固定条件筛选全市场股票，输出 TOP 5 推荐及 AI 分析理由。

## 整体流程

```
用户点击"开始选股"
        ↓
第一阶段：mootdx 并行扫描全市场股票（从 DB Stock 表读取代码列表）
        ↓
第二阶段：纯代码计算各项指标（PE/PB/ROE/MACD/MA/成交量）
        ↓
第三阶段：综合评分排序 → 选出 TOP 5 候选股
        ↓
第四阶段：AI Agent 深度分析 TOP 5（技术→情报→风控→策略→决策）
        ↓
输出：TOP 5 推荐股票 + 各股票 AI 分析理由
```

## 固定筛选条件（来自 a-stock-screener SKILL.md）

### 价值投资首选
- PE：5-15倍
- PB：<2倍
- 股息率：>3%

### 成长股
- ROE：>10%
- 净利润增长：>5%

### 技术面
- 均线多头排列（MA5 > MA10 > MA20）
- MACD 金叉
- 成交量放大（今日成交量 > 20日均量1.5倍）

### 综合评分权重
- 估值：30%
- 盈利：25%
- 技术：25%
- 股息/分红：20%

## 数据来源

- **股票列表**: `Stock` 表（从 DB 读取，约 5000+ 股票）
- **实时行情 + K 线**: `realtime_service`（mootdx），调用 `normalise_bars()`
- **财务数据**: mootdx 或 DB（PE/PB/ROE 等）

## 页面改造

### 入口
- 导航栏保留 `/screener` 入口，页面标题"股票筛选"

### 交互
1. 点击"开始选股"按钮
2. 显示进度条（阶段：扫描中 → 评分中 → AI分析中）
3. 输出 5 个股票卡片

### 输出卡片内容
每个股票卡片包含：
- 股票代码 + 名称
- 信号（买入/卖出/持有）
- 置信度（百分比）
- AI 分析理由（技术面、情报面、风控评估、策略）
- 目标价/止损价（可选）

## AI Agent 多阶段分析

与 AgentAnalysis 共用 orchestrator 框架，阶段定义：

| 阶段 | Agent | 说明 |
|------|-------|------|
| technical_analysis | 技术分析 | AI 分析 K 线走势、均线、MACD、RSI |
| intel | 情报分析 | AI 搜索相关新闻、资金流向 |
| risk | 风控评估 | AI 评估估值风险、市场风险 |
| strategy | 策略评估 | AI 给出操作策略 |
| decision | 决策 | 综合给出买入/卖出/持有信号 |

## 技术实现要点

### 第一阶段：并行扫描
- 从 `Stock` 表读取所有股票代码
- 使用 `ThreadPoolExecutor(max_workers=10)` 并行调用 mootdx
- `offset=120`（约 6 个月数据，足够计算 MA/MACD/RSI）
- 计算指标：MA5/10/20、MACD、RSI、成交量比

### 第二阶段：评分排序
- 按筛选条件过滤不满足的股票
- 计算综合评分（估值30% + 盈利25% + 技术25% + 股息20%）
- 排序取 TOP 5

### 第三阶段：AI 深度分析
- 对每只 TOP 5 股票调用 AI Agent 多阶段分析
- 可选：5 只串行分析，或并行分析（减少总时间）
- 结果存入 `screener_result` 表（可选）

### 后端新增文件
- `app/api/screener_agent.py` — 选股 Agent API 入口
- `app/agent/screener_orchestrator.py` — 选股专用编排器
- 或复用现有 orchestrator，传入 `mode='screener'`

### 前端改动
- `Screener.tsx` — 改为 AI 选股交互界面
- 进度显示（阶段进度条）
- 输出 5 个股票卡片

## 风险与注意事项

1. **mootdx 速度**：5000+ 股票 × 10 线程，并行扫描约 1-2 分钟
2. **AI 成本**：TOP 5 每只做完整 5 阶段分析，约 10-15 次 API 调用
3. **财务数据**：mootdx 不一定提供 PE/PB/ROE，可能需要 fallback 到 DB 或设为可选
4. **超时处理**：Job 模式（submit + poll status），与 AgentAnalysis 一致

## 实施顺序

1. 后端 `screener_agent.py` API + Job 模式
2. 复用 orchestrator 实现选股逻辑
3. 前端 `Screener.tsx` 改造成 AI 选股界面
4. 测试 + 调优