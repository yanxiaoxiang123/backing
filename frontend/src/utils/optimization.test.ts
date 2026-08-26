import { describe, expect, it } from 'vitest'

import type { StrategyInfo } from '../types'
import { buildOptimizationGrid } from './optimization'

const strategy: StrategyInfo = {
  name: 'ma_cross',
  description: 'test',
  parameters: {
    short_period: { type: 'slider', default: 5, min: 1, max: 30, step: 1 },
    long_period: { type: 'slider', default: 20, min: 10, max: 100, step: 1 },
  },
}

describe('buildOptimizationGrid', () => {
  it('keeps the Cartesian product within the backend budget', () => {
    const grid = buildOptimizationGrid(strategy, 200)
    const combinations = Object.values(grid).reduce(
      (total, values) => total * values.length,
      1,
    )

    expect(combinations).toBeLessThanOrEqual(200)
    expect(combinations).toBeGreaterThan(1)
    expect(grid.short_period[0]).toBe(1)
    expect(grid.short_period[grid.short_period.length - 1]).toBe(30)
    expect(grid.long_period[grid.long_period.length - 1]).toBe(100)
  })

  it('can restrict optimization to supported parameters', () => {
    const grid = buildOptimizationGrid(strategy, 200, new Set(['short_period']))
    expect(Object.keys(grid)).toEqual(['short_period'])
  })
})
