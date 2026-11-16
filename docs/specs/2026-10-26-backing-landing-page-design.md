# Backing 公开落地页设计

- 状态：待用户审阅
- 日期：2026-10-26
- 范围：`frontend/` 新增公开落地页与两个法律页面；不改现有 app 设计系统
- 依据：`landing-page-design` skill、`superpowers:brainstorming` 流程
- 用户已确认的决策：新建公开落地页、内部/个人使用、品牌优先混合、仅落地页可索引、未登录跳 `/welcome/`、品牌 Backing + 中文副标、真实界面截图、墨黑主按钮 + 橙色点缀、只本地验证 SEO、隐私 + 条款、干净系统栈、Dashboard + 策略回测截图

## 1. 背景与问题

Backing 目前是一个 API Key 门禁的 A 股研究、回测、AI 分析和模拟交易系统。未登录用户只能看到 `/login` 的 API Key 表单，没有公开的价值主张、产品证据或使用说明。项目也没有可被搜索引擎读取的公开页面：`frontend/index.html` 只有 `<title>`，favicon 指向不存在的 `/vite.svg`，没有 `public/` 目录。

本次目标是新增一个**公开、可分享、可被索引的静态落地页**，讲清 Backing 是什么、能做什么、边界在哪里，并把唯一转化动作收敛到登录。

## 2. 目标与非目标

### 目标

1. 在 `/welcome/` 提供一个完整的静态营销页，未登录访问 app 路由时自动进入。
2. 用真实产品能力和真实界面截图建立信任，不编造客户、logo、用户数或收益。
3. 把 skill 的结构、文案、排版、间距、圆角、配色、动效规则落到落地页，同时保留 Backing 的暖奶油 + 墨黑 + 信号橙品牌身份。
4. 落地页可被搜索引擎直接读取（HTML 源码含全文案，不依赖 JS），app shell 和业务路由 `noindex`。
5. 不引入新的 npm 运行时依赖，不影响主 bundle 和现有 app。

### 非目标

1. 不重构现有 app 的全局设计系统、`src/styles/*` 和 AntD 组件。
2. 不做自助注册、账号体系、付费、预约演示或营销自动化。
3. 不做实盘交易、收益承诺或投资建议。
4. 不做整套 SEO 运营（canonical、sitemap、持续内容、外链）；本轮只做本地可验证的 meta、OG、robots 和结构化数据。
5. 不替换 app 内的 Ant Design 图标。
6. 不引入 Geist/Manrope 等 webfont。

## 3. 已确认决策

| 项目 | 决策 |
|---|---|
| 改造对象 | 新建公开落地页 |
| 受众 | 内部/个人使用；页面可公开分享，但没有自助注册 |
| 唯一动作 | 登录研究工作台 |
| 设计方向 | 品牌优先混合：保留暖奶油、墨黑、信号橙；采纳 skill 的结构、文案、字号阶梯、间距、动效曲线 |
| SEO | 仅落地页可索引；本地验证 meta、OG、robots、JSON-LD；不做 canonical 和 sitemap |
| 入口 | 未登录访问 SPA 路由时整页跳转 `/welcome/?next=<原路径>`；`/login` 仍可直接访问 |
| 品牌 | `Backing` + 中文副标 `A 股研究台` |
| 字体 | 干净系统栈，去掉 Roboto、Arial、Helvetica |
| 主 CTA | 墨黑胶囊按钮；橙色只做信号点缀 |
| 法律页面 | 隐私 + 条款两个极简静态页，footer 链接 |
| 截图 | Dashboard + 策略回测；Playwright mock 数据截图，标注“真实界面，示例数据” |

## 4. 用户流程

### 4.1 未登录访客

1. 访客打开 `/`、`/stocks/600519` 或其他 app 路由。
2. SPA 探测会话失败，进入未认证状态。
3. 浏览器整页跳转到 `/welcome/?next=%2Fstocks%2F600519`。
4. 访客阅读落地页，点击“登录研究工作台”。
5. 跳转到 `/login?next=%2Fstocks%2F600519`。
6. 登录成功后回到 `/stocks/600519`；没有 `next` 时回到 `/`。

### 4.2 直接访问 `/login`

1. 访客直接打开 `/login`。
2. 不被重定向到 `/welcome/`，正常显示登录表单。
3. 登录后回到 `next` 指定路径，或回到 `/`。
4. 登录页提供“了解 Backing”链接回到 `/welcome/`。

### 4.3 已登录用户

1. 已登录用户访问 `/`，直接看到仪表盘。
2. 已登录用户访问 `/welcome/`，仍然看到公开落地页；点击登录 CTA 后，SPA 的 `/login` 路由会把已登录用户送回 `/`。

## 5. 页面结构与文案

页面类型按 skill A3 选择 **Type A：经典 Hero + 分段论证**，做精简版，避免 12 段模板感。

### 5.1 导航

浮动胶囊导航，固定在页面顶部，半透明背景 + backdrop blur，居中，最大宽度 760px。

链接：

- 功能 → `#features`
- 工作原理 → `#how-it-works`
- 边界 → `#boundary`
- 常见问题 → `#faq`
- 登录 → `/login`（保留 `next` 参数）

移动端：

- 汉堡按钮打开全屏面板，不显示小型下拉菜单。
- 面板背景为暖奶油色高不透明度 + blur。
- 链接按阅读顺序 60ms 错峰进入，总时长不超过 400ms。
- 打开后焦点移到关闭按钮，Tab 焦点圈定在面板内，Escape 关闭，关闭后焦点回到汉堡按钮。

当前所在 section 用橙色小圆点或下划线指示，并通过 `aria-current` 暴露给辅助技术。

### 5.2 Hero

文案：

- Eyebrow：`A 股研究 · 回测 · 模拟交易`
- H1：`从 K 线到模拟成交，把 A 股研究跑成一条可复现的链路`
- 副标题：`同步行情与日线，跑 13 个内置策略的回测和参数优化，用 DeepSeek 做多阶段分析，最后在模拟盘验证。所有交易都是模拟盘，不接券商。`
- 主 CTA：`登录研究工作台`
- 次链接：`看看工作流` → `#how-it-works`
- 风险逆转：`无需绑定券商账户。所有成交都在模拟盘。`
- 证据条：`数据源 baostock / mootdx · 13 个内置策略 · 统一回测引擎 · 模拟盘 T+1`

布局：

- H1 与副标题最大宽度 680px。
- 桌面端 H1 48px，移动端 30px；359px 以下用 24px，保证三行换行处不被拆词。
- 主 CTA 与次链接在同一行；移动端换行，主 CTA 在上。
- Hero 视觉为 Dashboard 截图，放在浏览器窗口框里；截图下方标注 `Backing 仪表盘 · 真实界面，示例数据`。
- H1 使用浅色主题文字渐变 `#141413 → #6f6a64`；不支持 `background-clip: text` 时回退为纯墨黑。
- 背景保持纯暖奶油色，不使用背景渐变。

### 5.3 标签揭示区

放在 Hero 之后、能力区之前，作为独立的视觉停顿。

文案（两句话，分三行呈现）：

- 第一行：`先回测，再相信。`
- 第二行：`每一个策略假设，`
- 第三行：`都值得放进数据里跑一遍。`

行为：

- 字号 36px 至 60px 之间，按 Tailwind 阶梯落到 48px 桌面 / 36px 移动。
- 文字初始为 30% 透明度，随滚动逐字过渡到 100%。
- 逐字触发使用每个字符的 `IntersectionObserver`，不做无节流的 `window` 滚动监听。
- 过渡使用 `cubic-bezier(0.22, 1, 0.36, 1)`，每字 300ms 至 500ms。
- `prefers-reduced-motion: reduce` 时直接显示全文，不做逐字动画。

渐进增强：在 `<head>` 的早期内联脚本里给 `<html>` 加 `js` 类；逐字透明度和滚动揭示样式只在 `html.js` 下生效。JS 不可用时，标签揭示和所有 section 直接以完整不透明度显示。

### 5.4 能力区

标题：`把研究流程里的重复动作收进一个系统`

四项能力，每项一个 Phosphor 内联 SVG 图标：

1. **数据到回测，一条链路**
   股票列表、日线、实时行情和技术指标都在同一个库里，回测直接读数据库，不用在脚本之间搬 CSV。
2. **13 个内置策略，参数可以搜**
   趋势、反转、突破三类策略；网格搜索参数组合，结果落库，直接对比净值、回撤和逐笔交易。
3. **AI 分析，结论有出处**
   技术面、消息面、风险、策略、决策五个阶段；事实来自工具网关的 `source_id` / `as_of`，不让模型编造行情。
4. **模拟盘按 A 股规则成交**
   没有审批就不下单；T+1、涨跌停、手续费和滑点都按规则模拟。

布局：

- 桌面端 2×2 网格，移动端单列。
- 卡片表面使用 `#fcfbfa`，四周完整 1px 边框，圆角 16px，内边距 24px 或 32px。
- 不使用单边边框，不使用背景渐变。

### 5.5 工作流

标题：`从数据到模拟盘，三步`

1. **同步数据**
   拉取股票列表和日线，实时行情按需获取；数据源不可达时明确返回空或 503，不假装有数据。
2. **选策略，跑回测**
   调参数或交给优化器做网格搜索；看净值曲线、最大回撤和逐笔交易。
3. **用 AI 写报告，再进模拟盘**
   生成多阶段研究报告，把结论放进模拟盘跟踪；审批通过后才成交。

布局：桌面端三列，移动端单列；步骤编号用 12px 标签 + 24px 标题；不使用装饰性大数字。

### 5.6 真实界面

标题：`真实界面，示例数据`

两张截图，均放在浏览器窗口框中：

1. **Dashboard**
   图注：`仪表盘：指数、自选股和当日走势 · 真实界面，示例数据`
   Alt：`Backing 仪表盘界面，展示指数卡片、自选股表格和当日走势图`
2. **策略回测**
   图注：`策略回测：净值曲线、回撤和逐笔交易 · 真实界面，示例数据`
   Alt：`Backing 策略回测界面，展示净值曲线、回撤指标和逐笔交易表`

说明：

- 截图来自真实前端，数据通过 Playwright 路由拦截注入，不是实时行情。
- 页面必须明确标注“示例数据”，不能让访客误以为是实时收益。
- 截图外层卡片圆角 16px，内部图片圆角 8px，符合嵌套半径公式（16 − 8 = 8）。

### 5.7 边界说明

标题：`先说清楚边界`

引导句：`这是一个研究工具，不是荐股服务，也不是实盘交易终端。`

三条：

1. **不接实盘。** 没有券商接口，所有成交都在模拟盘。
2. **不承诺收益。** 回测是历史数据上的推演，不代表未来表现。
3. **不替你做决定。** AI 输出是研究材料，不是投资建议。

这一节替代虚假的客户证言和收益截图，作为信任建立方式。

### 5.8 FAQ

使用原生 `<details>` / `<summary>`，答案始终在 HTML 中，保证可索引和键盘可操作。

1. **这是实盘交易系统吗？**
   不是。系统没有券商接口，所有下单和成交都发生在模拟盘。
2. **需要自己准备数据源吗？**
   需要配置 baostock 或 mootdx；两者都不可达时，实时行情会明确返回空或 503，不会用旧数据冒充实时。
3. **支持哪些策略？可以写自己的吗？**
   内置 13 个策略，覆盖趋势、反转和突破；自定义策略继承 `Strategy` 并注册即可出现在策略列表里。
4. **AI 分析会编造数据吗？**
   行情、财务和新闻事实都通过工具网关获取，返回带 `source_id`、`as_of` 和 `vendor`；模型只负责组织结论。
5. **回测会有未来函数吗？**
   统一执行器按交易日推进，指标只使用当日及之前的数据；评估用例覆盖了前视偏差检查。
6. **怎么登录？API Key 存在哪里？**
   用 API Key 换取 8 小时的 HttpOnly 会话 Cookie；Key 不写入 localStorage，也不进入浏览器 bundle。
7. **数据存在哪里？重启会丢吗？**
   默认 SQLite，可切 MySQL；回测结果、交易明细和任务状态都落库，重启后可以恢复。
8. **手机上能用吗？**
   页面是响应式布局，移动端有独立的全屏导航；图表和表格在窄屏下会隐藏次要列。
9. **这些内容构成投资建议吗？**
   不构成。系统只用于研究和模拟，不提供任何收益承诺。

### 5.9 最终 CTA

标题：`把下一个策略假设放进数据里`

正文：`登录 Backing，从同步数据开始，跑一遍回测，再决定要不要相信它。`

按钮：`登录研究工作台` → `/login`（保留 `next` 参数）

下方重复风险逆转：`无需绑定券商账户。所有成交都在模拟盘。`

### 5.10 Footer

内容：

- 品牌：`Backing` + `A 股研究台`
- 一句话：`A 股研究、回测、AI 分析与模拟交易工作台。`
- 导航：功能、工作原理、边界、常见问题、登录
- 法律：隐私 → `/legal/privacy.html`；条款 → `/legal/terms.html`
- 免责声明：`仅供研究使用，不构成投资建议。所有交易均为模拟盘。`
- 版权：`© 2026 Backing`

## 6. 视觉系统

### 6.1 品牌与颜色

沿用现有品牌色，落地页 CSS 使用独立的 `--lp-*` 变量，避免改动 app tokens：

| Token | 值 | 用途 |
|---|---|---|
| `--lp-canvas` | `#f3f0ee` | 页面背景 |
| `--lp-surface` | `#fcfbfa` | 卡片、导航表面 |
| `--lp-ink` | `#141413` | 主文字、主按钮 |
| `--lp-ink-soft` | `#262627` | 按钮 hover |
| `--lp-muted` | `#696969` | 次要文字 |
| `--lp-tertiary` | `#77716b` | 元信息 |
| `--lp-accent` | `#cf4500` | 信号橙，仅用于小圆点、eyebrow 装饰线、强调标记 |
| `--lp-clay` | `#9a3a0a` | 深锈色，用于需要更高对比度的小字强调 |
| `--lp-border` | `rgba(20, 20, 19, 0.12)` | 完整边框 |
| `--lp-border-soft` | `rgba(20, 20, 19, 0.08)` | 卡片边框 |

规则：

- 页面背景保持纯色，不使用背景渐变。
- 唯一的渐变是 Hero H1 的文字渐变，不用于背景。
- 橙色不做大面积色块，不做主按钮背景。
- 正文与次要文字对比度满足 WCAG AA；橙色只用于装饰、eyebrow 或短标签，不用于长正文，也不用于主按钮背景。

### 6.2 字体与字号

字体栈：

```css
font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC',
  'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
```

明确不包含 Roboto、Arial、Helvetica、Open Sans、Inter。

字号严格落在 Tailwind 阶梯：

| 用途 | 桌面 | 移动 | 行高 |
|---|---|---|---|
| Hero H1 | 48px (`text-5xl`) | 30px (`text-3xl`) | 1 / 36px |
| 标签揭示 | 48px (`text-5xl`) | 36px (`text-4xl`) | 1 / 40px |
| Section 标题 | 36px (`text-4xl`) | 30px (`text-3xl`) | 40px / 36px |
| 卡片标题 | 20px (`text-xl`) | 20px (`text-xl`) | 28px |
| 正文 | 16px (`text-base`) | 16px (`text-base`) | 24px |
| 辅助文字 | 14px (`text-sm`) | 14px (`text-sm`) | 20px |
| Eyebrow / 标签 | 12px (`text-xs`) | 12px (`text-xs`) | 16px |
| 按钮 | 16px (`text-base`) | 16px (`text-base`) | 24px |

规则：

- 不使用斜体。
- 字重最高 600，不使用 700 以上或 black。
- H1、Section 标题使用 `text-wrap: balance`；正文使用 `text-wrap: pretty`。
- 文案中不使用连字符；需要停顿用逗号、句号或 `·`。
- 按钮文字不使用“了解更多”“提交”这类空泛词。

### 6.3 间距与圆角

间距只使用以下值：`0, 2, 4, 8, 12, 16, 24, 32, 40, 48, 64, 80, 96`。

- Section 纵向内边距：桌面 96px，移动 64px。
- 卡片内边距：24px；大卡片 32px。
- 按钮内边距：纵向 8px，横向 12px；最小高度 40px。
- 导航内边距：纵向 8px，横向 16px。

圆角只使用 Tailwind 值：`2, 4, 8, 12, 16, 24, 9999`。

- 卡片：16px；大容器：24px。
- 按钮、导航、标签：9999px。
- 嵌套半径：内层圆角 = 外层圆角 − 间距；结果不大于 2 时保持直角或不变。
- 示例：外层 16px、内边距 8px → 内层 8px。

### 6.4 布局

- 内容最大宽度 1120px；Hero 文字最大宽度 680px。
- 导航最大宽度 760px，固定在顶部 24px；移动端顶部 16px，左右 16px。
- 桌面端能力区 2×2 网格，工作流三列；移动端全部单列。
- 页面左右内边距：移动 16px，平板 24px，桌面 32px。
- 不允许横向滚动；所有图片 `max-width: 100%; height: auto`。

### 6.5 动效

基础曲线：

```css
--lp-ease: cubic-bezier(0.22, 1, 0.36, 1);
```

规则：

- 布局和位置变化 500ms；颜色和透明度 hover 300ms；不短于 200ms。
- 只动画 `transform` 和 `opacity`，不动画 `top`、`left`、`width`、`height`。
- 滚动揭示：section 进入视口时上移 32px 并淡入，600ms 至 800ms，只播放一次。
- 使用 `IntersectionObserver`，不使用无节流的 `window` 滚动监听。
- `prefers-reduced-motion: reduce` 时移除位移和逐字动画，只保留必要的透明度变化或直接显示。

### 6.6 图标

- 使用 Phosphor 风格的内联 SVG，线宽 1.5，尺寸 24px。
- 不新增图标库依赖。
- 在 HTML 注释中标注 `Icons: Phosphor Icons (MIT)`。
- app 内部继续使用 Ant Design 图标，不在本次范围内替换。

### 6.7 状态与可访问性

- 所有链接和按钮具备 hover、active、focus-visible 状态。
- Focus ring：`outline: 2px solid var(--lp-ink); outline-offset: 3px;`。
- 主按钮 active：`transform: scale(0.98)`；hover：`translateY(-1px)` 或背景变深。
- 页面顶部提供“跳到主内容”链接。
- 使用语义标签：`<nav>`、`<main>`、`<section>`、`<article>`、`<footer>`。
- 每张有意义的图片都有描述性 alt；装饰性 SVG 使用 `aria-hidden="true"`。
- FAQ 使用原生 `<details>` / `<summary>`。
- 移动端菜单：焦点圈定、Escape 关闭、关闭后焦点归还、打开时锁定 body 滚动。
- 当前导航 section 通过 `aria-current` 指示。
- 无死链：所有链接指向真实路径或存在的锚点。

## 7. 技术设计

### 7.1 实现路径

采用**纯静态页**：`frontend/public/welcome/` 下的 HTML/CSS/少量 JS，构建时由 Vite 原样复制到 `dist/welcome/`，由 `vite preview` 直接服务。

理由：

- HTML 源码包含全文案，爬虫不依赖 JS。
- 不进入主 bundle，不影响 `check-bundle.mjs` 的分包预算。
- 不新增 React 运行时或 npm 依赖。
- 静态页与 app 认证门禁解耦，`/welcome/` 天然公开。

备选路径（不在本轮实施）：

- Vite MPA + React 第二入口：适合以后落地页需要复杂交互或共享 React 组件。
- SPA 内 React 路由 + 预渲染插件：适合落地页需要和 app 共享布局，但复杂度和风险最高。

### 7.2 文件变更

新增：

- `frontend/public/welcome/index.html`
- `frontend/public/welcome/landing.css`
- `frontend/public/welcome/landing.js`
- `frontend/public/welcome/assets/dashboard.png`
- `frontend/public/welcome/assets/strategies.png`
- `frontend/public/welcome/assets/og-image.png`
- `frontend/public/legal/privacy.html`
- `frontend/public/legal/terms.html`
- `frontend/public/favicon.svg`
- `frontend/public/robots.txt`
- `frontend/scripts/capture-landing.mjs`（开发期截图脚本，不进入 dist）
- `frontend/scripts/og-template.html`（OG 图模板，不进入 dist）
- `frontend/src/utils/nextPath.ts`
- `frontend/src/utils/nextPath.test.ts`
- `frontend/e2e/landing.spec.ts`

修改：

- `frontend/index.html`：加 `<meta name="robots" content="noindex,nofollow">`；favicon 改为 `/favicon.svg`。
- `frontend/src/App.tsx`：未认证且不在 `/login`、`/welcome`、`/welcome/` 时，整页跳转 `/welcome/?next=<原路径>`。
- `frontend/src/pages/Login.tsx`：读取并校验 `next` 参数；登录后回到原目标页；加“了解 Backing”链接到 `/welcome/`。

不修改：

- `frontend/src/styles/*`
- `frontend/vite.config.ts`
- 后端、`backend/`、`TradingAgents-astock/`
- 现有 app 业务组件和路由结构
- 不新增 npm 依赖
- 不自动提交 git

### 7.3 路由与登录跳转

未认证跳转：

- 在 `App.tsx` 未认证分支中，用 `useEffect` 执行 `window.location.replace`。
- 条件：`authState === 'unauthenticated'` 且 `location.pathname` 不是 `/login`、`/welcome`、`/welcome/`。
- 目标：`/welcome/?next=${encodeURIComponent(location.pathname + location.search)}`。
- 跳转期间渲染“正在前往介绍页…”加载态，避免闪现登录表单。
- 不使用 React Router 的 `<Navigate>`，因为它不会加载 `/welcome/` 这个静态文档，可能造成客户端循环。

`next` 参数校验：

- 必须以 `/` 开头。
- 不能以 `//` 开头。
- 不能以 `/\` 开头。
- 不满足条件时回退到 `/`。
- 校验逻辑放在 `src/utils/nextPath.ts`，由 `Login.tsx` 和单元测试复用。

登录页：

- 优先读取 `?next=`；没有或非法时读取 `location.state.from`；再回退到 `/`。
- 登录成功后 `navigate(from, { replace: true })`。
- 新增“了解 Backing”链接，指向 `/welcome/`。

落地页：

- `landing.js` 读取 `next` 参数，校验后把它追加到所有 `/login` 链接。
- 没有 JS 时，登录链接仍然指向 `/login`，登录后回到 `/`；这是可接受的降级。

### 7.4 SEO

落地页 `<head>`：

- `<html lang="zh-CN">`
- `<title>Backing｜A 股研究、回测与模拟交易工作台</title>`
- `<meta name="description" content="同步 A 股行情与日线，跑 13 个内置策略的回测和参数优化，用 DeepSeek 做多阶段分析，在模拟盘验证。仅供研究，不构成投资建议。">`
- `<meta name="robots" content="index,follow">`
- Open Graph：`og:type=website`、`og:title`、`og:description`、`og:image=/welcome/assets/og-image.png`、`og:locale=zh_CN`、`og:site_name=Backing`
- Twitter：`summary_large_image`
- JSON-LD：`SoftwareApplication` + `FAQPage`
- 不设置 canonical，不生成 sitemap；上线前由部署者补充生产域名、canonical 和 sitemap。

app shell：

- `frontend/index.html` 加 `noindex,nofollow`。
- 所有业务路由继承 app shell 的 noindex。

`robots.txt`：

```txt
User-agent: *
Allow: /welcome/
Disallow: /
```

法律页面：

- `/legal/privacy.html` 和 `/legal/terms.html` 都加 `noindex,follow`。
- 提供返回 `/welcome/` 的链接。

结构化数据：

- `SoftwareApplication`：name、description、applicationCategory、operatingSystem；不写价格、评分或用户数。
- `FAQPage`：与页面可见 FAQ 一一对应，答案使用纯文本。
- 修改可见 FAQ 时必须同步修改 JSON-LD。

### 7.5 截图与 OG 图

截图脚本 `frontend/scripts/capture-landing.mjs`：

- 假设 `npm run dev` 已运行在 `http://localhost:5174`。
- 使用 Playwright Chromium。
- 拦截 `/api/v1/auth/me` 返回 `{ authenticated: true }`。
- 拦截 Dashboard 和策略回测所需的 `/api/v1/**` 数据接口，返回固定 fixture。
- 设置 `deviceScaleFactor: 2`，视口 1440×900；截图后按显示宽度 720px 使用。
- 输出：
  - `frontend/public/welcome/assets/dashboard.png`
  - `frontend/public/welcome/assets/strategies.png`
- 如果某个页面的接口 mock 成本过高，第二张改用 Agent 分析页，并在交付说明中记录原因。
- 截图只使用示例数据，不包含真实 API Key、Cookie、个人信息或本地路径。

OG 图：

- 1200×630 PNG。
- 内容：暖奶油背景、Backing 字标、H1 摘要、抽象净值曲线、`A 股研究台` 副标。
- 使用 Playwright 对一个 1200×630 的本地 HTML 模板截图生成，模板不进入 dist。
- 输出 `frontend/public/welcome/assets/og-image.png`。
- 本地验证阶段使用相对路径 `/welcome/assets/og-image.png`；上线前需要改成生产域名下的绝对 URL。

图片规则：

- Hero 截图 `loading="eager"`、`fetchpriority="high"`、显式宽高。
- 第二张截图 `loading="lazy"`、`decoding="async"`、显式宽高。
- 单张图片目标小于 300KB；如果 PNG 超过预算，改用 JPEG 90% 或降低到 1x 分辨率。

### 7.6 构建与服务

- `frontend/public/welcome/` 由 Vite 原样复制到 `dist/welcome/`。
- `vite preview` 静态服务 `dist/`；`/welcome/` 应解析到 `dist/welcome/index.html`。
- 构建后验证：
  - `curl -I http://localhost:5174/welcome/` 返回 200。
  - `curl -s http://localhost:5174/welcome/ | grep "从 K 线到模拟成交"` 能命中，证明文案在 HTML 源码中。
  - `curl -I http://localhost:5174/login` 返回 200 且是 SPA shell。
- 如果 `vite preview` 不对 `/welcome/` 做目录索引，改用 Vite MPA 入口：
  - 在 `vite.config.ts` 增加 `build.rollupOptions.input`，把 `welcome/index.html` 作为第二入口。
  - 这只影响构建配置，不改视觉设计。
- 主 bundle 不变；`check-bundle.mjs` 不需要修改。

## 8. 内容真实性与合规

- 不编造客户、logo、用户数、收益、评价或媒体引用。
- 不使用“颠覆”“赋能”“极致”“世界级”等空话。
- 不承诺收益，不暗示回测结果代表未来表现。
- 所有产品数字来自代码或文档：13 个内置策略、5 个分析阶段、8 小时会话、T+1、baostock / mootdx。
- 截图必须标注“真实界面，示例数据”。
- 页面底部保留免责声明。
- 隐私页说明：
  - 落地页本身不加载统计脚本、不设置 Cookie。
  - 登录后 app 使用 HttpOnly 会话 Cookie 和 CSRF Cookie。
  - 数据存储在部署者配置的 SQLite 或 MySQL 中。
  - 没有第三方分析或广告。
- 条款页说明：
  - 仅供研究和模拟。
  - 不接实盘，不构成投资建议。
  - 不提供任何明示或暗示的担保。
  - 用户自行负责 API Key 和部署环境安全。
  - 数据和行情可能延迟或不可用。

## 9. 测试与验收

### 9.1 自动化测试

`nextPath` 单元测试：

- 接受 `/`、`/stocks/600519`、`/stocks?code=600519`。
- 拒绝 `//evil.com`、`https://evil.com`、`/\evil.com`、空字符串、`javascript:alert(1)`。

Playwright `landing.spec.ts`：

1. 访问 `/welcome/`，H1、主 CTA、FAQ 9 条、footer 法律链接都存在。
2. 主 CTA 的 `href` 是 `/login`；带 `?next=` 访问时，CTA 带上同样的 `next`。
3. 移动端 375px：汉堡按钮打开全屏菜单，Escape 关闭，焦点回到汉堡按钮。
4. 375 / 768 / 1440 三个宽度无横向滚动。
5. 模拟 `prefers-reduced-motion: reduce`，标签文字可见，动画样式不隐藏内容。
6. 未登录访问 `/stocks`（拦截 `/api/v1/auth/me` 返回未认证），最终 URL 是 `/welcome/?next=%2Fstocks`。
7. 直接访问 `/login?next=%2Fstocks`，登录成功后回到 `/stocks`（拦截登录接口）。

现有命令：

- `npm run typecheck`
- `npm run lint`
- `npm run format:check`
- `npm run build`
- `npm test`
- `npm run test:e2e`

### 9.2 手工验收

- 键盘 Tab 走完导航、CTA、FAQ、footer；focus ring 清晰可见。
- 375 / 768 / 1024 / 1440 无横向滚动；Hero 文字不溢出 680px。
- 关闭 JS 后，落地页文案、FAQ、法律链接仍然可见。
- `view-source` 能看到 H1 和 FAQ 答案。
- Lighthouse：Performance、Accessibility、Best Practices、SEO 均无明显失败项；不追求满分。
- 截图和 OG 图没有真实 Key、Cookie、个人信息或本地绝对路径。
- 页面没有背景渐变（Hero 文字渐变除外）、没有单边卡片边框、没有斜体、没有超粗字。
- 所有字号和间距落在本文档的阶梯内。

### 9.3 完成定义

- 上述自动化测试全部通过。
- 手工验收项全部通过。
- 未登录访问 app 路由会进入 `/welcome/`，登录后回到原目标页。
- `frontend/index.html` 带 `noindex`；`/welcome/` 带 `index,follow`。
- 主 bundle 预算检查通过，落地页不引入 React 或 AntD。

## 10. 风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| `vite preview` 不对 `/welcome/` 做目录索引 | 落地页打不开或落回 SPA | 构建后用 curl 验证；失败则改用 Vite MPA 入口 |
| `/welcome` 不带斜杠被 SPA 捕获 | 可能循环跳转 | `App.tsx` 排除 `/welcome` 和 `/welcome/`；链接统一使用带斜杠的 `/welcome/` |
| 截图 mock 成本高或页面状态不稳定 | 第二张截图延期 | 第二张改用 Agent 分析页；仍不行则先用 Dashboard 单图，并记录缺口 |
| 静态页 CSS 与 app tokens 漂移 | 品牌不一致 | 在 `landing.css` 顶部注释指向 `src/styles/tokens.css`；改品牌色时同步两处 |
| 无生产域名导致 canonical/sitemap 缺失 | 上线后搜索引擎收录不完整 | 本文档明确列为上线前补充项；不伪造 canonical |
| OG 图使用相对 URL | 部分社交平台不解析 | 本地验证阶段接受；上线前改成绝对 URL |
| 中文字体在不同系统差异 | 排版观感不一致 | 使用 PingFang SC / Microsoft YaHei / Noto Sans CJK fallback；字号和行高固定 |
| 落地页与 app 登录态不同步 | 已登录用户点登录 CTA 被送回 `/` | 这是预期行为；落地页不依赖登录态 |

## 11. 上线前补充（本地验证阶段不做）

1. 生产域名确定后：
   - 在落地页加 `<link rel="canonical" href="https://<domain>/welcome/">`。
   - 把 `og:image` 改成绝对 URL。
   - 生成 `public/sitemap.xml`，只收录 `/welcome/`。
   - 在 `robots.txt` 加 `Sitemap: https://<domain>/sitemap.xml`。
2. 如果部署从 `vite preview` 换成 Nginx/Caddy：
   - 配置 `/welcome/` 的静态目录索引。
   - 保持 `/login` 和其他 SPA 路由的 fallback 到 `index.html`。
3. 如果未来加统计或 Cookie：
   - 更新隐私页。
   - 视司法辖区决定是否加 Cookie 同意。
4. 如果未来加自助注册或定价：
   - 重新评估落地页结构和 CTA。
   - 需要真实运营承接，不在本轮范围内。

## 12. 不做清单

- 不编造客户、logo、用户数、收益、评价或媒体引用。
- 不做收益承诺或投资建议。
- 不接实盘、不接券商。
- 不重构 app 全局设计系统。
- 不替换 Ant Design 图标。
- 不新增字体或图标依赖。
- 不实现自助注册、账号体系、支付、预约演示。
- 不做 canonical 和 sitemap。
- 不自动提交 git。
