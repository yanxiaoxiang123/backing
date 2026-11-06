/** DL experiments use the backend session; remote credentials stay server-side. */
import api from './api'
import { normalizeStockCode } from '../utils/stockIdentity'
import type { JobSubmission } from '../types'

export type DLModelId = 'kronos-small' | 'kronos-base' | 'timesfm-2.5' | 'legacy'
export type DLExperimentKind = 'predict' | 'backtest'

export interface DLExperimentRequest {
  model: DLModelId
  stock_code: string
  kline_days: number
  prediction_days: number
  start_date?: string
  end_date?: string
  initial_capital?: number
}

export interface DLBar {
  date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
  amount?: number
  ohlc_valid?: boolean
}

export interface DLForecast {
  stock_code: string
  current_price: number
  last_date: string
  prediction_dates: string[]
  predicted_prices: number[]
  kline_data: DLBar[]
  predicted_klines?: DLBar[]
  forecast_target?: 'close' | 'ohlcv_amount'
  model?: DLModelId
  prediction_backend?: string
  input_start?: string
  execution_time_ms?: number
  model_metadata?: { model_revision?: string; execution_time_ms?: number }
  experiment?: DLExperimentRequest
}

export interface DLBacktest {
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
    cost?: number
    revenue?: number
    return?: number
    profit?: number
    fees?: number
  }>
  portfolio_values: number[]
  dates: string[]
  close_prices: number[]
  model?: DLModelId
  experiment?: DLExperimentRequest
  execution_time_ms?: number
}

export interface DLJobResult {
  success: boolean
  data: DLForecast | DLBacktest
}

export interface DLModelCatalog {
  models: Array<{
    id: DLModelId
    name: string
    available: boolean
    min_context: number
    max_context: number
    min_horizon: number
    max_horizon: number
    reason?: string | null
    output_fields?: string[]
  }>
  remote: { available: boolean; busy?: boolean; phase?: string; loaded_model?: string }
}

export async function getDLModels(): Promise<DLModelCatalog> {
  const response = await api.get<DLModelCatalog>('/dl/models')
  return response.data
}

export async function submitDLExperiment(
  kind: DLExperimentKind,
  request: DLExperimentRequest,
  idempotencyKey: string,
): Promise<JobSubmission> {
  const response = await api.post<JobSubmission>(
    `/dl/${kind}/submit`,
    {
      ...request,
      stock_code: normalizeStockCode(request.stock_code) ?? request.stock_code,
    },
    { headers: { 'Idempotency-Key': idempotencyKey } },
  )
  return response.data
}
