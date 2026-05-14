# Chat Agents 完整迁移设计

**日期**: 2026-05-14
**目标**: 将 TradingAgents-astock 完整迁移到 backing 项目

## 概述

将 `TradingAgents-astock/tradingagents/` 完整迁移至 `backend/app/agents_chat/`，实现完整的多 Agent 协作系统，包括：
- 17 个数据 vendor
- 7 分析师 + 3 风险辩手 + 研究员/交易员/经理
- LangGraph 工作流编排
- 流式输出支持

## 文件结构

```
backend/app/
└── agents_chat/                      # 全新重建
    ├── __init__.py
    ├── agents/                      # 分析师 (迁移自 TradingAgents)
    │   ├── analysts/
    │   │   ├── market_analyst.py       # 大盘分析
    │   │   ├── social_media_analyst.py # 社交媒体情绪
    │   │   ├── news_analyst.py         # 新闻分析
    │   │   ├── fundamentals_analyst.py # 基本面分析
    │   │   ├── policy_analyst.py       # 政策分析
    │   │   ├── hot_money_tracker.py   # 热钱追踪
    │   │   └── lockup_watcher.py      # 解禁追踪
    │   ├── researchers/
    │   │   ├── bull_researcher.py     # 多头研究员
    │   │   └── bear_researcher.py     # 空头研究员
    │   ├── risk_mgmt/
    │   │   ├── aggressive_debator.py  # 激进派辩手
    │   │   ├── conservative_debator.py # 保守派辩手
    │   │   └── neutral_debator.py      # 中立派辩手
    │   ├── managers/
    │   │   ├── portfolio_manager.py    # 组合经理
    │   │   └── research_manager.py    # 研究经理
    │   ├── trader/
    │   │   └── trader.py              # 交易员
    │   └── utils/
    │       ├── agent_states.py        # Agent 状态定义
    │       ├── agent_utils.py         # 工具函数
    │       └── memory.py              # Memory 实现
    ├── graph/                       # LangGraph 工作流 (迁移)
    │   ├── __init__.py
    │   ├── trading_graph.py          # 主图类
    │   ├── setup.py                  # 节点边构建
    │   ├── conditional_logic.py      # 路由决策
    │   ├── propagation.py            # 状态传播
    │   ├── reflection.py             # 反思机制
    │   ├── signal_processing.py      # 信号提取
    │   └── checkpointer.py          # 检查点
    ├── dataflows/                   # 数据层 (迁移)
    │   ├── __init__.py
    │   ├── a_stock.py               # 核心 A 股数据
    │   ├── config.py
    │   ├── interface.py
    │   ├── utils.py
    │   └── ... (其他 vendor 方法)
    └── llm_clients/                 # LLM 客户端 (迁移)
        ├── __init__.py
        ├── base.py
        └── deepseek.py              # 对接现有 DeepSeek
```

## Agent 工作流

```
输入: 股票代码 + 日期
  ↓
7 分析师顺序执行:
  MarketAnalyst → SocialMediaAnalyst → NewsAnalyst →
  FundamentalsAnalyst → PolicyAnalyst → HotMoneyTracker → LockupWatcher
  ↓
QualityGate (数据质量检验)
  ↓
研究员辩论:
  BullResearcher ↔ BearResearcher (ResearchManager 裁判)
  ↓
Trader 生成投资计划
  ↓
风险辩手辩论:
  Aggressive/Conservative/Neutral RiskDebators
  ↓
PortfolioManager 最终决策
  ↓
输出: FinalTradeDecision (流式)
```

## 数据源 (17 Vendor)

| 数据类型 | 来源 | 方法 |
|---------|------|------|
| OHLCV K线 | mootdx (TCP 7709) | `get_stock_data()` |
| 实时行情 | 腾讯财经 | `_tencent_quote()` |
| 技术指标 | stockstats | `get_indicators()` |
| 基本面 | 腾讯+mootdx+akshare | `get_fundamentals()` |
| 资产负债表 | akshare | `get_balance_sheet()` |
| 现金流量表 | akshare | `get_cashflow()` |
| 利润表 | akshare | `get_income_statement()` |
| 股票新闻 | akshare | `get_news()` |
| 全球新闻 | akshare | `get_global_news()` |
| 内部交易 | mootdx F10 | `get_insider_transactions()` |
| EPS 预测 | akshare | `get_profit_forecast()` |
| 热点股票 | 同花顺 | `get_hot_stocks()` |
| 北向资金 | 同花顺 | `get_northbound_flow()` |
| 概念板块 | 百度股市通 | `get_concept_blocks()` |
| 资金流向 | 百度股市通 | `get_fund_flow()` |
| 龙虎榜 | akshare | `get_dragon_tiger_board()` |
| 解禁数据 | akshare | `get_lockup_expiry()` |

## API 映射

| 现有 API | 新实现 |
|---------|--------|
| `POST /chat/stream` | `TradingAgentsGraph.astream()` |
| `POST /chat/agent/technical` | `MarketAnalyst` 节点 |
| `POST /chat/agent/sentiment` | `SocialMediaAnalyst` 节点 |
| `POST /chat/agent/news` | `NewsAnalyst` 节点 |
| `POST /chat/agent/fundamentals` | `FundamentalsAnalyst` 节点 |
| `POST /chat/agent/policy` | `PolicyAnalyst` 节点 |
| `POST /chat/agent/hotmoney` | `HotMoneyTracker` 节点 |
| `POST /chat/agent/lockup` | `LockupWatcher` 节点 |

## 流式输出

使用 `graph.astream_events()` 实现节点级别流式：

```python
async def stream_graph(stock_code: str, trade_date: str):
    graph = TradingAgentsGraph()
    state = graph.initial_state(stock_code, trade_date)

    async for event in graph.astream_events(state):
        if event["event"] == "on_chat_model_stream":
            yield event["data"]["chunk"].content
```

## 依赖关系

```
1. llm_clients/    (基础 - LLM 调用)
       ↓
2. dataflows/      (数据获取)
       ↓
3. agents/utils/   (状态定义、工具)
       ↓
4. agents/analysts/(7 分析师)
       ↓
5. agents/researchers/ + agents/risk_mgmt/ + agents/managers/ + agents/trader/
       ↓
6. graph/          (工作流编排)
       ↓
7. API 集成        (流式输出)
```

## 实施顺序

1. **Phase 1**: `llm_clients/` + `dataflows/`
2. **Phase 2**: `agents/utils/` + `agents/analysts/`
3. **Phase 3**: 其他 Agent (researchers/risk_mgmt/managers/trader)
4. **Phase 4**: `graph/` 工作流编排
5. **Phase 5**: API 集成 + 流式输出

## 现有代码处理

删除 `backend/app/agents/` 下的所有现有 Agent（除了依赖项如 `base.py`），替换为 `agents_chat/`。
