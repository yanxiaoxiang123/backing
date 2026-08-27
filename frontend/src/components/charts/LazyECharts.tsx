import {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useRef,
  type HTMLAttributes,
  type ReactNode,
} from 'react'
import type { EChartsOption } from 'echarts'
import type { EChartsType } from 'echarts/core'

let echartsPromise: Promise<typeof import('echarts/core')> | null = null

function loadEcharts() {
  if (!echartsPromise) {
    echartsPromise = Promise.all([
      import('echarts/core'),
      import('echarts/charts'),
      import('echarts/components'),
      import('echarts/renderers'),
    ]).then(([core, charts, components, renderers]) => {
      core.use([
        renderers.CanvasRenderer,
        charts.BarChart,
        charts.CandlestickChart,
        charts.LineChart,
        charts.ScatterChart,
        components.DataZoomComponent,
        components.GridComponent,
        components.LegendComponent,
        components.MarkLineComponent,
        components.MarkPointComponent,
        components.TooltipComponent,
      ])
      return core
    })
  }
  return echartsPromise
}

export interface LazyEChartsProps extends HTMLAttributes<HTMLDivElement> {
  option: EChartsOption | Record<string, unknown>
  opts?: { renderer?: 'canvas' | 'svg' }
  notMerge?: boolean
  lazyUpdate?: boolean
  summary?: string
}

export const LazyECharts = forwardRef<HTMLDivElement, LazyEChartsProps>(
  function LazyECharts(
    { option, opts, notMerge = false, lazyUpdate = false, summary, ...props },
    ref,
  ) {
    const containerRef = useRef<HTMLDivElement>(null)
    const chartRef = useRef<EChartsType | null>(null)
    const optionRef = useRef(option)
    optionRef.current = option
    useImperativeHandle(ref, () => containerRef.current as HTMLDivElement, [])

    useEffect(() => {
      const container = containerRef.current
      if (!container || import.meta.env.MODE === 'test') return
      let disposed = false
      let resizeObserver: ResizeObserver | null = null
      void loadEcharts().then((core) => {
        if (disposed) return
        const chart = core.init(container, undefined, {
          renderer: opts?.renderer ?? 'canvas',
        })
        chartRef.current = chart
        chart.setOption(optionRef.current as EChartsOption, { notMerge, lazyUpdate })
        if (typeof ResizeObserver !== 'undefined') {
          resizeObserver = new ResizeObserver(() => chart.resize())
          resizeObserver.observe(container)
        }
      })
      return () => {
        disposed = true
        resizeObserver?.disconnect()
        chartRef.current?.dispose()
        chartRef.current = null
      }
    }, [lazyUpdate, notMerge, opts?.renderer])

    useEffect(() => {
      chartRef.current?.setOption(option as EChartsOption, { notMerge, lazyUpdate })
    }, [lazyUpdate, notMerge, option])

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

export function ChartRegion({
  label,
  children,
}: {
  label: string
  children: ReactNode
}) {
  return (
    <div className="chart-region" role="group" aria-label={label}>
      {children}
    </div>
  )
}
