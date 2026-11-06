import axios from 'axios'
import { toast } from '../utils/toast'
import type {
  Stock,
  DailyKline,
  BacktestResult,
  BacktestListItem,
  KlineResponse,
  StrategyInfo,
  SignalResponse,
  StrategyBacktestResponse,
  AgentAnalyzeRequest,
  AgentAnalyzeResponse,
  AnalysisRecord,
  StockOverview,
  JobStatus,
  JobSubmission,
  WatchlistItem,
  WatchlistResponse,
  CompareRequest,
  CompareResponse,
  ResearchExecutionOptions,
} from '../types'
import { normalizeStockCode } from '../utils/stockIdentity'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 120000, // 120秒超时，分析需要较长时间
})

function canonicalStockCode(code: string | null | undefined): string {
  const raw = String(code ?? '').trim()
  return normalizeStockCode(raw) ?? raw
}

function canonicalStockRequest<T extends { stock_code: string }>(request: T): T {
  return { ...request, stock_code: canonicalStockCode(request.stock_code) }
}

function canonicalStockCodes(codes?: string[]): string[] | undefined {
  return codes?.map((code) => canonicalStockCode(code))
}

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

/**
 * 用账号 + 密码换短期 HttpOnly session cookie。
 *
 * 密码只出现在本次请求体中，不落盘、不进 bundle、不随后续请求发送。
 */
export async function loginWithCredentials(
  username: string,
  password: string,
): Promise<void> {
  await axios.post(
    '/api/v1/auth/session',
    { username: username.trim(), password },
    { baseURL: '' },
  )
  setAuthState('authenticated')
}

/** 用 API key 换短期 HttpOnly session cookie（key 不落盘、不进 bundle）。 */
export async function loginWithApiKey(apiKey: string): Promise<void> {
  const csrfToken = readCsrfToken()
  await axios.post(
    '/api/v1/auth/session',
    { api_key: apiKey },
    csrfToken
      ? { baseURL: '', headers: { 'X-CSRF-Token': csrfToken } }
      : { baseURL: '' },
  )
  setAuthState('authenticated')
}

export async function logout(): Promise<void> {
  try {
    const csrfToken = readCsrfToken()
    await axios.post(
      '/api/v1/auth/logout',
      {},
      csrfToken
        ? { baseURL: '', headers: { 'X-CSRF-Token': csrfToken } }
        : { baseURL: '' },
    )
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
    // A page change or StrictMode cleanup deliberately aborts polling requests.
    if (axios.isCancel(error)) return Promise.reject(error)
    if (!axios.isAxiosError(error)) {
      // 非网络错误 —— 透传并全局兜底提示
      toast.error(getApiErrorMessage(error))
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
      toast.error(getApiErrorMessage(error))
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
  const items = response.data.map((item) => ({
    ...item,
    code: canonicalStockCode(item.code),
  }))
  const nextCursor = items.length > 0 ? items[items.length - 1].id : null
  return {
    items,
    total: Number(response.headers['x-total-count'] || items.length),
    nextCursor,
  }
}

export async function getStock(code: string): Promise<Stock> {
  const response = await api.get<Stock>(
    `/stocks/${encodeURIComponent(canonicalStockCode(code))}`,
  )
  return { ...response.data, code: canonicalStockCode(response.data.code) }
}

export async function getStockKline(
  code: string,
  startDate?: string,
  endDate?: string,
  priceSource?: 'raw' | 'legacy',
): Promise<DailyKline[]> {
  const normalizedCode = canonicalStockCode(code)
  const params = new URLSearchParams()
  if (startDate) params.append('start_date', startDate)
  if (endDate) params.append('end_date', endDate)
  if (priceSource) params.append('price_source', priceSource)
  const response = await api.get<DailyKline[]>(
    `/stocks/${encodeURIComponent(normalizedCode)}/kline?${params}`,
  )
  return response.data.map((item) => ({
    ...item,
    stock_code: canonicalStockCode(item.stock_code),
  }))
}

export async function getStockIndicators(
  code: string,
  period = 'daily',
  startDate?: string,
  endDate?: string,
): Promise<KlineResponse> {
  const normalizedCode = canonicalStockCode(code)
  const params = new URLSearchParams()
  params.append('period', period)
  if (startDate) params.append('start_date', startDate)
  if (endDate) params.append('end_date', endDate)
  const response = await api.get<KlineResponse>(
    `/stocks/${encodeURIComponent(normalizedCode)}/indicators?${params}`,
  )
  return {
    ...response.data,
    stock_code: canonicalStockCode(response.data.stock_code),
  }
}

export async function getStockOverview(code: string): Promise<StockOverview> {
  const response = await api.get<StockOverview>(
    `/stocks/${encodeURIComponent(canonicalStockCode(code))}/overview`,
  )
  return {
    ...response.data,
    stock: {
      ...response.data.stock,
      code: canonicalStockCode(response.data.stock.code),
    },
    quote: response.data.quote
      ? {
          ...response.data.quote,
          code: canonicalStockCode(response.data.quote.code),
        }
      : response.data.quote,
  }
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
    canonicalStockCodes(stockCodes),
    {
      params,
    },
  )
  return response.data
}

export async function getBacktestResults(
  stockCode?: string,
  skip = 0,
  limit = 20,
  strategyName?: string,
  sort?: 'newest' | 'return',
): Promise<{ items: BacktestListItem[]; total: number }> {
  const params = new URLSearchParams()
  if (stockCode?.trim()) params.append('stock_code', stockCode.trim())
  if (strategyName?.trim()) params.append('strategy_name', strategyName.trim())
  if (sort) params.append('sort', sort)
  params.append('skip', String(skip))
  params.append('limit', String(limit))
  const response = await api.get<BacktestListItem[]>(`/backtest/results?${params}`)
  const items = response.data.map((item) => ({
    ...item,
    stock_code: canonicalStockCode(item.stock_code),
  }))
  const totalHeader =
    response.headers['x-total-count'] ?? response.headers['X-Total-Count']
  return {
    items,
    total: Number(totalHeader ?? items.length),
  }
}

export async function getBacktestResult(id: number): Promise<BacktestResult> {
  const response = await api.get<BacktestResult>(`/backtest/${id}`)
  return {
    ...response.data,
    stock_code: canonicalStockCode(response.data.stock_code),
  }
}

// Strategy APIs
export async function getStrategies(): Promise<StrategyInfo[]> {
  const response = await api.get<StrategyInfo[]>('/strategies')
  return response.data
}

export interface SignalRequest extends ResearchExecutionOptions {
  strategy_name: string
  stock_code: string
  start_date: string
  end_date: string
  parameters?: Record<string, number | string>
}

export async function generateSignals(request: SignalRequest): Promise<SignalResponse> {
  const response = await api.post<SignalResponse>(
    '/strategies/signals',
    canonicalStockRequest(request),
  )
  return {
    ...response.data,
    stock_code: canonicalStockCode(response.data.stock_code),
  }
}

export interface StrategyBacktestRequest extends ResearchExecutionOptions {
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
    canonicalStockRequest(request),
  )
  return {
    ...response.data,
    stock_code: canonicalStockCode(response.data.stock_code),
  }
}

export interface OptimizeRequest extends ResearchExecutionOptions {
  strategy_name: string
  stock_code: string
  start_date: string
  end_date: string
  initial_capital: number
  param_grid: Record<string, number[]>
  metric: string
}

export async function submitOptimizeParameters(
  request: OptimizeRequest,
): Promise<JobSubmission> {
  const response = await api.post<JobSubmission>(
    '/strategies/optimize/submit',
    canonicalStockRequest(request),
  )
  return response.data
}

export async function submitAnalyzeStock(
  request: AgentAnalyzeRequest,
): Promise<JobSubmission> {
  const response = await api.post<JobSubmission>(
    '/agent/analyze/submit',
    canonicalStockRequest(request),
  )
  return response.data
}

export async function getAnalysisHistory(
  stockCode?: string,
  skip = 0,
  limit = 20,
): Promise<AnalysisRecord[]> {
  const params = new URLSearchParams()
  if (stockCode) params.append('stock_code', canonicalStockCode(stockCode))
  params.append('skip', String(skip))
  params.append('limit', String(limit))
  const response = await api.get<AnalysisRecord[]>(`/agent/history?${params}`)
  return response.data.map((item) => ({
    ...item,
    stock_code: canonicalStockCode(item.stock_code),
  }))
}

export async function getAnalysisDetail(
  recordId: number,
): Promise<AgentAnalyzeResponse> {
  const response = await api.get<AgentAnalyzeResponse>(`/agent/${recordId}`)
  return {
    ...response.data,
    stock_code: canonicalStockCode(response.data.stock_code),
  }
}

export async function getJobStatus<T = Record<string, unknown>>(
  jobId: string,
  signal?: AbortSignal,
): Promise<JobStatus<T>> {
  const response = await api.get<JobStatus<T>>(`/jobs/${jobId}`, { signal })
  return response.data
}

export interface JobMetricCounter {
  name: string
  value: number
  job_type?: string
  [key: string]: unknown
}

export interface JobMetrics {
  started_at: string
  counters: JobMetricCounter[]
  durations: Array<{ name: string; value_ms: number; [key: string]: unknown }>
}

export async function getJobMetrics(): Promise<JobMetrics> {
  const response = await api.get<JobMetrics>('/jobs/metrics')
  return response.data
}

export async function cancelJob(jobId: string): Promise<void> {
  await api.post(`/jobs/${jobId}/cancel`)
}

// Watchlist API
export async function getWatchlist(): Promise<WatchlistResponse> {
  const response = await api.get<WatchlistResponse>('/watchlist')
  return {
    ...response.data,
    items: response.data.items.map((item) => ({
      ...item,
      stock_code: canonicalStockCode(item.stock_code),
    })),
  }
}

export async function addToWatchlist(stockCode: string): Promise<WatchlistItem> {
  const response = await api.post<WatchlistItem>('/watchlist', {
    stock_code: canonicalStockCode(stockCode),
  })
  return {
    ...response.data,
    stock_code: canonicalStockCode(response.data.stock_code),
  }
}

export async function removeFromWatchlist(
  stockCode: string,
): Promise<{ success: boolean }> {
  const response = await api.delete<{ success: boolean }>(
    `/watchlist/${encodeURIComponent(canonicalStockCode(stockCode))}`,
  )
  return response.data
}

export async function submitScreener(): Promise<{ job_id: string }> {
  const response = await api.post<{ job_id: string }>('/screener/submit')
  return response.data
}

export interface ScreenerJobRecord {
  id: string
  job_type?: string
  status: string
  progress: number
  payload?: { stage: string; current: number; total: number; message: string }
  result?: {
    success: boolean
    total_scanned: number
    results: unknown[]
  }
  error?: string
  created_at?: string
  updated_at?: string
}

export async function getScreenerStatus(jobId: string): Promise<ScreenerJobRecord> {
  const response = await api.get(`/screener/${jobId}`)
  return response.data
}

export async function getScreenerHistory(limit = 20): Promise<ScreenerJobRecord[]> {
  const response = await api.get<ScreenerJobRecord[]>('/screener/history', {
    params: { limit },
  })
  return response.data
}

// Strategy Comparison API
export async function compareStrategies(
  request: CompareRequest,
): Promise<CompareResponse> {
  const response = await api.post<CompareResponse>(
    '/strategies/compare',
    canonicalStockRequest(request),
  )
  return {
    ...response.data,
    stock_code: canonicalStockCode(response.data.stock_code),
  }
}

// Realtime Bars API
export async function getRealtimeBars(
  code: string,
  period: string = 'daily',
  cacheForResearch = false,
): Promise<
  RealtimeFreshness & {
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
  }
> {
  const normalizedCode = canonicalStockCode(code)
  const response = await api.get<
    RealtimeFreshness & {
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
    }
  >(
    `/realtime/${encodeURIComponent(normalizedCode)}?${new URLSearchParams({
      period,
      cache_for_research: String(cacheForResearch),
    })}`,
  )
  return {
    ...response.data,
    code: canonicalStockCode(response.data.code),
    data: (Array.isArray(response.data.data) ? response.data.data : []).map((bar) => ({
      ...bar,
      symbol: canonicalStockCode(bar.symbol),
    })),
  }
}

export interface RealtimeFreshness {
  status?: 'ok' | 'empty' | 'unavailable'
  provider?: string
  served_at?: number
  fetched_at?: number
  market_at?: string
  cache_age_ms?: number
  stale?: boolean
  cache_source?: 'provider' | 'memory' | 'redis' | string
  reason?: string | null
}

// Realtime Quotes API
export interface RealtimeQuote {
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
}

export async function getRealtimeQuotes(codes: string[]): Promise<
  RealtimeFreshness & {
    success: boolean
    data: RealtimeQuote[]
  }
> {
  const normalizedCodes = codes.map(canonicalStockCode)
  const response = await api.get<
    RealtimeFreshness & { success: boolean; data: RealtimeQuote[] }
  >(`/realtime/quotes?codes=${encodeURIComponent(normalizedCodes.join(','))}`)
  return {
    ...response.data,
    data: (Array.isArray(response.data.data) ? response.data.data : []).map(
      (quote) => ({
        ...quote,
        symbol: canonicalStockCode(quote.symbol),
      }),
    ),
  }
}

// Realtime Indices API
export interface RealtimeIndex {
  symbol: string
  name: string
  close: number
  change: number
  change_percent: number
  prev_close: number
}

export async function getRealtimeIndices(): Promise<
  RealtimeFreshness & {
    success: boolean
    data: RealtimeIndex[]
  }
> {
  const response = await api.get<
    RealtimeFreshness & { success: boolean; data: RealtimeIndex[] }
  >('/realtime/indices')
  return response.data
}

export default api
