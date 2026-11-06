import {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useRef,
  type HTMLAttributes,
} from 'react'
import type { EChartsOption } from 'echarts'
import type { EChartsType } from './echartsCustom'
import {
  hasRevealableLine,
  LINE_REVEAL_MS,
  settledChartOption,
} from './chartInteraction'

let echartsPromise: Promise<typeof import('./echartsCustom').default> | null = null

function loadEcharts() {
  if (!echartsPromise) {
    echartsPromise = import('./echartsCustom').then((m) => m.default)
  }
  return echartsPromise
}

export interface LazyEChartsProps extends HTMLAttributes<HTMLDivElement> {
  option: EChartsOption | Record<string, unknown>
  opts?: { renderer?: 'canvas' | 'svg' }
  notMerge?: boolean
  lazyUpdate?: boolean
  summary?: string
  resetKey?: number
  /** Replay only when the displayed instrument or time window changes. */
  revealKey?: string | number
}

export const LazyECharts = forwardRef<HTMLDivElement, LazyEChartsProps>(
  function LazyECharts(
    {
      option,
      opts,
      notMerge = false,
      lazyUpdate = false,
      summary,
      resetKey = 0,
      revealKey,
      ...props
    },
    ref,
  ) {
    const containerRef = useRef<HTMLDivElement>(null)
    const chartRef = useRef<EChartsType | null>(null)
    const optionRef = useRef(option)
    const revealKeyRef = useRef(revealKey)
    const applyOptionRef = useRef<(() => void) | null>(null)
    const finishRevealRef = useRef<(() => void) | null>(null)
    optionRef.current = option
    revealKeyRef.current = revealKey
    useImperativeHandle(ref, () => containerRef.current as HTMLDivElement, [])

    useEffect(() => {
      const container = containerRef.current
      if (!container || import.meta.env.MODE === 'test') return
      let disposed = false
      let resizeObserver: ResizeObserver | null = null
      let dragging = false
      let revealedKey: string | number | undefined
      let revealing = false
      let revealTimer: number | undefined
      const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)')
      const clearRevealTimer = () => {
        window.clearTimeout(revealTimer)
        revealTimer = undefined
      }
      const finishReveal = () => {
        clearRevealTimer()
        if (!revealing || !chartRef.current) return
        revealing = false
        chartRef.current.setOption(settledChartOption(optionRef.current), {
          notMerge: false,
          lazyUpdate: false,
        })
      }
      const applyOption = () => {
        if (!chartRef.current) return
        clearRevealTimer()
        const key = revealKeyRef.current
        const newLine =
          key !== undefined &&
          key !== revealedKey &&
          hasRevealableLine(optionRef.current)
        if (newLine) revealedKey = key
        revealing = newLine && !reducedMotion.matches
        // notMerge still reuses ECharts' line view and its completed clip.
        // Explicit dataset changes need a fresh view for the native entrance.
        if (revealing) chartRef.current.clear()
        chartRef.current.setOption(settledChartOption(optionRef.current, revealing), {
          notMerge: notMerge || revealing,
          lazyUpdate: revealing ? false : lazyUpdate,
        })
        if (revealing) {
          revealTimer = window.setTimeout(finishReveal, LINE_REVEAL_MS)
        }
      }
      applyOptionRef.current = applyOption
      finishRevealRef.current = finishReveal
      let pointer = { clientX: 0, clientY: 0 }
      const start = () => {
        finishReveal()
        dragging = true
      }
      const track = (event: PointerEvent) => {
        pointer = { clientX: event.clientX, clientY: event.clientY }
      }
      const end = () => {
        dragging = false
      }
      const cancel = () => {
        finishReveal()
        if (!dragging) return
        // Finish zrender's existing drag lifecycle on touch/pointer cancellation.
        container.dispatchEvent(
          new MouseEvent('mouseup', { bubbles: true, ...pointer }),
        )
        end()
      }
      container.addEventListener('pointerdown', start)
      container.addEventListener('touchstart', start)
      container.addEventListener('pointermove', track)
      container.addEventListener('wheel', finishReveal, { passive: true })
      reducedMotion.addEventListener('change', finishReveal)
      window.addEventListener('pointercancel', cancel)
      window.addEventListener('touchcancel', cancel)
      window.addEventListener('blur', cancel)
      window.addEventListener('mouseup', end)
      window.addEventListener('touchend', end)
      void loadEcharts().then((core) => {
        if (disposed) return
        const chart = core.init(container, undefined, {
          renderer: opts?.renderer ?? 'canvas',
        })
        chartRef.current = chart
        applyOption()
        if (typeof ResizeObserver !== 'undefined') {
          let width = container.clientWidth
          let height = container.clientHeight
          resizeObserver = new ResizeObserver(() => {
            // The observer's initial notification must not cancel the entrance.
            const nextWidth = container.clientWidth
            const nextHeight = container.clientHeight
            if (width === nextWidth && height === nextHeight) return
            width = nextWidth
            height = nextHeight
            finishReveal()
            chart.resize()
          })
          resizeObserver.observe(container)
        }
      })
      return () => {
        disposed = true
        clearRevealTimer()
        applyOptionRef.current = null
        finishRevealRef.current = null
        container.removeEventListener('pointerdown', start)
        container.removeEventListener('touchstart', start)
        container.removeEventListener('pointermove', track)
        container.removeEventListener('wheel', finishReveal)
        reducedMotion.removeEventListener('change', finishReveal)
        window.removeEventListener('pointercancel', cancel)
        window.removeEventListener('touchcancel', cancel)
        window.removeEventListener('blur', cancel)
        window.removeEventListener('mouseup', end)
        window.removeEventListener('touchend', end)
        resizeObserver?.disconnect()
        chartRef.current?.dispose()
        chartRef.current = null
      }
    }, [lazyUpdate, notMerge, opts?.renderer])

    useEffect(() => {
      applyOptionRef.current?.()
    }, [lazyUpdate, notMerge, option, revealKey])

    useEffect(() => {
      const zoom = (optionRef.current as EChartsOption).dataZoom
      const items = Array.isArray(zoom) ? zoom : zoom ? [zoom] : []
      // Reset ranges only: retain legend selections and the current data.
      if (resetKey && items.length) {
        finishRevealRef.current?.()
        chartRef.current?.dispatchAction({
          type: 'dataZoom',
          batch: items.map((item, dataZoomIndex) => ({
            dataZoomIndex,
            start: item.start ?? 0,
            end: item.end ?? 100,
            startValue: item.startValue,
            endValue: item.endValue,
          })),
        })
      }
    }, [resetKey])

    return (
      <div
        ref={containerRef}
        {...props}
        role={props.role ?? 'img'}
        aria-label={summary ?? props['aria-label'] ?? '交互式数据图表'}
      />
    )
  },
)

LazyECharts.displayName = 'LazyECharts'
