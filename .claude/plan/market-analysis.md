# 大盘分析功能实现计划

## 需求概述
在AI分析界面添加"大盘分析"功能，使用AI Agent分析上证指数、深证成指、创业板指等主要大盘指数的走势，给出综合判断。

## 任务类型
- [ ] Frontend (→ Gemini)
- [x] Backend (→ Codex)
- [x] Fullstack (→ Parallel)

## 技术方案

### 方案选择
由于需要同时修改前端（添加大盘分析Tab）和后端（添加指数数据获取和新的分析逻辑），采用全栈并行方案。

### 核心设计
1. **大盘指数选择**: 上证指数(sh.000001)、深证成指(sz.399001)、创业板指(sz.399006)、科创50(sz.000688)
2. **分析逻辑**: 复用现有的AgentOrchestrator，但针对指数做专门的提示词优化
3. **数据获取**: 扩展baostock_service添加指数数据获取功能

## 实现步骤

### 后端 (Backend)

#### Step 1: 扩展 baostock_service 添加指数数据获取
- 在 `app/services/baostock_service.py` 添加 `get_index_list()` 方法
- 添加 `get_index_daily_kline()` 方法获取指数K线数据

#### Step 2: 创建大盘分析 API
- 在 `app/api/agent.py` 添加 `/agent/market/analyze` 端点
- 支持同时分析多个指数，返回综合判断

#### Step 3: 添加指数到股票列表（可选）
- 扩展 `/api/stocks` 支持 `type=index` 参数返回大盘指数

### 前端 (Frontend)

#### Step 4: 扩展 AgentAnalysis 页面
- 在 Tabs 中添加"大盘分析"新 Tab
- 创建大盘指数选择组件（多选）
- 添加大盘分析结果展示组件

#### Step 5: 添加大盘分析 API 调用
- 在 `src/services/api.ts` 添加 `analyzeMarket()` 方法

## 关键文件

| 文件 | 操作 | 描述 |
|------|------|------|
| `backend/app/services/baostock_service.py` | 扩展 | 添加指数数据获取方法 |
| `backend/app/api/agent.py` | 扩展 | 添加大盘分析API端点 |
| `frontend/src/services/api.ts` | 扩展 | 添加analyzeMarket API |
| `frontend/src/pages/AgentAnalysis.tsx` | 修改 | 添加大盘分析Tab |

## 风险与缓解

| 风险 | 缓解措施 |
|------|----------|
| baostock API 不稳定 | 添加重试机制和错误处理 |
| 指数分析结果不准确 | 复用现有的技术分析Agent，确保逻辑一致 |
| 前端展示样式需统一 | 使用与现有分析结果一致的卡片样式 |

## 实现顺序
1. 后端: baostock_service 指数获取 → API 端点
2. 前端: API 调用 → UI 组件
3. 测试: 端到端测试大盘分析流程
