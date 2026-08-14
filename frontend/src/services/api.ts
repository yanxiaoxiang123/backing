import axios from 'axios'
import { message } from 'antd'
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
  CompareResponse,
} from '../types'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 120000, // 120秒超时，分析需要较长时间
})

// ---------------------------------------------------------------------------
// 会话认证
//
// 后端签发短期 HttpOnly session cookie（SameSite=Lax，生产 https_only）。
// API key 只在登录时经一次 POST /api/v1/auth/session 提交，随后即被丢弃：
// 不写入 bundle（无 VITE_API_KEY）、不写 localStorage、不进任何请求头。
// 状态变更请求携带后端登录时下发的 csrf_token cookie（double-submit）。
// ---------------------------------------------------------------------------

export type AuthState = 'unknown' | 'authenticated' | 'unauthenticated'

let _authState: AuthState = 'unknown'
const _authListeners = new Set<(state: AuthState) => void>()

export function getAuthState(): AuthState {
  return _authState
}

function setAuthState(state: AuthState): void {
  if (_authState === state) return
  _authState = state
  _authListeners.forEach((fn) => fn(state))
}

/** 订阅认证状态变化，返回取消订阅函数。 */
export function onAuthChange(fn: (state: AuthState) => void): () => void {
  _authListeners.add(fn)
  return () => {
    _authListeners.delete(fn)
  }
}

function readCsrfToken(): string {
  const match = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]+)/)
  return match ? decodeURIComponent(match[1]) : ''
}

/** 启动时探测会话：无有效 cookie 则进入未认证状态（跳转登录页）。 */
export async function bootstrapAuth(): Promise<void> {
  try {
    const response = await axios.get('/api/v1/auth/me', { baseURL: '' })
    setAuthState(response.data?.authenticated ? 'authenticated' : 'unauthenticated')
  } catch {
    setAuthState('unauthenticated')
  }
}

/** 用 API key 换短期 HttpOnly session cookie（key 不落盘、不进 bundle）。 */
export async function loginWithApiKey(apiKey: string): Promise<void> {
  await axios.post('/api/v1/auth/session', { api_key: apiKey }, { baseURL: '' })
  setAuthState('authenticated')
}

export async function logout(): Promise<void> {
  try {
    await axios.post('/api/v1/auth/logout', {}, { baseURL: '' })
  } finally {
    setAuthState('unauthenticated')
  }
}

// 状态变更请求自动携带 CSRF token（double-submit）
api.interceptors.request.use((config) => {
  const method = (config.method || 'get').toUpperCase()
  if (method !== 'GET' && method !== 'HEAD' && method !== 'OPTIONS') {
    const token = readCsrfToken()
    if (token) {
      config.headers = config.headers || {}
      config.headers['X-CSRF-Token'] = token
    }
  }
  return config
})

// 提取后端统一错误体里的可读信息
function extractUserMessage(error: unknown): string | undefined {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as { error?: { message?: string } } | undefined
    if (data?.error?.message) return data.error.message
  }
  return undefined
}

export interface ApiError extends Error {
  status?: number
  /** 后端返回的可读错误信息（业务错误），由页面负责呈现。 */
  userMessage?: string
}

/** 从任意异常中提取面向用户的错误文案（供页面 catch 后展示）。 */
export function getApiErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const backendMsg = extractUserMessage(error)
    if (backendMsg) return backendMsg
    if (error.code === 'ECONNABORTED') return '请求超时，请稍后重试'
    if (error.response) {
      const status = error.response.status
      if (status >= 500) return '服务器开小差了，请稍后重试'
    } else {
      return '网络异常，请检查网络后重试'
    }
    if (error.message) return error.message
  }
  if (error instanceof Error && error.message) return error.message
  return '请求失败，请稍后重试'
}

// 全局响应拦截器 — 错误归属：全局只处理认证/未知错误，业务错误由页面呈现。
// 认证错误（401/403）静默，由页面/会话逻辑处理；业务错误（有响应体）把可读
// 信息挂到 error.userMessage 上透传给页面，避免与页面自己的 toast 重复；
// 仅网络层未知错误（超时/断网）在此做全局兜底提示。
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (!axios.isAxiosError(error)) {
      // 非网络错误 —— 透传并全局兜底提示
      message.error(getApiErrorMessage(error))
      return Promise.reject(error)
    }

    const status = error.response?.status

    // 401/403 静默（由页面自行处理跳转登录）
    if (status === 401 || status === 403) {
      // 业务接口 401 = 会话失效/未登录 → 进入未认证状态（跳转登录页）
      if (status === 401 && !(error.config?.url || '').includes('/auth/')) {
        setAuthState('unauthenticated')
      }
      console.warn(`[api] ${status} ${error.config?.url}`)
      return Promise.reject(error)
    }

    const userMessage = extractUserMessage(error) || error.message || '请求失败'

    if (error.response) {
      // 业务错误：挂到 error 上，由页面呈现（避免重复 toast）
      const apiError = error as ApiError
      apiError.status = status
      apiError.userMessage = userMessage
    } else {
      // 网络层未知错误（无响应）：全局兜底提示
      message.error(getApiErrorMessage(error))
    }

    return Promise.reject(error)
  },
)

// Stock APIs
export async function getStocks(
  market?: string,
  cursor = 0,
  limit = 100,
  search?: string,
): Promise<{ items: Stock[]; total: number; nextCursor: number | null }> {
  const params = new URLSearchParams()
  if (market) params.append('market', market)
  if (search) params.append('search', search)
  params.append('cursor', String(cursor))
  params.append('limit', String(limit))
  const response = await api.get<Stock[]>(`/stocks?${params}`)
  const items = response.data
  const nextCursor = items.length > 0 ? items[items.length - 1].id : null
  return {
    items,
    total: Number(response.headers['x-total-count'] || items.length),
    nextCursor,
  }
}

export async function getAllStocks(market?: string): Promise<Stock[]> {
  const pageSize = 500
  let cursor = 0
  const items: Stock[] = []

  do {
    const response = await getStocks(market, cursor, pageSize)
    items.push(...response.items)
    if (response.items.length === 0) {
      break
    }
    cursor = response.nextCursor ?? -1
  } while (cursor !== -1)

  return items
}

export async function getStock(code: string): Promise<Stock> {
  const response = await api.get<Stock>(`/stocks/${code}`)
  return response.data
}

export async function getStockKline(
  code: string,
  startDate?: string,
  endDate?: string,
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
  endDate?: string,
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
  endDate?: string,
): Promise<SyncResponse> {
  const params: Record<string, string> = {}
  if (startDate) {
    params.start_date = startDate
  }
  if (endDate) {
    params.end_date = endDate
  }
  const response = await api.post<SyncResponse>('/stocks/sync-kline', stockCodes, {
    params,
  })
  return response.data
}

export async function submitSyncStocks(): Promise<JobSubmission> {
  const response = await api.post<JobSubmission>('/stocks/sync/submit')
  return response.data
}

export async function submitSyncKline(
  stockCodes?: string[],
  strategy: 'incremental' | 'full' = 'incremental',
): Promise<JobSubmission> {
  const params: Record<string, string> = { strategy }
  const response = await api.post<JobSubmission>(
    '/stocks/sync-kline/submit',
    stockCodes,
    {
      params,
    },
  )
  return response.data
}

export async function getIndexList(): Promise<IndexInfo[]> {
  const response = await api.get<IndexInfo[]>('/indices')
  return response.data
}

export async function submitSyncIndices(
  indexCodes?: string[],
  startDate = '2020-01-01',
  endDate?: string,
): Promise<JobSubmission> {
  const params: Record<string, string> = { start_date: startDate }
  if (endDate) {
    params.end_date = endDate
  }
  const response = await api.post<JobSubmission>('/indices/sync/submit', indexCodes, {
    params,
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
  limit = 20,
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

export async function runStrategyBacktest(
  request: StrategyBacktestRequest,
): Promise<StrategyBacktestResponse> {
  const response = await api.post<StrategyBacktestResponse>(
    '/strategies/backtest',
    request,
  )
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

export async function optimizeParameters(
  request: OptimizeRequest,
): Promise<OptimizeResponse> {
  const response = await api.post<OptimizeResponse>('/strategies/optimize', request)
  return response.data
}

export async function submitOptimizeParameters(
  request: OptimizeRequest,
): Promise<JobSubmission> {
  const response = await api.post<JobSubmission>('/strategies/optimize/submit', request)
  return response.data
}

// ==================== Agent APIs ====================

export async function analyzeStock(
  request: AgentAnalyzeRequest,
): Promise<AgentAnalyzeResponse> {
  const response = await api.post<AgentAnalyzeResponse>('/agent/analyze', request)
  return response.data
}

export async function submitAnalyzeStock(
  request: AgentAnalyzeRequest,
): Promise<JobSubmission> {
  const response = await api.post<JobSubmission>('/agent/analyze/submit', request)
  return response.data
}

export async function getAnalysisHistory(
  stockCode?: string,
  skip = 0,
  limit = 20,
): Promise<AnalysisRecord[]> {
  const params = new URLSearchParams()
  if (stockCode) params.append('stock_code', stockCode)
  params.append('skip', String(skip))
  params.append('limit', String(limit))
  const response = await api.get<AnalysisRecord[]>(`/agent/history?${params}`)
  return response.data
}

export async function getAnalysisDetail(
  recordId: number,
): Promise<AgentAnalyzeResponse> {
  const response = await api.get<AgentAnalyzeResponse>(`/agent/${recordId}`)
  return response.data
}

export async function getJobStatus<T = Record<string, unknown>>(
  jobId: string,
  signal?: AbortSignal,
): Promise<JobStatus<T>> {
  const response = await api.get<JobStatus<T>>(`/jobs/${jobId}`, { signal })
  return response.data
}

export async function cancelJob(jobId: string): Promise<void> {
  await api.post(`/jobs/${jobId}/cancel`)
}

// 大盘分析 APIs
export async function analyzeMarket(
  request: MarketAnalyzeRequest,
): Promise<MarketAnalyzeResponse> {
  const response = await api.post<MarketAnalyzeResponse>(
    '/agent/market/analyze',
    request,
  )
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

export async function dlPredict(
  request: DLPredictionRequest,
): Promise<DLPredictionResponse> {
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

export async function dlBacktest(
  request: DLBacktestRequest,
): Promise<DLBacktestResponse> {
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
  const response = await api.post<WatchlistItem>('/watchlist', {
    stock_code: stockCode,
  })
  return response.data
}

export async function removeFromWatchlist(
  stockCode: string,
): Promise<{ success: boolean }> {
  const response = await api.delete<{ success: boolean }>(`/watchlist/${stockCode}`)
  return response.data
}

// Screener API
export async function runScreener(request: ScreenerRequest): Promise<ScreenerResponse> {
  const response = await api.post<ScreenerResponse>('/screener', request)
  return response.data
}

export async function submitScreener(): Promise<{ job_id: string }> {
  const response = await api.post<{ job_id: string }>('/screener/submit')
  return response.data
}

export async function getScreenerStatus(jobId: string): Promise<{
  status: string
  progress: number
  payload?: { stage: string; current: number; total: number; message: string }
  result?: { success: boolean; total_scanned: number; results: any[] }
  error?: string
}> {
  const response = await api.get(`/screener/${jobId}`)
  return response.data
}

// Strategy Comparison API
export async function compareStrategies(
  request: CompareRequest,
): Promise<CompareResponse> {
  const response = await api.post<CompareResponse>('/strategies/compare', request)
  return response.data
}

// Realtime Bars API
export async function getRealtimeBars(
  code: string,
  period: string = 'daily',
): Promise<{
  success: boolean
  code: string
  data: Array<{
    date: string
    open: number
    high: number
    low: number
    close: number
    volume: number
    amount: number
    symbol: string
  }>
}> {
  const response = await api.get<{
    success: boolean
    code: string
    data: Array<{
      date: string
      open: number
      high: number
      low: number
      close: number
      volume: number
      amount: number
      symbol: string
    }>
  }>(`/realtime/${code}?period=${period}`)
  return response.data
}

// Realtime Quotes API
export async function getRealtimeQuotes(codes: string[]): Promise<{
  success: boolean
  data: Array<{
    symbol: string
    open: number
    high: number
    low: number
    close: number
    volume: number
    amount: number
    change: number
    change_percent: number
    prev_close: number
  }>
}> {
  const response = await api.get<any>(`/realtime/quotes?codes=${codes.join(',')}`)
  return response.data
}

// Realtime Indices API
export async function getRealtimeIndices(): Promise<{
  success: boolean
  data: Array<{
    symbol: string
    name: string
    close: number
    change: number
    change_percent: number
    prev_close: number
  }>
}> {
  const response = await api.get<any>('/realtime/indices')
  return response.data
}

export default api
