import { useEffect, useRef } from 'react'

export function useScrollMemory(key: string, ready: boolean) {
  const position = useRef(0)
  useEffect(() => {
    const save = () => {
      position.current = window.scrollY
      try {
        sessionStorage.setItem(`backing_scroll:${key}`, String(position.current))
      } catch {
        /* Storage is optional. */
      }
    }
    window.addEventListener('scroll', save, { passive: true })
    return () => window.removeEventListener('scroll', save)
  }, [key])
  useEffect(() => {
    if (!ready) return
    let stored = 0
    try {
      stored = Number(sessionStorage.getItem(`backing_scroll:${key}`)) || 0
    } catch {
      /* Storage is optional. */
    }
    const frame = window.requestAnimationFrame(() => window.scrollTo(0, stored))
    return () => window.cancelAnimationFrame(frame)
  }, [key, ready])
}
