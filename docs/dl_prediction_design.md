# DL 预测系统实现规划

## 一、需求概述

### 功能需求
1. **预测功能**: 使用 LSTM+Finance-Llama 模型预测未来5天收盘价
2. **可视化**: K线图 + 预测折线图（历史和预测用不同颜色区分）
3. **回测功能**: 基于预测结果进行回测，输出收益率、交易记录等

### 模型信息
- **模型文件**: `E:\Y\Y2\Project_try\backing\backend\models\llm\ceshi\*.pth`
- **Finance-Llama**: `E:\Y\Y2\Project_try\backing\backend\models\llm\Finance-Llama-8B`
- **输入特征**: 19个 (open, high, low, volatility_20, daily_range, volume_change, macd, rsi, ma5, ma20, ema12, ema26, momentum, vol_ma5, atr, obv, bollinger_upper, bollinger_lower, price_volume_ratio)
- **预测目标**: 未来5天收盘价
- **时间步长**: 60天 (time_steps=60)

---

## 二、架构设计

```
┌─────────────────────────────────────────────────────────────────┐
│                         前端 (Frontend)                         │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  DLPrediction.tsx                                       │  │
│  │  - 股票选择器                                           │  │
│  │  - 预测按钮 / 回测按钮                                  │  │
│  │  - K线图 + 预测折线图 (ECharts)                         │  │
│  │  - 回测结果展示                                         │  │
│  └─────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      后端 API (FastAPI)                        │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  /api/dl/predict     - 预测未来5天价格                  │   │
│  │  /api/dl/backtest   - 回测                             │   │
│  │  /api/dl/strategies - 获取DL策略列表                   │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   服务层 (Services)                            │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐   │
│  │ model_loader   │  │ predictor      │  │ backtest      │   │
│  │ - 加载.pt模型  │  │ - 特征计算     │  │ - 交易策略    │   │
│  │ - 加载Llama   │  │ - 模型推理     │  │ - 回测执行    │   │
│  │ - 设备管理    │  │ - 结果反归一化 │  │ - 指标计算    │   │
│  └────────────────┘  └────────────────┘  └────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 三、文件结构

```
backing/backend/
├── app/
│   ├── services/
│   │   ├── dl_prediction/          # [新建] DL预测服务
│   │   │   ├── __init__.py
│   │   │   ├── model_loader.py     # 模型加载器
│   │   │   ├── features.py        # 19个技术指标
│   │   │   ├── predictor.py       # 预测服务
│   │   │   └── backtest.py        # 回测逻辑
│   │   └── ...
│   ├── api/
│   │   ├── dl_prediction.py       # [新建] API接口
│   │   └── ...
│   └── config.py                  # [修改] 添加配置
│
└── models/llm/
    ├── ceshi/                     # 你的模型目录
    │   ├── *.pth                  # 模型权重
    │   ├── scaler_X.pkl           # 特征标准化器
    │   └── scaler_y.pkl            # 目标标准化器
    └── Finance-Llama-8B/           # Finance-Llama 模型
```

```
backing/frontend/src/
├── pages/
│   ├── DLPrediction.tsx           # [新建] DL预测页面
│   └── ...
├── services/
│   └── api.ts                     # [修改] 添加API调用
└── types/
    └── index.ts                   # [修改] 添加类型定义
```

---

## 四、核心模块设计

### 4.1 配置 (config.py)

```python
# 新增配置项
DL_MODEL_PATH: str = "E:/Y/Y2/Project_try/backing/backend/models/llm/ceshi"
DL_LLAMA_PATH: str = "E:/Y/Y2/Project_try/backing/backend/models/llm/Finance-Llama-8B"
DL_MODEL_NAME: str = "best_model.pth"  # 模型文件名
DL_TIME_STEPS: int = 60
DL_HIDDEN_SIZE: int = 256
DL_NUM_LAYERS: int = 2
DL_OUTPUT_SIZE: int = 5
DL_DEVICE: str = "cpu"  # 或 "cuda"
```

### 4.2 模型加载器 (model_loader.py)

```python
class DLModelLoader:
    """LSTM+FinanceLlama 模型加载器"""

    def __init__(self):
        self.model = None
        self.scaler_X = None
        self.scaler_y = None
        self.device = torch.device(config.DL_DEVICE)

    def load_model(self) -> StockLSTM_FinanceLlama:
        """加载模型权重"""
        # 1. 创建模型结构
        # 2. 加载 .pth 权重
        # 3. 加载 scaler
        # 4. 加载 Finance-Llama
        pass

    def predict(self, features: np.ndarray) -> np.ndarray:
        """预测未来5天价格"""
        # 1. 标准化
        # 2. 转换为 tensor
        # 3. 模型推理
        # 4. 反标准化
        pass
```

### 4.3 特征计算 (features.py)

```python
class DLFeatures:
    """19个技术指标计算"""

    FEATURE_NAMES = [
        'open', 'high', 'low', 'volatility_20', 'daily_range',
        'volume_change', 'macd', 'rsi', 'ma5', 'ma20',
        'ema12', 'ema26', 'momentum', 'vol_ma5', 'atr',
        'obv', 'bollinger_upper', 'bollinger_lower', 'price_volume_ratio'
    ]

    @staticmethod
    def compute_features(df: pd.DataFrame) -> pd.DataFrame:
        """从K线数据计算19个特征"""
        # 与 data_preprocessing.py 相同的计算逻辑
        pass
```

### 4.4 预测服务 (predictor.py)

```python
class DLPredictor:
    """预测服务"""

    def __init__(self):
        self.loader = DLModelLoader()
        self.loader.load_model()

    def predict(self, stock_code: str, kline_data: list) -> DLPredictionResult:
        """
        预测未来5天收盘价

        Returns:
            {
                dates: ["2024-01-02", ..., "2024-01-06"],
                predicted_prices: [10.5, 10.8, 11.0, 10.9, 11.2],
                current_price: 10.3
            }
        """
        pass
```

### 4.5 回测逻辑 (backtest.py)

```python
class DLBacktester:
    """基于预测结果的回测"""

    def run_backtest(
        self,
        stock_code: str,
        start_date: str,
        end_date: str,
        initial_capital: float = 100000
    ) -> DLBacktestResult:
        """
        回测逻辑

        Returns:
            {
                total_return: 0.15,          # 总收益率
                annualized_return: 0.25,     # 年化收益率
                sharpe_ratio: 1.5,          # 夏普比率
                max_drawdown: 0.08,         # 最大回撤
                win_rate: 0.65,             # 胜率
                trades: [...],              # 交易记录
                portfolio_values: [...]      # 每日组合价值
            }
        """
        pass
```

---

## 五、API 设计

### 5.1 预测接口

**POST** `/api/dl/predict`

Request:
```json
{
  "stock_code": "600000",
  "kline_days": 60
}
```

Response:
```json
{
  "success": true,
  "data": {
    "stock_code": "600000",
    "current_price": 10.3,
    "last_date": "2024-01-01",
    "prediction_dates": ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05", "2024-01-06"],
    "predicted_prices": [10.5, 10.8, 11.0, 10.9, 11.2],
    "kline_data": [
      {"date": "2023-11-03", "open": 10.0, "high": 10.5, "low": 9.8, "close": 10.3, "volume": 1000000},
      ...
    ]
  }
}
```

### 5.2 回测接口

**POST** `/api/dl/backtest`

Request:
```json
{
  "stock_code": "600000",
  "start_date": "2023-01-01",
  "end_date": "2024-01-01",
  "initial_capital": 100000
}
```

Response:
```json
{
  "success": true,
  "data": {
    "total_return": 0.15,
    "annualized_return": 0.25,
    "sharpe_ratio": 1.5,
    "max_drawdown": 0.08,
    "win_rate": 0.65,
    "total_trades": 20,
    "trades": [
      {"date": "2023-03-15", "action": "BUY", "price": 10.5, "quantity": 1000},
      {"date": "2023-03-20", "action": "SELL", "price": 11.0, "quantity": 1000}
    ],
    "portfolio_values": [...]
  }
}
```

---

## 六、前端页面设计

### 6.1 页面布局

```
┌─────────────────────────────────────────────────────────────┐
│  DL 预测                                                      │
├─────────────────────────────────────────────────────────────┤
│  [股票选择 ▼]  [预测]  [回测]                                 │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│     K线图 + 预测折线图                                       │
│     ▓▓▓▓▓▓░░░░░░░  ← 历史价格 (蓝色)                         │
│           ░░░░░░░░░  ← 预测价格 (红色)                        │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  回测结果 (回测时显示)                                        │
│  ┌─────────────┬─────────────┬─────────────┐                │
│  │ 总收益率    │ 年化收益率  │ 夏普比率    │                │
│  │ +15.00%     │ +25.00%     │ 1.5         │                │
│  └─────────────┴─────────────┴─────────────┘                │
│  最大回撤: -8.00%  |  胜率: 65%  |  交易次数: 20            │
├─────────────────────────────────────────────────────────────┤
│  交易记录                                                     │
│  ┌──────────┬────────┬────────┬────────┐                     │
│  │ 日期      │ 操作   │ 价格   │ 数量   │                     │
│  ├──────────┼────────┼────────┼────────┤                     │
│  │ 03-15    │ 买入   │ 10.50  │ 1000   │                     │
│  │ 03-20    │ 卖出   │ 11.00  │ 1000   │                     │
│  └──────────┴────────┴────────┴────────┘                     │
└─────────────────────────────────────────────────────────────┘
```

### 6.2 图表配置

- **历史K线**: 折线图，蓝色
- **预测价格**: 折线图，红色虚线
- **分界线**: 在最后一个历史日期处画一条竖线，标注"预测起点"

---

## 七、实施步骤

| 步骤 | 任务 | 预估时间 |
|------|------|----------|
| 1 | 修改 config.py 添加配置 | 5 min |
| 2 | 创建 dl_prediction/features.py 技术指标 | 15 min |
| 3 | 创建 dl_prediction/model_loader.py 模型加载 | 20 min |
| 4 | 创建 dl_prediction/predictor.py 预测服务 | 15 min |
| 5 | 创建 dl_prediction/backtest.py 回测逻辑 | 20 min |
| 6 | 创建 api/dl_prediction.py API接口 | 15 min |
| 7 | 修改 frontend/api.ts 添加API调用 | 10 min |
| 8 | 创建 frontend/types/index.ts 类型定义 | 10 min |
| 9 | 创建 frontend/pages/DLPrediction.tsx 页面 | 30 min |
| 10 | 添加路由和菜单 | 5 min |
| 11 | 测试整个流程 | 15 min |

**总计**: 约 160 分钟

---

## 八、注意事项

1. **模型文件**: 确认 `.pth` 文件完整，目前目录中只有 `.qkdownloading` 文件
2. **内存占用**: Finance-Llama-8B 模型较大，确保服务器内存充足
3. **推理速度**: 首次推理较慢（需加载模型），后续会缓存
4. **错误处理**: 模型推理失败时返回友好错误信息

---

## 九、待确认问题

- [ ] 模型文件名确认（当前目录无 .pth 文件）
- [ ] 交易滑点设置（默认 0）
- [ ] 手续费设置（默认 0）
- [ ] 初始资金默认值（100000）
