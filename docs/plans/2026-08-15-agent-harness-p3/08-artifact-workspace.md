# 08 artifact 工作区写入与查看

**交付**：运行时节点把关键产物（策略规格、回测报告、研究摘要）写成每 run 独立工作区文件；列表/下载 API；工作台 ArtifactViewer 接线。

**范围**：
- 每 run 工作区目录（gitignored）；节点产出写文件并落 artifacts 记录，内容一致。
- API：列出某 run 产物、下载文件（沿用现有认证）。
- ArtifactViewer：展示列表与内容/下载。
- 已存在 artifacts 端点保持兼容。

**验收**：
- pytest：文件与记录一致、列表/下载、认证拒绝。
- Vitest：ArtifactViewer 渲染；`npm run build` 全绿。
- 手动：一个 run 完成后工作台可见其回测报告文件并可下载。

**阻塞**：None
**委派**：ineligible（runtime 节点耦合）
