import { useState, useCallback } from 'react'

const PREFIX = 'backing_'

export function usePersistedState<T>(
  key: string,
  defaultValue: T,
): [T, (value: T | ((prev: T) => T)) => void] {
  const storageKey = PREFIX + key

  const [state, setState] = useState<T>(() => {
    try {
      const raw = sessionStorage.getItem(storageKey)
      if (raw !== null) return JSON.parse(raw) as T
    } catch { /* ignore */ }
    return defaultValue
  })

  const setPersistedState = useCallback(
    (value: T | ((prev: T) => T)) => {
      setState((prev) => {
        const next = typeof value === 'function' ? (value as (prev: T) => T)(prev) : value
        try {
          sessionStorage.setItem(storageKey, JSON.stringify(next))
        } catch { /* quota exceeded */ }
        return next
      })
    },
    [storageKey],
  )

  return [state, setPersistedState]
}