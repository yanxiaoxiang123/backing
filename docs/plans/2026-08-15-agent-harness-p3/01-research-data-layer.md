# 01 研究数据层

**交付**：新闻、公告、财报摘要、基准指数四类确定性数据服务 + SQLite 缓存表 + 网关工具 `event.news`、`event.announcement`、`fundamental.financials`、`market.index_kline`。

**范围**：
- 数据源：akshare（个股新闻、公告列表、财报摘要）；baostock（指数日线，如 sh.000300）。
- 缓存表：按（工具名、参数、as_of 生效窗口）键控；条目携带 `source_id/as_of/vendor/data_version`；命中直接返回，未命中外呼后写缓存。
- 网关工具输出统一 envelope（`{ok, data, source_id, as_of, vendor}`）；只读权限；参数 schema 严格校验。
- 外呼失败：返回明确"未接入/获取失败"错误，计入调用结果，不伪造数据。

**验收**：
- pytest：缓存命中/失效、证据五元组齐全、外呼 mock 化、失败路径返回明确错误。
- 手动 smoke：真实调用一次新闻/公告/财报/指数接口，确认可返回（网络脆弱则记录并 mock 验证）。

**阻塞**：None
**委派**：eligible（独立新模块，接缝稳定）
