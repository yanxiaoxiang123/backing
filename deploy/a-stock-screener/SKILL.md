---
name: a-stock-screener
description: A股量化选股工具。根据估值、盈利、技术、资金等多维度综合筛选A股股票，推荐最值得入手的股票。使用BaoStock或AKShare获取数据。当用户说"帮我选股"、"筛选股票"、"A股推荐"、"什么股票值得买"时触发。
---

# A股量化选股器

## 工作流程

### 第一步：获取数据

**数据源优先级：**
1. BaoStock（主要，推荐）
2. AKShare（备用）

```python
import baostock as bs
import pandas as pd

# BaoStock 获取K线
bs.login()
rs = bs.query_history_k_data_plus(
    code="sz.000001",
    fields="date,open,high,low,close,volume,amount,turn",
    start_date='2025-01-01',
    end_date='20260324',
    frequency="d"
)
data = []
while rs.error_code == '0' and rs.next():
    data.append(rs.get_row_data())
df = pd.DataFrame(data, columns=['日期','开盘','最高','最低','收盘','成交量','成交额','换手率'])
bs.logout()
```

```python
# AKShare 获取K线
import akshare as ak
df = ak.stock_zh_a_hist(symbol="000001", period="daily", start_date="20250101", adjust="qfq")
```

### 第二步：多维度筛选

**价值投资首选：**
- PE：5-15倍
- PB：<2倍
- 股息率：>3%

**成长股：**
- ROE：>10%
- 净利润增长：>5%

**技术面：**
- 均线多头排列（MA5>MA10>MA20）
- MACD 金叉
- 成交量放大

### 第三步：综合评分

对候选股票按以下维度打分：
1. 估值得分（PE越低越高）
2. 盈利得分（ROE越高越高）
3. 技术得分（信号越多越高）
4. 资金得分（股息率越高越高）

### 第四步：深度分析

对评分最高的前3只股票进行快速分析：
- market-analyst → 技术面确认
- fundamentals-analyst → 基本面确认
- risk-analysts → 风险评估

### 第五步：输出报告

```
🎯 A股精选三只股票

1. [股票名称]（代码）
   - 推荐理由：3-5点
   - 目标价：
   - 止损价：
   - 风险等级：

2. ...

3. ...
```

## 报告模板

```markdown
# 🎯 A股量化选股报告
**筛选日期：** {日期}
**数据来源：** {BaoStock/AKShare}

---

## 🏆 第一名：[股票名称]（{代码}）

| 指标 | 数值 | 评价 |
|------|------|------|
| 现价 | XX元 | - |
| PE | Xx | ✅/❌ |
| ROE | XX% | ✅/❌ |
| 股息率 | XX% | ✅/❌ |
| 技术信号 | XXX | ✅/❌ |

- **推荐理由：**
  - 1. ...
  - 2. ...
- **目标价：** XX元（+XX%）
- **止损价：** XX元（-XX%）
- **风险等级：** ⭐⭐⭐

---

## 对比总览

| 股票 | 现价 | PE | 股息率 | 目标价 | 上涨空间 |
|------|------|----|--------|--------|---------|
| ... | ... | ... | ... | ... | ... |

---

⚠️ **风险提示：** 仅供参考，不构成投资建议
```

## 注意事项

1. **数据校验**：获取数据后检查是否为空
2. **备用数据源**：BaoStock失败时尝试AKShare，反之亦然
3. **风险提示**：每份报告必须包含"仅供参考，不构成投资建议"
4. **分批发送**：每完成一步立即发送报告给用户
