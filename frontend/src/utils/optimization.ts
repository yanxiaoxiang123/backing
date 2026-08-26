import type { StrategyInfo } from '../types'

const decimalPlaces = (step: number) => {
  const text = String(step)
  return text.includes('.') ? text.length - text.indexOf('.') - 1 : 0
}

/** Build a representative grid without exceeding the backend combination budget. */
export function buildOptimizationGrid(
  strategy: StrategyInfo,
  maxCombinations = 200,
  includedNames?: Set<string>,
): Record<string, number[]> {
  const dimensions = Object.entries(strategy.parameters)
    .filter(
      ([name, config]) =>
        config.type === 'slider' &&
        config.min !== undefined &&
        config.max !== undefined &&
        (!includedNames || includedNames.has(name)),
    )
    .map(([name, config]) => {
      const step = Number(config.step || 1)
      const capacity = Math.max(
        1,
        Math.floor((Number(config.max) - Number(config.min)) / step + 1e-9) + 1,
      )
      return { name, config, step, capacity, count: Math.min(2, capacity) }
    })

  if (dimensions.length === 0) return {}

  const combinations = () =>
    dimensions.reduce((total, dimension) => total * dimension.count, 1)

  // Spend the remaining budget across dimensions in round-robin order.
  let expanded = true
  while (expanded) {
    expanded = false
    for (const dimension of dimensions) {
      if (dimension.count >= dimension.capacity) continue
      const nextTotal = (combinations() / dimension.count) * (dimension.count + 1)
      if (nextTotal <= maxCombinations) {
        dimension.count += 1
        expanded = true
      }
    }
  }

  return Object.fromEntries(
    dimensions.map(({ name, config, step, capacity, count }) => {
      const precision = decimalPlaces(step)
      const indexes =
        count === 1
          ? [0]
          : Array.from({ length: count }, (_, index) =>
              Math.round((index * (capacity - 1)) / (count - 1)),
            )
      const values = indexes.map((index) =>
        Number((Number(config.min) + index * step).toFixed(precision)),
      )
      return [name, [...new Set(values)]]
    }),
  )
}
