import { useCallback, useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getStocks } from '../services/stocks'
import type { Stock } from '../types'
import { stockSearchKeys } from '../services/queryKeys'
import { normalizeStockCode, sameStock } from '../utils/stockIdentity'

const RECENT_KEY = 'stocksearch_recent'
const MAX_RECENT = 8

export interface StockOption {
  code: string
  name: string
  label: string
}

export interface StockSearchResult extends StockOption {
  isRecent?: boolean
}

function toOptions(stocks: Stock[]): StockOption[] {
  return stocks.map((stock) => ({
    code: stock.code,
    name: stock.name,
    label: `${stock.code} - ${stock.name}`,
  }))
}

function loadRecent(): StockOption[] {
  try {
    const raw = localStorage.getItem(RECENT_KEY)
    const parsed: unknown = raw ? JSON.parse(raw) : []
    if (!Array.isArray(parsed)) return []
    return parsed.filter((item): item is StockOption =>
      Boolean(
        item &&
        typeof item === 'object' &&
        typeof (item as StockOption).code === 'string' &&
        typeof (item as StockOption).name === 'string' &&
        typeof (item as StockOption).label === 'string',
      ),
    )
  } catch {
    return []
  }
}

function saveRecent(options: StockOption[]) {
  try {
    localStorage.setItem(RECENT_KEY, JSON.stringify(options.slice(0, MAX_RECENT)))
  } catch {
    // Storage may be unavailable in private browsing; searching still works.
  }
}

export function useStockSearch() {
  const [query, setQuery] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const [recent, setRecent] = useState<StockOption[]>(loadRecent)

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedQuery(query.trim()), 250)
    return () => window.clearTimeout(timer)
  }, [query])

  const searchQuery = useQuery({
    queryKey: stockSearchKeys.query(debouncedQuery),
    queryFn: () => getStocks(undefined, 0, 50, debouncedQuery),
    enabled: debouncedQuery.length > 0,
    staleTime: 60_000,
    retry: 1,
  })

  const serverOptions = useMemo(
    () => toOptions(searchQuery.data?.items ?? []),
    [searchQuery.data],
  )

  const search = useCallback(
    (input: string, watchlistCodes?: string[]): StockSearchResult[] => {
      const normalized = input.trim()
      if (!normalized) {
        const result: StockSearchResult[] = []
        const seen = new Set<string>()
        for (const option of recent) {
          const code = normalizeStockCode(option.code) ?? option.code
          if (!seen.has(code)) {
            result.push({ ...option, code, isRecent: true })
            seen.add(code)
          }
        }
        for (const code of watchlistCodes ?? []) {
          const normalizedCode = normalizeStockCode(code) ?? code
          if (!Array.from(seen).some((item) => sameStock(item, normalizedCode))) {
            result.push({ code: normalizedCode, name: '', label: normalizedCode })
            seen.add(normalizedCode)
          }
        }
        return result
      }
      if (normalized.toLowerCase() !== debouncedQuery.toLowerCase()) return []
      return serverOptions
    },
    [debouncedQuery, recent, serverOptions],
  )

  const trackSelection = useCallback((option: StockOption) => {
    setRecent((previous) => {
      const next = [
        option,
        ...previous.filter((item) => !sameStock(item.code, option.code)),
      ]
      saveRecent(next)
      return next.slice(0, MAX_RECENT)
    })
  }, [])

  return {
    query,
    setQuery,
    allOptions: serverOptions,
    recent,
    loading: searchQuery.isFetching,
    error: searchQuery.error,
    reload: searchQuery.refetch,
    search,
    trackSelection,
  }
}
