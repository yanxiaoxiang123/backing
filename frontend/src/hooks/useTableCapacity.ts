import { useLayoutEffect, useState, type RefObject } from 'react'

/** Measure actual table space so server pagination never needs an inner scrollbar. */
export function useTableCapacity(area: RefObject<HTMLDivElement>) {
  const [capacity, setCapacity] = useState(20)
  useLayoutEffect(() => {
    const element = area.current
    if (!element) return
    let frame = 0
    const measure = () => {
      const height = element.getBoundingClientRect().height
      if (height <= 0) return
      const rowHeight =
        element.querySelector('.stock-row-measure')?.getBoundingClientRect().height ||
        36
      const headHeight =
        element.querySelector('.stock-head-measure')?.getBoundingClientRect().height ||
        36
      const next = Math.max(
        1,
        Math.min(100, Math.floor((height - headHeight - 2) / rowHeight)),
      )
      setCapacity((previous) => (previous === next ? previous : next))
    }
    const schedule = () => {
      cancelAnimationFrame(frame)
      frame = requestAnimationFrame(measure)
    }
    measure()
    const observer =
      typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(schedule)
    observer?.observe(element)
    window.addEventListener('resize', schedule)
    return () => {
      cancelAnimationFrame(frame)
      observer?.disconnect()
      window.removeEventListener('resize', schedule)
    }
  }, [area])
  return capacity
}
