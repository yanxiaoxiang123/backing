export interface Stock {
  id: number
  code: string
  name: string
  market: string
  list_date?: string
  created_at: string
}

export interface DailyKline {
  id: number
  stock_code: string
  date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
  amount?: number
}

export interface BacktestTrade {
  id: number
  date?: string
  trade_date: string
  action: 'buy' | 'sell'
  price: number
  quantity: number
  amount: number
}

export interface BacktestResult {
  id: number
  strategy_id: number
  stock_code: string
  start_date: string
  end_date: string
  initial_capital: number
  final_capital: number
  total_return: number
  annual_return: number
  sharpe_ratio?: number
  max_drawdown?: number
  win_rate?: number
  total_trades: number
  created_at: string
  trades: BacktestTrade[]
}

export interface BacktestListItem {
  id: number
  stock_code: string
  start_date: string
  end_date: string
  total_return: number
  total_trades: number
  created_at: string
}

export interface SyncResponse {
  success: boolean
  message: string
  stocks_synced: number
  klines_synced: number
}

export interface BacktestRequest {
  stock_code: string
  strategy_type: string
  start_date: string
  end_date: string
  initial_capital: number
  parameters?: Record<string, number | string | boolean>
}

export interface KlineIndicator {
  date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
  ma5?: number
  ma10?: number
  ma20?: number
  ma60?: number
  ma120?: number
  dif?: number
  dea?: number
  macd?: number
  kdj_k?: number
  kdj_d?: number
  kdj_j?: number
  rsi6?: number
  rsi12?: number
  rsi24?: number
}

export interface KlineResponse {
  success: boolean
  stock_code: string
  stock_name: string
  period: string
  data: KlineIndicator[]
}

// ==================== Strategy Types ====================

export interface StrategyParamConfig {
  type: 'slider' | 'input' | 'select'
  default: number | string
  min?: number
  max?: number
  step?: number
  options?: { label: string; value: string | number }[]
  description?: string
}

export interface StrategyInfo {
  name: string
  description: string
  parameters: Record<string, StrategyParamConfig>
}

export interface SignalDataPoint {
  date: string
  close: number
  signal: number
  ma_short?: number
  ma_long?: number
  volume?: number
  pred_close_5d?: number
  pred_return_5d?: number
  confidence?: number
}

export interface SignalResponse {
  success: boolean
  strategy_name: string
  stock_code: string
  start_date: string
  end_date: string
  data: SignalDataPoint[]
  stats?: SignalStats
}

export interface SignalStats {
  total_buy_signals: number
  total_sell_signals: number
  total_trades: number
  win_rate: number
  avg_holding_days: number
  avg_return_per_trade: number
  profit_ratio: number
  max_win: number
  max_loss: number
  consecutive_wins: number
  consecutive_losses: number
}

export interface BacktestTradeItem {
  date: string
  trade_date?: string
  action: string
  price: number
  quantity: number
  amount: number
}

export interface BacktestMetrics {
  sharpe_ratio: number
  total_return: number
  annual_return: number
  max_drawdown: number
  win_rate: number
  profit_factor: number
  total_trades: number
}

export interface StrategyBacktestResponse {
  success: boolean
  strategy_name: string
  stock_code: string
  start_date: string
  end_date: string
  initial_capital: number
  final_capital: number
  trades: BacktestTradeItem[]
  metrics: BacktestMetrics
}

export interface OptimizeResultItem {
  params: Record<string, number>
  metrics: Record<string, number>
  score: number
}

export interface OptimizeResponse {
  success: boolean
  strategy_name: string
  stock_code: string
  metric: string
  best_params: Record<string, number>
  best_score: number
  best_metrics: Record<string, number>
  total_combinations: number
  all_results: OptimizeResultItem[]
}

export interface JobSubmission {
  job_id: string
  status: string
  job_type?: string
  message: string
}

export interface JobStatus<T = Record<string, unknown>> {
  id: string
  job_type: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  message: string
  progress: number
  payload: Record<string, unknown>
  result?: T
  error?: string
  created_at: string
  updated_at: string
}

// ==================== Agent Types ====================

export interface AgentAnalyzeRequest {
  stock_code: string
  stock_name?: string
  mode: 'quick' | 'standard' | 'full' | 'strategy'
}

export interface AgentOpinion {
  agent_name: string
  signal: 'buy' | 'sell' | 'hold'
  confidence: number
  reason: string
  metadata?: Record<string, unknown>
}

export interface AgentNewsItem {
  title: string
  url: string
  content: string
  score?: number
}

export interface AgentStage {
  stage_name: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  opinion?: AgentOpinion
  error?: string
  duration_s: number
  meta?: Record<string, unknown>
}

export interface AgentAnalyzeResponse {
  success: boolean
  stock_code: string
  stock_name: string
  mode: string
  final_signal: 'buy' | 'sell' | 'hold'
  final_confidence: number
  final_reason: string
  opinions: AgentOpinion[]
  stages: AgentStage[]
  news_items?: AgentNewsItem[]
  duration_s: number
  error?: string
}

export interface AnalysisRecord {
  id: number
  stock_code: string
  stock_name?: string
  analysis_date: string
  mode: string
  final_signal: 'buy' | 'sell' | 'hold'
  final_confidence: number
  final_reason?: string
  duration_s: number
  error?: string
  created_at: string
}

// 大盘分析类型
export interface IndexInfo {
  code: string
  name: string
}

export interface IndexResult {
  code: string
  name: string
  success: boolean
  signal: 'buy' | 'sell' | 'hold'
  confidence: number
  reason: string
  error?: string
}

export interface MarketAnalyzeRequest {
  index_codes?: string[]
  mode?: string
}

export interface MarketAnalyzeResponse {
  success: boolean
  indices: IndexResult[]
  overall_signal: 'buy' | 'sell' | 'hold'
  overall_confidence: number
  overall_reason: string
  duration_s: number
  error?: string
}

export interface DashboardMover {
  id: number
  code: string
  name: string
  current_price: number
  change: number
  change_percent: number
}

export interface DashboardIndex {
  code: string
  name: string
  value: number
  change: number
  change_percent: number
}

export interface DashboardTrend {
  name: string
  dates: string[]
  values: number[]
}

export interface DashboardStock {
  id: number
  code: string
  name: string
  current_price: number
  high: number
  low: number
  volume: number
  change: number
  change_percent: number
}

export interface DashboardSummary {
  market_stats: {
    up: number
    down: number
    flat: number
    total: number
  }
  indices: DashboardIndex[]
  trend: DashboardTrend
  watchlist: DashboardStock[]
}

export interface WatchlistItem {
  id: number
  stock_code: string
  stock_name?: string
  added_at: string
}

export interface WatchlistResponse {
  items: WatchlistItem[]
  total: number
}

// ==================== Screener Types ====================

export interface ScreenerCondition {
  indicator: string
  operator: string
  value: number
  params?: Record<string, number>
}

export interface ScreenerRequest {
  conditions: ScreenerCondition[]
  logic: 'AND' | 'OR'
  market?: string
  max_results: number
}

export interface ScreenerResultItem {
  stock_code: string
  stock_name: string
  close: number
  volume: number
  change_pct: number | null
  indicators: Record<string, number | null>
  matched_conditions: string[]
}

export interface ScreenerResponse {
  success: boolean
  total_stocks_scanned: number
  total_matched: number
  conditions_used: string[]
  logic: string
  results: ScreenerResultItem[]
  execution_time_s: number
}

// ==================== Strategy Comparison Types ====================

export interface CompareRequest {
  stock_code: string
  start_date: string
  end_date: string
  initial_capital?: number
}

export interface CompareStrategyMetrics {
  strategy_name: string
  total_return: number
  annual_return: number
  sharpe_ratio: number
  max_drawdown: number
  win_rate: number
  total_trades: number
  profit_factor: number
}

export interface CompareCurvePoint {
  date: string
  value: number
}

export interface CompareStrategyResult {
  strategy_name: string
  description: string
  metrics: CompareStrategyMetrics
  equity_curve: CompareCurvePoint[]
  error?: string
}

export interface CompareResponse {
  success: boolean
  stock_code: string
  start_date: string
  end_date: string
  initial_capital: number
  results: CompareStrategyResult[]
  total_strategies: number
  failed_count: number
}
