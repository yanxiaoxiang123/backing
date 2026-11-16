# Backing · 60 秒项目介绍

交付：`out/backing-intro.mp4`（音乐与音效）、`out/backing-intro-nobgm.mp4`（保留音效）。均为 1920×1080、30fps、60 秒，中文文案，无配音。

## 预览与编辑

```powershell
cd E:\stock\videos\backing-intro
npm ci
npm run dev
```

动效工作台：

```powershell
node C:/Users/13566/.codex/skills/video-shotcraft/workbench/scripts/open.mjs E:/stock/videos/backing-intro
```

访问 http://localhost:5198/?import=project 。镜头、字幕、转场、音效和配乐分轨；可调整文案、颜色、字号、位置和速度并导出。工作台预览多留 1 秒尾部编辑空间，成片实际内容为 60 秒。

## 工程说明

- `src/timeline.ts`：镜头、字幕、音效统一时间线与音频偏移补偿。
- `src/Main.tsx`：真实页面截图的相机运动、图表揭示、品牌与架构段。
- `src/workbench.ts`：可编辑多轨清单。
- `public/textures/`：真实前端组件截图，使用拦截接口注入的固定演示数据。
- `DESIGN.md`：产品简报、分镜、视觉与镜头卡适配依据。
- `QA.md`、`INDEPENDENT-REVIEW.md`：技术验证及独立审查。
- `public/audio/`：音乐、音效及许可来源。

采集脚本仅连接本地前端，所有 API 与 WebSocket 均拦截；不使用真实账号、聊天、持仓或数据库。全片声明“演示数据 · 仅供研究”，不承诺预测准确性或投资收益。

重新渲染可使用 Remotion 的 `bgm` 输入参数输出同一时间线的两版（默认含配乐；`--props='{"bgm":false}'` 为无配乐版）；`scripts/finalize.py` 为两版音轨裁齐 60 秒并设置快速播放。首次渲染请分别输出到两版交付文件名，再从仓库根目录运行 `python videos/backing-intro/scripts/finalize.py`；该脚本会保留渲染原片，避免对已完成的文件重复处理。详细参数参见脚本及验证记录。

音乐来自 Mixkit，音效来自 Freesound CC0；来源、原文件与衍生处理见各自 credits 和 manifest。音频已做客观峰值、响度、卡拍与同步测量，未宣称人工试听验收。
