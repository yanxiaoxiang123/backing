# 量化交易系统全面升级规划

## 项目概述

将现有的A股量化系统升级为完整的量化交易平台，支持策略研究、交易执行和组合管理。

## 当前状态

- **前端**: React 18 + TypeScript + Vite + Ant Design + ECharts + React Router v6
- **后端**: FastAPI + SQLAlchemy + MySQL
- **数据源**: Baostock (A股数据)

## 升级架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (React)                         │
├──────────┬──────────┬──────────┬──────────┬──────────────────┤
│ Dashboard│ Strategy │ Trading  │ Portfolio│ Settings         │
│ 仪表盘   │ 策略研究 │ 交易执行 │ 组合管理 │ 系统设置         │
└──────────┴──────────┴──────────┴──────────┴──────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Backend API (FastAPI)                       │
├──────────┬──────────┬──────────┬──────────┬──────────────────┤
│  Stock   │ Backtest │ Trading  │ Portfolio│ Auth & Users     │
│ 数据服务 │ 回测引擎 │ 交易服务 │ 组合服务 │ 用户认证         │
└──────────┴──────────┴──────────┴──────────┴──────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Data Layer (MySQL)                         │
├──────────┬──────────┬──────────┬──────────┬──────────────────┤
│ Stocks   │ Backtest │ Orders   │ Positions│ Users & Config   │
│ 股票数据 │ 回测结果 │ 委托记录 │ 持仓信息 │ 用户配置         │
└──────────┴──────────┴──────────┴──────────┴──────────────────┘
```

---

## Phase 1: 基础架构升级

### 1.1 技术栈升级 (保持现有技术栈，针对性增强)

| 项目 | 当前 | 升级建议 |
|------|------|----------|
| 数据库 | MySQL | 保持MySQL，可选PostgreSQL |
| 状态管理 | useState | 可选 Zustand (复杂状态) |
| HTTP Client | fetch | 可选 Axios + React Query |
| UI组件 | Ant Design | 保持 + 自定义主题 |
| 图表 | ECharts | 保持，扩展图表类型 |
| 实时推送 | 无 | WebSocket |

### 1.2 项目结构优化

```
backend/
├── app/
│   ├── api/              # API路由
│   │   ├── routes/
│   │   │   ├── stocks.py
│   │   │   ├── backtest.py
│   │   │   ├── trading.py
│   │   │   ├── portfolio.py
│   │   │   └── users.py
│   │   └── dependencies.py
│   ├── core/             # 核心配置
│   │   ├── config.py
│   │   ├── security.py
│   │   └── database.py
│   ├── models/           # 数据模型
│   │   ├── stock.py
│   │   ├── backtest.py
│   │   ├── trading.py
│   │   └── user.py
│   ├── schemas/          # Pydantic schemas
│   ├── services/         # 业务逻辑
│   │   ├── data/        # 数据服务
│   │   ├── strategy/    # 策略服务
│   │   ├── backtest/    # 回测引擎
│   │   ├── trading/     # 交易服务
│   │   └── portfolio/   # 组合服务
│   └── utils/           # 工具函数

frontend/
├── src/
│   ├── components/      # 通用组件
│   │   ├── charts/
│   │   ├── forms/
│   │   ├── layout/
│   │   └── ui/
│   ├── features/        # 功能模块
│   │   ├── dashboard/
│   │   ├── stocks/
│   │   ├── strategies/
│   │   ├── backtest/
│   │   ├── trading/
│   │   ├── portfolio/
│   │   └── settings/
│   ├── hooks/           # 自定义hooks
│   ├── services/        # API服务
│   ├── stores/          # Zustand stores
│   ├── types/           # TypeScript类型
│   └── utils/           # 工具函数
```

---

## Phase 2: 策略研究模块

### 2.1 策略引擎增强

#### 新增策略类型

```python
# 策略接口
class Strategy(ABC):
    @abstractmethod
    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """生成交易信号"""
        pass

    @abstractmethod
    def get_parameters(self) -> Dict[str, Parameter]:
        """获取策略参数定义"""
        pass
```

| 策略名称 | 描述 | 参数 |
|----------|------|------|
| MA Cross | 均线交叉策略 | short_period, long_period |
| Mean Reversion | 均值回归 | period, std_threshold |
| Momentum | 动量策略 | period, threshold |
| Breakout | 突破策略 | period, atr_multiplier |
| RSI Reversal | RSI反转 | rsi_period, oversold, overbought |
| MACD Cross | MACD交叉 | fast, slow, signal |
| Dual Thrust | 双枢轴策略 | k_up, k_down |

### 2.2 策略参数优化

```python
# 参数优化服务
class ParameterOptimizer:
    def grid_search(self, strategy, data, param_grid):
        """网格搜索最优参数"""

    def random_search(self, strategy, data, n_iter):
        """随机搜索"""

    def bayesian_optimization(self, strategy, data):
        """贝叶斯优化"""
```

### 2.3 因子库

```python
# 技术因子
class TechnicalFactors:
    # 趋势因子
    - SMA, EMA, WMA, HullMA
    - MACD, Signal, Histogram
    - ADX, +DI, -DI

    # 动量因子
    - RSI, Stochastic, CCI
    - ROC, Momentum
    - Williams %R

    # 波动率因子
    - ATR, Bollinger Bands
    - Standard Deviation

    # 成交量因子
    - OBV, VWAP
    - Volume MA, Volume Ratio
```

### 2.4 前端策略编辑器

- 策略模板选择
- 参数滑动条配置
- 实时信号预览
- 策略代码编辑器 (可选)

---

## Phase 3: 回测系统增强

### 3.1 回测引擎升级

```python
class BacktestEngine:
    def __init__(self, initial_capital, commission_rate=0.0003):
        self.capital = initial_capital
        self.commission_rate = commission_rate
        self.positions = {}
        self.trades = []
        self.equity_curve = []

    def run(self, signals, data):
        """执行回测"""
        # 逐K线回测
        # 支持做多/做空
        # 精确计算手续费、滑点
        # 记录完整交易日志
```

### 3.2 回测指标

| 指标 | 描述 |
|------|------|
| Total Return | 总收益率 |
| Annual Return | 年化收益率 |
| Sharpe Ratio | 夏普比率 |
| Sortino Ratio | 索提诺比率 |
| Calmar Ratio | 卡玛比率 |
| Max Drawdown | 最大回撤 |
| Win Rate | 胜率 |
| Profit Factor | 盈利因子 |
| Avg Win/Loss | 平均盈亏比 |
| Recovery Factor | 恢复因子 |

### 3.3 回测分析图表

- 权益曲线图
- 回撤图
- 收益分布图
- 月度收益热力图
- 交易分布图

---

## Phase 4: 交易执行模块

### 4.1 模拟交易

```python
class PaperTrading:
    """模拟交易引擎"""

    def __init__(self, initial_capital):
        self.cash = initial_capital
        self.positions = {}
        self.orders = []
        self.closed_trades = []

    def place_order(self, symbol, quantity, direction):
        """下单"""

    def cancel_order(self, order_id):
        """撤单"""

    def get_quote(self, symbol):
        """获取实时行情"""

    def update_positions(self):
        """更新持仓"""
```

### 4.2 实盘对接 (预留接口)

```python
class BrokerAdapter(ABC):
    """券商接口适配器"""

    @abstractmethod
    def login(self, account, password):
        pass

    @abstractmethod
    def place_order(self, order):
        pass

    @abstractmethod
    def cancel_order(self, order_id):
        pass

    @abstractmethod
    def get_positions(self):
        pass

    @abstractmethod
    def get_account(self):
        pass
```

### 4.3 交易信号

- 策略信号监控面板
- 信号提醒 (WebSocket推送)
- 信号历史记录

---

## Phase 5: 组合管理模块

### 5.1 持仓管理

```python
class Position:
    symbol: str
    quantity: int
    avg_cost: float
    current_price: float
    market_value: float
    unrealized_pnl: float
    realized_pnl: float

class Portfolio:
    positions: List[Position]
    cash: float
    total_value: float
    total_pnl: float
    daily_return: float
```

### 5.2 风险管理

```python
class RiskManager:
    def check_position_limit(self, symbol, quantity):
        """检查持仓限制"""

    def check_drawdown_limit(self, portfolio):
        """检查回撤限制"""

    def calculate_var(self, portfolio, confidence=0.95):
        """计算VaR风险价值"""

    def calculate_portfolio_volatility(self):
        """计算组合波动率"""

    def set_stop_loss(self, symbol, price):
        """设置止损"""

    def set_take_profit(self, symbol, price):
        """设置止盈"""
```

### 5.3 绩效分析

| 指标 | 描述 |
|------|------|
| Total Return | 总收益 |
| Annualized Return | 年化收益 |
| Volatility | 波动率 |
| Sharpe Ratio | 夏普比率 |
| Sortino Ratio | 索提诺比率 |
| Max Drawdown | 最大回撤 |
| Beta | Beta系数 |
| Alpha | Alpha值 |
| Win Rate | 胜率 |
| Profit Factor | 盈利因子 |

### 5.4 收益归因

- 资产配置收益
- 选股收益
- 时机选择收益
- 行业贡献分析

---

## Phase 6: 数据服务增强

### 6.1 数据源扩展

| 数据类型 | 来源 | 用途 |
|----------|------|------|
| 股票日K | Baostock | 现有 |
| 股票分时 | Baostock/Tushare | 日内交易 |
| 财务数据 | Tushare | 基本面分析 |
| 因子数据 | 自建 | 因子研究 |
| 宏观数据 | 中国宏观 | 宏观择时 |
| 资金流向 | 每日更新 | 资金分析 |

### 6.2 数据API

```python
@router.get("/data/stocks")
def get_stocks(market: str = None, sector: str = None):
    """获取股票列表，支持行业筛选"""

@router.get("/data/kline")
def get_kline(symbol: str, period: str, start: date, end: date):
    """获取K线数据"""

@router.get("/data/fundamental")
def get_fundamental(symbol: str, report_type: str = "annual"):
    """获取财务数据"""

@router.get("/data/factors")
def get_factors(symbols: List[str], factors: List[str]):
    """获取因子数据"""
```

---

## Phase 7: 用户系统

### 7.1 认证授权

```python
class User(Base):
    id: int
    username: str
    email: str
    hashed_password: str
    role: str  # admin, trader, viewer
    created_at: datetime
    settings: JSON

# JWT认证
- 登录/注册
- Token刷新
- 权限控制
```

### 7.2 用户设置

- 主题切换 (浅色/深色)
- 通知偏好
- 交易设置 (默认手数、滑点设置)
- 界面布局保存

---

## Phase 8: 通知系统

### 8.1 通知类型

| 类型 | 渠道 | 触发条件 |
|------|------|----------|
| 交易信号 | App通知/邮件 | 策略产生信号 |
| 委托成交 | App通知 | 订单成交/撤单 |
| 风险预警 | App通知/短信 | 止损/风控触发 |
| 系统公告 | 站内信 | 系统更新 |

### 8.2 WebSocket实时推送

```python
# 实时数据推送
- 行情变化
- 信号触发
- 订单状态
- 持仓更新
- 风险预警
```

---

## 实施顺序

### 第一期 (4-6周): 基础架构
1. 项目结构重构
2. 技术栈升级
3. 用户系统基础
4. 数据服务增强

### 第二期 (4-6周): 策略研究
1. 策略引擎扩展
2. 因子库实现
3. 参数优化工具
4. 回测系统升级

### 第三期 (4-6周): 交易执行
1. 模拟交易引擎
2. 风控系统
3. 订单管理
4. 实时信号推送

### 第四期 (4-6周): 组合管理
1. 持仓面板
2. 绩效分析
3. 收益归因
4. 报表导出

---

## 技术选型 (与现有项目保持一致)

### 前端
- React 18 + TypeScript
- Vite (构建工具)
- Ant Design (UI组件库)
- ECharts / echarts-for-react (图表)
- React Router v6 (路由)
- 可选增强: Zustand, Axios, React Query

### 后端
- FastAPI
- SQLAlchemy
- MySQL (当前) / PostgreSQL (可选)
- Baostock (数据源)
- 可选增强: Celery (异步任务), Redis (缓存), WebSocket (实时推送)

### DevOps (可选)
- Docker / Docker Compose
- GitHub Actions (CI/CD)

---

## 风险与挑战

1. **数据质量**: Baostock数据可能有延迟，需要考虑数据清洗
2. **回测精度**: 真实交易有滑点、手续费差异，回测结果需谨慎对待
3. **实盘风险**: 实盘对接需要券商API，需考虑接口稳定性和合规性
4. **性能**: 大量K线数据计算需要优化，可考虑预计算和缓存
