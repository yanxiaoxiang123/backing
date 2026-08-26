import { useEffect, useRef, useState } from 'react'
import { getRealtimeBars } from '../services/api'
import type { KlineIndicator } from '../types'

type PeriodType = 'daily' | 'weekly' | 'monthly'

interface RealtimeBar {
  date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
  amount: number
}

interface RealtimeMessage {
  type: 'init' | 'update'
  data?: RealtimeBar[]
}

function normalizeBar(bar: RealtimeBar): KlineIndicator {
  return {
    date: bar.date,
    open: bar.open,
    high: bar.high,
    low: bar.low,
    close: bar.close,
    volume: bar.volume,
    amount: bar.amount,
  }
}

export function mergeRealtimeBars(current: KlineIndicator[], updates: RealtimeBar[]) {
  const byDate = new Map(current.map((bar) => [bar.date, bar]))
  updates.forEach((bar) =>
    byDate.set(bar.date, { ...byDate.get(bar.date), ...normalizeBar(bar) }),
  )
  return [...byDate.values()].sort((a, b) => a.date.localeCompare(b.date))
}

export function useRealtimeKline(code: string | undefined, period: PeriodType) {
  const [data, setData] = useState<KlineIndicator[]>([])
  const [loading, setLoading] = useState(Boolean(code))
  const [error, setError] = useState<string | null>(null)
  const [connected, setConnected] = useState(false)
  const [fallback, setFallback] = useState(false)
  const socketRef = useRef<WebSocket | null>(null)
  const reconnectRef = useRef<ReturnType<typeof setTimeout>>()
  const retryCountRef = useRef(0)

  useEffect(() => {
    if (!code) {
      setData([])
      setLoading(false)
      return
    }

    let cancelled = false
    const loadFallback = async () => {
      setFallback(true)
      setLoading(true)
      try {
        const response = await getRealtimeBars(code, period)
        if (!cancelled) {
          setData(response.data.map(normalizeBar))
          setError(null)
        }
      } catch {
        if (!cancelled) setError('加载 K 线数据失败')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    const connect = () => {
      if (cancelled) return
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const socket = new WebSocket(
        `${protocol}//${window.location.host}/api/v1/ws/realtime/${code}?period=${period}`,
      )
      socketRef.current = socket
      socket.onopen = () => {
        retryCountRef.current = 0
        setConnected(true)
      }
      socket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data) as RealtimeMessage
          const bars = message.data ?? []
          if (message.type === 'init') {
            setData(bars.map(normalizeBar))
            setLoading(false)
            setError(null)
          } else if (message.type === 'update' && bars.length) {
            setData((current) => mergeRealtimeBars(current, bars))
          }
        } catch {
          setError('实时行情消息格式异常')
        }
      }
      socket.onerror = () => {
        setConnected(false)
        void loadFallback()
      }
      socket.onclose = () => {
        socketRef.current = null
        setConnected(false)
        if (!cancelled) {
          const delay = Math.min(30_000, 2_000 * 2 ** retryCountRef.current)
          retryCountRef.current += 1
          reconnectRef.current = setTimeout(connect, delay)
        }
      }
    }
    setLoading(true)
    setFallback(false)
    setError(null)
    connect()
    return () => {
      cancelled = true
      if (reconnectRef.current) clearTimeout(reconnectRef.current)
      socketRef.current?.close()
      socketRef.current = null
    }
  }, [code, period])

  return { data, loading, error, connected, fallback }
}
