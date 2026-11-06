import { useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

const positiveInt = (value: string | null, fallback: number) =>
  value &&
  /^\d+$/.test(value) &&
  Number.isSafeInteger(Number(value)) &&
  Number(value) > 0
    ? Number(value)
    : fallback

export function useHistoryLocation() {
  const [params, setParams] = useSearchParams()
  const stock = params.get('stock') ?? ''
  const strategy = params.get('strategy') ?? ''
  const page = positiveInt(params.get('page'), 1)
  const requestedSize = positiveInt(params.get('page_size'), 20)
  const pageSize = [10, 20, 50, 100].includes(requestedSize) ? requestedSize : 20
  const sort: 'return' | 'newest' =
    params.get('sort') === 'return' ? 'return' : 'newest'
  const selectedId = positiveInt(params.get('result'), 0) || null
  const [stockInput, setStockInput] = useState(stock)
  const [strategyInput, setStrategyInput] = useState(strategy)
  const update = useCallback(
    (values: Record<string, string | number | null>, replace = false) => {
      setParams(
        (current) => {
          const next = new URLSearchParams(current)
          Object.entries(values).forEach(([key, value]) => {
            if (value === null || value === '') next.delete(key)
            else next.set(key, String(value))
          })
          return next
        },
        { replace },
      )
    },
    [setParams],
  )
  useEffect(() => {
    setStockInput(stock)
    setStrategyInput(strategy)
  }, [stock, strategy])
  useEffect(() => {
    if (stockInput.trim() === stock && strategyInput.trim() === strategy) return
    const timer = window.setTimeout(() => {
      update(
        { stock: stockInput.trim(), strategy: strategyInput.trim(), page: 1 },
        true,
      )
    }, 300)
    return () => window.clearTimeout(timer)
  }, [stockInput, strategyInput, stock, strategy, update])
  const scrollParams = new URLSearchParams(params)
  scrollParams.delete('result')
  return {
    stock,
    strategy,
    page,
    pageSize,
    sort,
    selectedId,
    stockInput,
    setStockInput,
    strategyInput,
    setStrategyInput,
    update,
    scrollKey: `/history?${scrollParams}`,
  }
}
