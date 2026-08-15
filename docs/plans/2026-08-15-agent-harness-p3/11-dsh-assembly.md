# 11 DSH 运行时装配 E2E

**交付**：在未跟踪克隆内构建 DSH runtime；quant.gateway Cordis 工具消费者；独立 UI + 工具审批卡；session↔run 映射端到端。

**范围**：
- 构建：`deepseek-harness/` 内 pnpm install + build、`pip install -e python/sdk python/sdk-runtime`；仅产物（node_modules/dist/egg-info，均在克隆 .gitignore 内），不改源文件；commit 固定 47f9438。
- 插件：`dsh-quant-plugin/` 提供 quant.gateway 工具消费者（走 FastAPI Tool Gateway + 现有认证）、profile 配置、会话工具 skill。
- UI：DSH bundled web 启动后展示量化工具；调用出现审批卡（参数+风险）；session_id ↔ run_id 双向映射（agent_runs.session_id）。
- E2E：对话 → 审批 → 后端 run 创建 → SSE → Chat Node 渲染结构化结果。

**验收**：
- 构建成功证据（pnpm build + pip -e 输出）；runtime 启动 smoke。
- 脚本化探针：网关调用、session↔run 映射、审批流；手动验收截图/记录。
- 构建失败降级：维持 HTTP 直连并记录（规格风险 3）。

**阻塞**：None
**委派**：eligible（隔离环境构建，低耦合）
