import axios from 'axios'
import type {
  Stock,
  DailyKline,
  BacktestResult,
  BacktestListItem,
  SyncResponse,
  BacktestRequest,
  KlineResponse,
  StrategyInfo,
  SignalResponse,
  StrategyBacktestResponse,
  OptimizeResponse,
  AgentAnalyzeRequest,
  AgentAnalyzeResponse,
  AnalysisRecord,
  IndexInfo,
  MarketAnalyzeRequest,
  MarketAnalyzeResponse,
  DashboardSummary,
  JobStatus,
  JobSubmission,
  WatchlistItem,
  WatchlistResponse,
  ScreenerRequest,
  ScreenerResponse,
  CompareRequest,
  CompareResponse
} from '../types'

const api = axios.create({
  baseURL: '/api',
  timeout: 120000  // 120秒超时，分析需要较长时间
})

// 添加 API Key 到所有请求
api.interceptors.request.use((config) => {
  const apiKey = import.meta.env.VITE_API_KEY
  if (apiKey) {
    config.headers['X-API-Key'] = apiKey
  }
  return config
})

// Stock APIs
export async function getStocks(
  market?: string,
  skip = 0,
  limit = 100
): Promise<{ items: Stock[]; total: number }> {
  const params = new URLSearchParams()
  if (market) params.append('market', market)
  params.append('skip', String(skip))
  params.append('limit', String(limit))
  const response = await api.get<Stock[]>(`/stocks?${params}`)
  return {
    items: response.data,
    total: Number(response.headers['x-total-count'] || response.data.length)
  }
}

export async function getAllStocks(market?: string): Promise<Stock[]> {
  const pageSize = 500
  let skip = 0
  let total = 0
  const items: Stock[] = []

  do {
    const response = await getStocks(market, skip, pageSize)
    items.push(...response.items)
    total = response.total
    skip += response.items.length
    if (response.items.length === 0) {
      break
    }
  } while (items.length < total)

  return items
}

export async function getStock(code: string): Promise<Stock> {
  const response = await api.get<Stock>(`/stocks/${code}`)
  return response.data
}

export async function getStockKline(
  code: string,
  startDate?: string,
  endDate?: string
): Promise<DailyKline[]> {
  const params = new URLSearchParams()
  if (startDate) params.append('start_date', startDate)
  if (endDate) params.append('end_date', endDate)
  const response = await api.get<DailyKline[]>(`/stocks/${code}/kline?${params}`)
  return response.data
}

export async function getStockIndicators(
  code: string,
  period = 'daily',
  startDate?: string,
  endDate?: string
): Promise<KlineResponse> {
  const params = new URLSearchParams()
  params.append('period', period)
  if (startDate) params.append('start_date', startDate)
  if (endDate) params.append('end_date', endDate)
  const response = await api.get<KlineResponse>(`/stocks/${code}/indicators?${params}`)
  return response.data
}

export async function getDashboardSummary(): Promise<DashboardSummary> {
  const response = await api.get<DashboardSummary>('/dashboard')
  return response.data
}

export async function syncStocks(): Promise<SyncResponse> {
  const response = await api.post<SyncResponse>('/stocks/sync')
  return response.data
}

export async function syncKline(
  stockCodes?: string[],
  startDate?: string,
  endDate?: string
): Promise<SyncResponse> {
  const params: Record<string, string> = {}
  if (startDate) {
    params.start_date = startDate
  }
  if (endDate) {
    params.end_date = endDate
  }
  const response = await api.post<SyncResponse>('/stocks/sync-kline', stockCodes, {
    params
  })
  return response.data
}

export async function submitSyncStocks(): Promise<JobSubmission> {
  const response = await api.post<JobSubmission>('/stocks/sync/submit')
  return response.data
}

export async function submitSyncKline(
  stockCodes?: string[],
  startDate = '2020-01-01',
  endDate?: string
): Promise<JobSubmission> {
  const params: Record<string, string> = { start_date: startDate }
  if (endDate) {
    params.end_date = endDate
  }
  const response = await api.post<JobSubmission>('/stocks/sync-kline/submit', stockCodes, {
    params
  })
  return response.data
}

export async function getIndexList(): Promise<IndexInfo[]> {
  const response = await api.get<IndexInfo[]>('/indices')
  return response.data
}

export async function submitSyncIndices(
  indexCodes?: string[],
  startDate = '2020-01-01',
  endDate?: string
): Promise<JobSubmission> {
  const params: Record<string, string> = { start_date: startDate }
  if (endDate) {
    params.end_date = endDate
  }
  const response = await api.post<JobSubmission>('/indices/sync/submit', indexCodes, {
    params
  })
  return response.data
}

// Backtest APIs
export async function runBacktest(request: BacktestRequest): Promise<BacktestResult> {
  const response = await api.post<BacktestResult>('/backtest', request)
  return response.data
}

export async function getBacktestResults(
  stockCode?: string,
  skip = 0,
  limit = 20
): Promise<BacktestListItem[]> {
  const params = new URLSearchParams()
  if (stockCode) params.append('stock_code', stockCode)
  params.append('skip', String(skip))
  params.append('limit', String(limit))
  const response = await api.get<BacktestListItem[]>(`/backtest/results?${params}`)
  return response.data
}

export async function getBacktestResult(id: number): Promise<BacktestResult> {
  const response = await api.get<BacktestResult>(`/backtest/${id}`)
  return response.data
}

// Strategy APIs
export async function getStrategies(): Promise<StrategyInfo[]> {
  const response = await api.get<StrategyInfo[]>('/strategies')
  return response.data
}

export async function getStrategy(strategyName: string): Promise<StrategyInfo> {
  const response = await api.get<StrategyInfo>(`/strategies/${strategyName}`)
  return response.data
}

export interface SignalRequest {
  strategy_name: string
  stock_code: string
  start_date: string
  end_date: string
  parameters?: Record<string, number | string>
}

export async function generateSignals(request: SignalRequest): Promise<SignalResponse> {
  const response = await api.post<SignalResponse>('/strategies/signals', request)
  return response.data
}

export interface StrategyBacktestRequest {
  strategy_name: string
  stock_code: string
  start_date: string
  end_date: string
  initial_capital: number
  parameters?: Record<string, number | string>
}

export async function runStrategyBacktest(request: StrategyBacktestRequest): Promise<StrategyBacktestResponse> {
  const response = await api.post<StrategyBacktestResponse>('/strategies/backtest', request)
  return response.data
}

export interface OptimizeRequest {
  strategy_name: string
  stock_code: string
  start_date: string
  end_date: string
  initial_capital: number
  param_grid: Record<string, number[]>
  metric: string
}

export async function optimizeParameters(request: OptimizeRequest): Promise<OptimizeResponse> {
  const response = await api.post<OptimizeResponse>('/strategies/optimize', request)
  return response.data
}

export async function submitOptimizeParameters(request: OptimizeRequest): Promise<JobSubmission> {
  const response = await api.post<JobSubmission>('/strategies/optimize/submit', request)
  return response.data
}

// ==================== Agent APIs ====================

export async function analyzeStock(request: AgentAnalyzeRequest): Promise<AgentAnalyzeResponse> {
  const response = await api.post<AgentAnalyzeResponse>('/agent/analyze', request)
  return response.data
}

export async function submitAnalyzeStock(request: AgentAnalyzeRequest): Promise<JobSubmission> {
  const response = await api.post<JobSubmission>('/agent/analyze/submit', request)
  return response.data
}

export async function getAnalysisHistory(
  stockCode?: string,
  skip = 0,
  limit = 20
): Promise<AnalysisRecord[]> {
  const params = new URLSearchParams()
  if (stockCode) params.append('stock_code', stockCode)
  params.append('skip', String(skip))
  params.append('limit', String(limit))
  const response = await api.get<AnalysisRecord[]>(`/agent/history?${params}`)
  return response.data
}

export async function getAnalysisDetail(recordId: number): Promise<AgentAnalyzeResponse> {
  const response = await api.get<AgentAnalyzeResponse>(`/agent/${recordId}`)
  return response.data
}

export async function getJobStatus<T = Record<string, unknown>>(jobId: string): Promise<JobStatus<T>> {
  const response = await api.get<JobStatus<T>>(`/jobs/${jobId}`)
  return response.data
}

export async function cancelJob(jobId: string): Promise<void> {
  await api.post(`/jobs/${jobId}/cancel`)
}

// 大盘分析 APIs
export async function analyzeMarket(
  request: MarketAnalyzeRequest
): Promise<MarketAnalyzeResponse> {
  const response = await api.post<MarketAnalyzeResponse>('/agent/market/analyze', request)
  return response.data
}

// ============== DL Prediction API ==============

export interface DLPredictionRequest {
  stock_code: string
  kline_days?: number
}

export interface DLPredictionResponse {
  success: boolean
  data?: {
    stock_code: string
    current_price: number
    last_date: string
    prediction_dates: string[]
    predicted_prices: number[]
    kline_data: Array<{
      date: string
      open: number
      high: number
      low: number
      close: number
      volume: number
    }>
  }
  error?: string
}

export async function dlPredict(request: DLPredictionRequest): Promise<DLPredictionResponse> {
  const response = await api.post<DLPredictionResponse>('/dl/predict', request)
  return response.data
}

export interface DLBacktestRequest {
  stock_code: string
  start_date: string
  end_date: string
  initial_capital?: number
}

export interface DLBacktestResponse {
  success: boolean
  data?: {
    total_return: number
    annualized_return: number
    sharpe_ratio: number
    max_drawdown: number
    win_rate: number
    total_trades: number
    trades: Array<{
      date: string
      action: 'BUY' | 'SELL'
      price: number
      quantity: number
    }>
    portfolio_values: number[]
  }
  error?: string
}

export async function dlBacktest(request: DLBacktestRequest): Promise<DLBacktestResponse> {
  const response = await api.post<DLBacktestResponse>('/dl/backtest', request)
  return response.data
}

// Watchlist API
export async function getWatchlist(): Promise<WatchlistResponse> {
  const response = await api.get<WatchlistResponse>('/watchlist')
  return response.data
}

export async function getWatchlistCodes(): Promise<string[]> {
  const response = await api.get<string[]>('/watchlist/codes')
  return response.data
}

export async function addToWatchlist(stockCode: string): Promise<WatchlistItem> {
  const response = await api.post<WatchlistItem>('/watchlist', { stock_code: stockCode })
  return response.data
}

export async function removeFromWatchlist(stockCode: string): Promise<{ success: boolean }> {
  const response = await api.delete<{ success: boolean }>(`/watchlist/${stockCode}`)
  return response.data
}

// Screener API
export async function runScreener(request: ScreenerRequest): Promise<ScreenerResponse> {
  const response = await api.post<ScreenerResponse>('/screener', request)
  return response.data
}

// Strategy Comparison API
export async function compareStrategies(request: CompareRequest): Promise<CompareResponse> {
  const response = await api.post<CompareResponse>('/strategies/compare', request)
  return response.data
}

export default api
