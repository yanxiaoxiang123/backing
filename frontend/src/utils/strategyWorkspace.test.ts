import { describe, expect, it } from 'vitest'
import type { StrategyBacktestRequest } from '../services/api'
import type { StrategyInfo } from '../types'
import {
  mergeStrategyParameters,
  readSavedStrategyRun,
  sameStrategyRequest,
} from './strategyWorkspace'

const strategy: StrategyInfo = {
  name: 'ma_cross',
  description: 'Moving average crossover',
  parameters: {
    short_window: { type: 'slider', default: 5, min: 2, max: 30 },
    long_window: { type: 'slider', default: 20, min: 10, max: 120 },
  },
}
const request: StrategyBacktestRequest = {
  stock_code: 'sh.600000',
  strategy_name: 'ma_cross',
  start_date: '2025-11-04',
  end_date: '2026-11-04',
  initial_capital: 100000,
  parameters: { short_window: 8, long_window: 20 },
  price_source: 'raw',
  corporate_action_mode: 'verified',
  dividend_tax_rate: 0,
}
const saved = {
  version: 1,
  request,
  result: {
    success: true,
    result_id: 41,
    ...request,
    final_capital: 105200,
    metrics: {
      total_return: 5.2,
      annual_return: 5.2,
      sharpe_ratio: 0.87,
      max_drawdown: 3.1,
      win_rate: 50,
      profit_factor: 1.4,
      total_trades: 2,
    },
    trades: [
      { date: '2026-10-03', action: 'buy', price: 10, quantity: 1000, amount: 10000 },
    ],
    portfolio_values: [
      {
        date: '2026-10-03',
        total_value: 100000,
        cash: 90000,
        position_value: 10000,
        position: 1000,
      },
    ],
  },
}

describe('strategy workspace recovery', () => {
  it('restores known edited parameters without losing new catalog defaults', () => {
    expect(mergeStrategyParameters(strategy, { short_window: 8, removed: 9 })).toEqual({
      short_window: 8,
      long_window: 20,
    })
  })

  it('discards invalid edits without throwing when storage has an unexpected shape', () => {
    expect(
      mergeStrategyParameters(strategy, {
        short_window: 'oops',
        long_window: Infinity,
      }),
    ).toEqual({ short_window: 5, long_window: 20 })
    expect(mergeStrategyParameters(strategy, null)).toEqual({
      short_window: 5,
      long_window: 20,
    })
    expect(mergeStrategyParameters(undefined, { short_window: 8 })).toEqual({})
  })

  it('keeps a saved response and its exact execution request together', () => {
    expect(readSavedStrategyRun(JSON.parse(JSON.stringify(saved)))).toEqual(saved)
  })

  it('retains the original request when the returned trading dates are narrower', () => {
    const effective = {
      ...saved,
      result: { ...saved.result, start_date: '2025-11-05', end_date: '2026-11-03' },
    }
    expect(readSavedStrategyRun(effective)).toEqual(effective)
  })

  it.each([
    null,
    {},
    { ...saved, version: 2 },
    { ...saved, request: { ...request, parameters: [] } },
    { ...saved, result: { ...saved.result, metrics: null } },
    { ...saved, result: { ...saved.result, trades: [null] } },
    { ...saved, result: { ...saved.result, portfolio_values: [{}] } },
  ])('ignores malformed saved runs: %j', (value) => {
    expect(readSavedStrategyRun(value)).toBeNull()
  })

  it('compares parameter values independently of key ordering', () => {
    expect(
      sameStrategyRequest(request, {
        ...request,
        parameters: { long_window: 20, short_window: 8 },
      }),
    ).toBe(true)
  })

  it.each([
    { stock_code: 'sz.000002' },
    { parameters: { short_window: 9, long_window: 20 } },
    { price_source: 'legacy' as const },
    { corporate_action_mode: 'price_only' as const },
    { dividend_tax_rate: 0.1 },
    { initial_capital: 200000 },
  ])('marks the saved run as different after changing %j', (patch) => {
    expect(sameStrategyRequest(request, { ...request, ...patch })).toBe(false)
  })
})
