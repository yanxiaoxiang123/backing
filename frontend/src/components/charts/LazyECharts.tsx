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
import {
  chartZoomSlide,
  isNextZoomWindow,
  readChartZoomWindow,
  type ChartZoomWindow,
} from './chartZoom'
import { CHART_TEXT } from '../../styles/typography'
import { collectChartText } from './chartFonts'

const ZOOM_SLIDE_MS = 480

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
  /** Slide the data zoom window when one new bar advances it. */
  slideWindow?: boolean
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
      slideWindow = false,
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
    const slideWindowRef = useRef(slideWindow)
    const previousZoomRef = useRef<ChartZoomWindow | null>(null)
    const zoomAnimationRef = useRef<number | undefined>(undefined)
    optionRef.current = option
    revealKeyRef.current = revealKey
    slideWindowRef.current = slideWindow
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
      const animateZoom = (previous: ChartZoomWindow, next: ChartZoomWindow) => {
        if (!chartRef.current) return
        const zoom = (optionRef.current as EChartsOption).dataZoom
        const items = Array.isArray(zoom) ? zoom : zoom ? [zoom] : []
        if (!items.length) return
        const { from, to } = chartZoomSlide(previous, next)
        const applyZoom = (start: number, end: number) => {
          chartRef.current?.dispatchAction({
            type: 'dataZoom',
            batch: items.map((_, index) => ({ dataZoomIndex: index, start, end })),
          })
        }
        applyZoom(from.start, from.end)
        const startedAt = performance.now()
        const step = (now: number) => {
          const progress = Math.min(1, (now - startedAt) / ZOOM_SLIDE_MS)
          const eased = 1 - (1 - progress) ** 3
          applyZoom(
            from.start + (to.start - from.start) * eased,
            from.end + (to.end - from.end) * eased,
          )
          zoomAnimationRef.current =
            progress < 1 ? requestAnimationFrame(step) : undefined
        }
        zoomAnimationRef.current = requestAnimationFrame(step)
      }
      let fontRefreshTimer: number | undefined
      let loadedChartText = ''
      const refreshForFonts = () => {
        if (revealing) {
          scheduleFontRefresh()
          return
        }
        const chart = chartRef.current
        if (!chart) return
        // Canvas text does not inherit CSS. Re-apply the shared face and
        // re-measure labels after a delayed CJK subset arrives.
        chart.setOption(
          { textStyle: { fontFamily: CHART_TEXT.fontFamily } },
          { notMerge: false, lazyUpdate: false },
        )
        chart.resize()
      }
      const scheduleFontRefresh = () => {
        window.clearTimeout(fontRefreshTimer)
        fontRefreshTimer = window.setTimeout(() => {
          fontRefreshTimer = undefined
          if (!disposed) refreshForFonts()
        }, 150)
      }
      const loadChartFonts = () => {
        if (typeof document.fonts === 'undefined') return
        const text = collectChartText(optionRef.current)
        if (!text || text === loadedChartText) return
        loadedChartText = text
        // Canvas does not request a webfont by itself; loading the characters
        // the option can paint makes the CJK subsets fetch before the refresh.
        void document.fonts
          .load(`${CHART_TEXT.label}px "Noto Sans SC Variable"`, text)
          .then(() => {
            if (!disposed) scheduleFontRefresh()
          })
          .catch(() => {})
      }
      const applyOption = () => {
        if (!chartRef.current) return
        const nextZoom = readChartZoomWindow(optionRef.current)
        const previousZoom = previousZoomRef.current
        if (zoomAnimationRef.current) {
          cancelAnimationFrame(zoomAnimationRef.current)
          zoomAnimationRef.current = undefined
        }
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
        if (
          slideWindowRef.current &&
          previousZoom &&
          nextZoom &&
          isNextZoomWindow(previousZoom, nextZoom)
        ) {
          animateZoom(previousZoom, nextZoom)
        }
        previousZoomRef.current = nextZoom
        loadChartFonts()
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
        if (typeof document.fonts !== 'undefined') {
          void document.fonts.ready.then(() => {
            if (!disposed) scheduleFontRefresh()
          })
          document.fonts.addEventListener('loadingdone', scheduleFontRefresh)
        }
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
        if (zoomAnimationRef.current) {
          cancelAnimationFrame(zoomAnimationRef.current)
          zoomAnimationRef.current = undefined
        }
        if (typeof document.fonts !== 'undefined') {
          document.fonts.removeEventListener('loadingdone', scheduleFontRefresh)
        }
        window.clearTimeout(fontRefreshTimer)
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
        if (zoomAnimationRef.current) {
          cancelAnimationFrame(zoomAnimationRef.current)
          zoomAnimationRef.current = undefined
        }
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
        data-chart-font={CHART_TEXT.fontFamily}
        role={props.role ?? 'img'}
        aria-label={summary ?? props['aria-label'] ?? '交互式数据图表'}
      />
    )
  },
)

LazyECharts.displayName = 'LazyECharts'
