import type { StrategyBacktestRequest } from '../services/api'
import type { StrategyBacktestResponse, StrategyInfo } from '../types'

export type StrategyParameters = Record<string, number | string>
export interface SavedStrategyRun {
  version: 1
  request: StrategyBacktestRequest
  result: StrategyBacktestResponse
}

const record = (value: unknown): value is Record<string, unknown> =>
  value !== null && typeof value === 'object' && !Array.isArray(value)
const finite = (value: unknown): value is number =>
  typeof value === 'number' && Number.isFinite(value)
const text = (value: unknown): value is string =>
  typeof value === 'string' && value.length > 0
const parameterValue = (value: unknown) => typeof value === 'string' || finite(value)

export function mergeStrategyParameters(
  strategy: StrategyInfo | undefined,
  saved: unknown,
): StrategyParameters {
  if (!strategy) return {}
  return Object.fromEntries(
    Object.entries(strategy.parameters).map(([key, config]) => {
      const value = record(saved) ? saved[key] : undefined
      const valid =
        parameterValue(value) &&
        typeof value === typeof config.default &&
        (typeof value !== 'number' ||
          ((config.min === undefined || value >= config.min) &&
            (config.max === undefined || value <= config.max))) &&
        (!config.options?.length ||
          config.options.some((option) => option.value === value))
      return [key, valid ? value : config.default]
    }),
  ) as StrategyParameters
}

export function readSavedStrategyRun(value: unknown): SavedStrategyRun | null {
  if (!record(value) || value.version !== 1) return null
  const { request, result } = value
  if (!record(request) || !record(result)) return null
  const identity = ['stock_code', 'strategy_name', 'start_date', 'end_date'] as const
  if (
    !identity.every((key) => text(request[key]) && text(result[key])) ||
    request.stock_code !== result.stock_code ||
    request.strategy_name !== result.strategy_name ||
    !finite(request.initial_capital) ||
    request.initial_capital <= 0 ||
    request.initial_capital !== result.initial_capital ||
    !finite(result.final_capital) ||
    result.success !== true ||
    !Number.isSafeInteger(result.result_id) ||
    Number(result.result_id) <= 0 ||
    (request.parameters !== undefined &&
      (!record(request.parameters) ||
        !Object.values(request.parameters).every(parameterValue))) ||
    !['raw', 'legacy', 'auto', undefined].includes(
      request.price_source as string | undefined,
    ) ||
    !['verified', 'price_only', undefined].includes(
      request.corporate_action_mode as string | undefined,
    ) ||
    (request.dividend_tax_rate !== undefined && !finite(request.dividend_tax_rate)) ||
    !record(result.metrics) ||
    ![
      'total_return',
      'annual_return',
      'sharpe_ratio',
      'max_drawdown',
      'win_rate',
      'profit_factor',
      'total_trades',
    ].every((key) => finite((result.metrics as Record<string, unknown>)[key])) ||
    !Array.isArray(result.trades) ||
    !result.trades.every(
      (trade) =>
        record(trade) &&
        text(trade.date) &&
        text(trade.action) &&
        ['price', 'quantity', 'amount'].every((key) => finite(trade[key])),
    ) ||
    (result.portfolio_values !== undefined &&
      (!Array.isArray(result.portfolio_values) ||
        !result.portfolio_values.every(
          (point) =>
            record(point) &&
            text(point.date) &&
            ['total_value', 'cash', 'position_value', 'position'].every((key) =>
              finite(point[key]),
            ),
        )))
  )
    return null
  return value as unknown as SavedStrategyRun
}

export function sameStrategyRequest(
  left: StrategyBacktestRequest,
  right: StrategyBacktestRequest,
): boolean {
  const fields = [
    'stock_code',
    'strategy_name',
    'start_date',
    'end_date',
    'initial_capital',
    'price_source',
    'corporate_action_mode',
    'dividend_tax_rate',
  ] as const
  if (fields.some((field) => left[field] !== right[field])) return false
  const leftParams = left.parameters ?? {}
  const rightParams = right.parameters ?? {}
  const keys = new Set([...Object.keys(leftParams), ...Object.keys(rightParams)])
  return Array.from(keys).every((key) => leftParams[key] === rightParams[key])
}
