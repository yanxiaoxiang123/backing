# 模拟盘 4–8 周连续运行验收 runbook（US-3.5；P3-5）

> 日期：2026-08-15
> 背景：切片 12 已交付机制（soak 循环、恢复演练、重放审计）并在本机后台启动连续运行；
> 完整验收需要 4–8 周墙钟运行，按本清单由运行方执行。判据来自规格 v2 决策 21/22/23 与 P3-5。

## 环境

- 后端：`cd backend && python main.py`（:8808）；soak 循环默认开启（间隔 60s，`PAPER_SOAK_INTERVAL_S`/`PAPER_SOAK_ENABLED` 可调）。
- 数据：日线由既有同步流程维护；审批后下一交易日开盘价撮合（无 bar 则等待，窗口过后过期）。
- 凭证：`API_KEY`（`backend/.env`）。

## 每日检查（连续 4–8 周）

1. `python scripts/paper_replay_audit.py` → 输出 PASS。
2. `POST /api/v1/paper/match` → 无异常；`GET /api/v1/paper/account` 现金/持仓符合预期。
3. 若有待批订单：`GET /api/v1/paper/plan` 核对盘前计划；审批后下一交易日检查是否按开盘价成交（费用明细正确）。
4. `GET /api/v1/paper/alerts`：检查新增告警（数据陈旧/回撤/费用）；确认同日去重生效。
5. 工作台（:5174）：事件流/审批卡/归因/告警面板可交互。

## 每周检查

1. 归因复核：`GET /api/v1/paper/attribution` 分解与手动计算一致（alpha/beta/费用拖累）。
2. 审计抽样：随机 1 笔成交，用 `GET /api/v1/paper/events` 从 proposed → filled 完整回放，金额与费用逐项核对。
3. 后台日志：`grep "paper soak cycle" /tmp/backend_run.log`，确认循环持续运行且无异常堆栈。

## 恢复演练（每周一次）

1. 准备：确保存在 ≥1 笔已批准待撮合订单（或制造一笔）。
2. 杀进程：`lsof -ti :8808 | xargs kill -9`。
3. 重启：`cd backend && nohup python main.py > /tmp/backend_run.log 2>&1 &`。
4. `POST /api/v1/paper/match` 两遍，断言：
   - 第一遍处理完成；第二遍 `processed == 0`（无重复成交/重复过期——事务原子 + 状态机）。
   - 每笔订单终态唯一（filled/expired/cancelled/rejected），无残留 approved。
5. `python scripts/paper_replay_audit.py` → PASS（重放与现状一致，证明无丢事件/无双写）。

## 验收判据（达成即关闭 P3-5）

- [ ] 连续运行 ≥ 4 周（每日检查全绿；每周恢复演练成功）。
- [ ] 恢复成功率 100%（演练 4 周 × ≥1 次全通过）。
- [ ] 每笔订单可用重放工具复现并解释（抽查 ≥5 笔，含买入/卖出/过期/一字板拒绝路径）。
- [ ] 无审批订单从未成交（抽查审计日志确认）。
- [ ] 归因与告警在连续运行期持续可用且数值可复核。

## 已知边界（本 runbook 范围外）

- 撮合为日线粒度（下一交易日开盘价）；周末/同步滞后时订单等待而非过期（窗口以 bar 到达为准）。
- 一字板判定为开=高=低=涨跌停价近似（未接 L2 盘口）。
- 4–8 周墙钟本身由运行方执行；本机已连跑时长在交付时报告。
