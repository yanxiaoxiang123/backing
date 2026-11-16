# Agent Workspace Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让工作台支持后缀股票代码自动查询、名称搜索、连续追问、新闻公告和右侧行情联动。

**Architecture:** 共享股票解析层规范化所有标识；typed gateway 新增本地股票搜索；原生 runtime 在模型之前解析并验证目标，自动执行基础查询或研究。通过持久化 stock.selected 事件恢复会话目标，前端按会话消费事件并隔离行情与研究请求。

**Tech Stack:** Python/FastAPI/SQLAlchemy/Pydantic，React/TypeScript/Vitest，pytest，现有 DeepSeek runtime。

**Spec:** docs/superpowers/specs/2026-10-30-agent-workspace-improvements-design.md（用户已于本会话确认六项范围）

## Global Constraints

- 沿用 FastAPI、SQLAlchemy、Pydantic、React、TypeScript 和现有 DeepSeek 原生聊天运行时，不切换模型供应商，不引入外部 harness。
- 新工具只读、有限结果、输入校验，所有数据经过 typed gateway。禁止开放写入/模拟下单/宿主代码执行权限。
- 不引入迁移或自动股票同步；本地股票库缺数据需如实报告。
- 保留已有未提交改动；不执行 git commit/push。任务提交步骤由检查 diff 代替。
- 后端使用 D:/anaconda3/envs/backing/python.exe；前端使用 npm --prefix frontend。
- 模型工具名用下划线，注册表名保留域分隔点。

## Review Focus

- 非法后缀、英文标识符和长数字不能被截取为合法股票；任务 1 参数化测试。
- 新目标解析失败不得沿用旧股票回答；任务 3 会话测试。
- 截断的搜索结果不能被误判为唯一候选；任务 2 搜索与任务 3 目标测试。
- 较旧 SSE/HTTP 请求不能污染切换后的会话、run 和行情；任务 4 受控 Promise 测试。
- 模型不能用与本轮目标不同的股票或未授权工具绕过目标守卫；任务 3 runtime 测试。

---

### Task 1: 股票标识兼容

**Files:** backend/app/domain/stock_codes.py；backend/tests/test_stock_codes.py；frontend/src/utils/stockIdentity.ts；frontend/src/utils/stockIdentity.test.ts。

**Interfaces:** 保留 normalize_stock_code、find_stock_reference、stock_code_from_text、canonicalize_stock_code_in_text 与 normalizeStockCode/extractStockCode。新增 find_stock_references(text: str, *, db: Any | None = None) -> list[StockReference] 供任务 3 多代码检查。显式交易所优先，包括 sh.000001；裸代码推断保持各层已有规则。

- [x] 添加后缀、大小写、中文句子、完整 token 边界、去重之前的多引用位置、规范化幂等测试；断言 000001.sz -> sz.000001、000001.sh -> sh.000001、1234567/abc000001/000001.xyz 无部分匹配。
- [x] 执行后端 test_stock_codes.py 和前端 stockIdentity.test.ts，确认新增用例失败。
- [x] 实现完整 token 识别和前后缀处理；自由文本提取不能吞掉中文标点，也不能剥离非法后缀。同步工具字段的受支持格式说明可以在任务 2/3 完成。
- [x] 重跑上述测试及 test_stock_code_resolution.py；检查任务 diff。

### Task 2: 本地股票搜索工具

**Files:** backend/app/tools/market.py；backend/tests/test_market_search.py（新增）。

**Interfaces:** market.search（模型别名 market_search 由任务 3 映射）；MarketSearchParams(query: str, limit: int = 10)，1 <= limit <= 20，query trim 后非空且 <=100 字符；输出 {source_id, as_of, vendor, query, matches: [{code,name,market}], total, truncated}。精确规范代码查询；精确名称命中时只返回精确名称；否则名称包含查询；按 code 排序。

- [x] 写 gateway 调用测试：后缀代码、精确名优先、包含匹配、零命中、limit=1 仍返回真实 total、LIKE %/_ 按字面处理、read 权限。
- [x] 使用 backing Python 跑 test_market_search.py，确认失败。
- [x] 在 MARKET_TOOLS 注册只读搜索，SQLAlchemy 查询现有 Stock，自动转义通配符；使用任务 1 规范化函数，禁止网络和同步。
- [x] 重跑测试，检查 diff；不提交。

### Task 3: 运行时目标解析、自动查询和连续追问

**Files:** backend/app/agent_chat/targets.py（新增）；policy.py；runtime.py；seam.py；backend/tests/test_agent_chat_targets.py（新增）；test_agent_chat_native.py。

**Interfaces:** 新增 STOCK_SELECTED='stock.selected'，payload {stock_code: str}；必须在 gateway 成功确认股票后发出。TargetResolution dataclass 包含 stock_code: str | None、message: str | None、explicit: bool；目标解析器 resolve_target(message, previous_stock, context, invoke) -> TargetResolution，invoke 接收 registry 名和参数返回 envelope。历史目标仅来自最近成功 stock.selected 或兼容旧版的用户代码/成功股票查找事件，不能从助手叙述选股。

- [x] 测试：单代码不依赖模型工具调用即执行 stock_info/snapshot；无 run；canonical 目标；名称唯一/歧义/未找到；本轮无效目标阻止旧股回退；两只股票先后查询后追问用最新；上下文验证；分析名称在解析后仅创建一个 run；缺失目标不创建 run；多代码和比较请求要求选择；失败基础信息不查 snapshot/不发 selected；模型越权/跨股票请求被拒绝；新闻公告 schema 和调用经过 gateway。
- [x] 跑目标及 native 测试确认新增用例失败。已有分析测试应补充 Stock fixture，反映批准的股票存在性前置条件，不删除原有断言。
- [x] 目标模块通过 gateway 查找本地股票。剥离有限的查询/分析/新闻等指令词提取名称；不把纯追问文本当新名字。不确定输入可交模型使用 market_search，但歧义不授权研究。运行时强制验证唯一股票后自动查询 stock_info/snapshot；明确分析自动单次 run；只读追问开放新闻公告。保持 deadline、cancel、凭证快照和历史预算。
- [x] classify 保留社交无工具优先；支持直接代码、名称查询、新闻公告及上下文。模型系统提示提供当前 UTC 日期、规范目标、来源要求和研究已执行事实。模型工具调用必须受 scope 和本轮目标约束；搜索唯一结果可更新目标，多结果不自动选第一项。
- [x] 历史恢复读取当前会话已确认事件；旧版兼容从最近用户代码验证 stock_info 后采用，失败/歧义事件不可确认股票。模型数据消息包含真实自动查询结果，符合模型 tool-call 配对要求。
- [x] 跑 tests/test_agent_chat_native.py、targets、schema、seam、service、api 及工具测试；检查 diff。

### Task 4: 会话目标恢复与研究面板隔离

**Files:** frontend/src/types/chat.ts；services/agentChats.ts（如 SSE 类型校验需要）；hooks/useAgentChat.ts；hooks/useAgentRun.ts；pages/AgentWorkspace.tsx；对应 .test.ts/.test.tsx。

**Interfaces:** UseAgentChatResult 增加 stockCode: string | null，从每个 turn 的 stock.selected 事件重建，按 turn 时间顺序选择最新，不由助手文本推断。UseAgentRunResult 增加 detach(): void，清理流、状态、URL run_id；忽略已失效请求。已有旧事件兼容。

- [x] 写测试：selected 事件前于 submit 返回、重放旧事件不覆盖新目标、加载旧历史不改变当前目标；切换/新建会话清空目标；旧 SSE 不能写入新会话；受控请求验证旧行情与旧 run 不回写；工作台查询目标优先旧 run、显示规范股票、无目标时 URL/run 回退。
- [x] 跑上述测试确认失败。
- [x] 扩展 TurnParts 记录目标并从 parts/turns 有序派生；connect/select/send 添加会话代数或 ref 守卫，切换时立即停旧流并清理状态；恢复按现有 SSE 路径，不新增 DB。
- [x] useAgentRun 增加 detach 和请求所属 run 检查，工作台只展示当前 thread 关联研究；右侧行情使用 chat.stockCode，显式标注股票；加载新行情时清空旧数据。保留既有 UI 与组件风格，不改图表设计。
- [x] 跑 hook、工作台、stockIdentity 测试及 typecheck，检查 diff。

### Task 5: 交叉验证与审查

- [x] 使用 superpowers:requesting-code-review 对本轮变更做独立审查，重点按 Review Focus 验证完整查询/追问流程。
- [x] 接收反馈使用 superpowers:receiving-code-review；修复确认的问题并重跑对应测试。
- [x] 使用 superpowers:verification-before-completion，执行相关 pytest（包含 gateway/API/聊天）、ruff check 修改 Python 文件、npm typecheck、前端相关 Vitest、ESLint 和 Prettier 修改文件，build。
- [x] 环境允许时按 gstack/run 实测工作台；不自动调用付费模型。无线上模型验证时明确写在交付说明；记录已有基线问题。
- [x] 更新本计划勾选状态，交付实际变更、测试结果和限制；不 commit/push。

## Self-review

规格的六项行为分别由任务 1–4 覆盖；搜索/目标接口与事件字段在计划中统一。Review Focus 的五类输入均有对应任务测试。无迁移、供应商切换或任意交易权限；现有脏工作区直接增量实施，保留现有改动。用户已确认范围，按照项目要求选择 subagent-driven 流程，不重复要求批准同一范围。
