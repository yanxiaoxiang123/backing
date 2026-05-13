import { useState, useEffect, useCallback, useRef } from 'react'
import { getAllStocks } from '../services/api'
import type { Stock } from '../types'

const RECENT_KEY = 'stocksearch_recent'
const MAX_RECENT = 8

export interface StockOption {
  code: string
  name: string
  label: string
}

let cachedStocks: StockOption[] | null = null
let cachePromise: Promise<StockOption[]> | null = null

function toOptions(stocks: Stock[]): StockOption[] {
  return stocks.map(s => ({
    code: s.code,
    name: s.name,
    label: `${s.code} - ${s.name}`,
  }))
}

function loadRecent(): StockOption[] {
  try {
    const raw = localStorage.getItem(RECENT_KEY)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

function saveRecent(options: StockOption[]) {
  try {
    localStorage.setItem(RECENT_KEY, JSON.stringify(options.slice(0, MAX_RECENT)))
  } catch { /* quota exceeded – ignore */ }
}

export function useStockSearch() {
  const [allOptions, setAllOptions] = useState<StockOption[]>(() => cachedStocks ?? [])
  const [recent, setRecent] = useState<StockOption[]>(loadRecent)
  const [loading, setLoading] = useState(!cachedStocks)
  const loaded = useRef(!!cachedStocks)

  useEffect(() => {
    if (loaded.current) return
    loaded.current = true

    const load = async () => {
      if (cachePromise) return cachePromise
      cachePromise = (async () => {
        const stocks = await getAllStocks()
        const opts = toOptions(stocks)
        cachedStocks = opts
        setAllOptions(opts)
        setLoading(false)
        return opts
      })()
      return cachePromise
    }
    load()
  }, [])

  const search = useCallback(
    (query: string, watchlistCodes?: string[]): StockOption[] => {
      const source = allOptions.length ? allOptions : cachedStocks ?? []
      if (!query) {
        // Show recent + watchlist (when no query)
        const seen = new Set<string>()
        const result: StockOption[] = []

        // Recent selections first
        for (const r of recent) {
          if (!seen.has(r.code)) {
            result.push(r)
            seen.add(r.code)
          }
        }
        // Then watchlist
        if (watchlistCodes) {
          for (const code of watchlistCodes) {
            if (!seen.has(code)) {
              const match = source.find(o => o.code === code)
              if (match) {
                result.push(match)
                seen.add(code)
              }
            }
          }
        }
        return result
      }

      const q = query.toLowerCase()
      return source.filter(
        o => o.code.toLowerCase().includes(q) || o.name.toLowerCase().includes(q),
      )
    },
    [allOptions, recent],
  )

  const trackSelection = useCallback((option: StockOption) => {
    const next = [option, ...recent.filter(r => r.code !== option.code)]
    setRecent(next)
    saveRecent(next)
  }, [recent])

  return { allOptions, recent, loading, search, trackSelection }
}