import { useCallback, useEffect, useState } from 'react'
import { Card, Button, Progress, Tag, message, Row, Col, Empty, Select } from 'antd'
import {
  PlayCircleOutlined,
  CheckCircleOutlined,
  HistoryOutlined,
  ReloadOutlined,
} from '@ant-design/icons'
import {
  submitScreener,
  getScreenerStatus,
  getScreenerHistory,
  cancelJob,
  type ScreenerJobRecord,
} from '../services/api'

interface StockResult {
  stock_code: string
  stock_name: string
  close: number
  volume: number
  change_pct: number
  ma5: number
  ma10: number
  ma20: number
  macd_dif: number
  macd_dea: number
  macd_hist: number
  rsi: number
  volume_ratio: number
  composite_score: number
  ai_signal?: string
  ai_confidence?: number
  ai_reason?: string
}

const STAGE_LABELS: Record<string, string> = {
  scanning: '📊 正在扫描全市场股票...',
  scoring: '🏆 正在综合评分排序...',
  ai_analysis: '🤖 AI 深度分析中',
  completed: '✅ 选股完成',
  initializing: '⏳ 正在初始化...',
}

function Screener() {
  const [running, setRunning] = useState(false)
  const [stage, setStage] = useState('')
  const [progress, setProgress] = useState(0)
  const [current, setCurrent] = useState(0)
  const [total, setTotal] = useState(0)
  const [messageText, setMessageText] = useState('')
  const [jobId, setJobId] = useState<string | null>(null)
  const [results, setResults] = useState<StockResult[]>([])
  const [totalScanned, setTotalScanned] = useState(0)
  const [completed, setCompleted] = useState(false)
  const [history, setHistory] = useState<ScreenerJobRecord[]>([])
  const [selectedHistoryId, setSelectedHistoryId] = useState<string>()

  const applyCompletedJob = useCallback(
    (job: ScreenerJobRecord, notify = false) => {
      const nextResults = (job.result?.results ?? []) as StockResult[]
      setJobId(job.id)
      setSelectedHistoryId(job.id)
      setStage('completed')
      setProgress(100)
      setResults(nextResults)
      setTotalScanned(job.result?.total_scanned ?? 0)
      setCompleted(true)
      setRunning(false)
      if (notify) {
        if (nextResults.length > 0) {
          message.success(`选股完成，找到 ${nextResults.length} 只股票`)
        } else {
          message.info('扫描完成，本轮没有股票符合筛选条件')
        }
      }
    },
    [],
  )

  const refreshHistory = useCallback(async (restoreLatest = false) => {
    const records = await getScreenerHistory()
    setHistory(records)
    if (restoreLatest) {
      const latestCompleted = records.find(
        (record) => record.status === 'completed' && record.result,
      )
      if (latestCompleted) applyCompletedJob(latestCompleted)
    }
  }, [applyCompletedJob])

  useEffect(() => {
    refreshHistory(true).catch(() => {
      // 历史加载失败不阻塞新的筛选任务。
    })
  }, [refreshHistory])

  const handleRun = async () => {
    try {
      setRunning(true)
      setCompleted(false)
      setSelectedHistoryId(undefined)
      setResults([])
      setTotalScanned(0)
      setProgress(0)
      setStage('initializing')
      setMessageText('正在提交选股任务...')

      const res = await submitScreener()
      setJobId(res.job_id)
      await pollJob(res.job_id)
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '提交选股任务失败')
      setRunning(false)
    }
  }

  const pollJob = async (jobId: string) => {
    const startTime = Date.now()
    const MAX_POLL_MS = 10 * 60 * 1000 // 10 minutes

    while (true) {
      if (Date.now() - startTime > MAX_POLL_MS) {
        message.error('任务超时，请稍后重试')
        setRunning(false)
        break
      }
      try {
        const job = await getScreenerStatus(jobId)

        if (job.status === 'completed') {
          applyCompletedJob(job, true)
          refreshHistory().catch(() => {})
          break
        }

        if (job.status === 'failed') {
          message.error(job.error || '选股任务失败')
          setRunning(false)
          break
        }

        // 更新进度
        const p = job.payload
        if (p) {
          setStage(p.stage)
          setCurrent(p.current || 0)
          setTotal(p.total || 0)
          setMessageText(p.message || STAGE_LABELS[p.stage] || '处理中...')
          const pct = p.total > 0 ? Math.round((p.current / p.total) * 100) : 0
          setProgress(pct)
        }

        await new Promise((r) => setTimeout(r, 2000))
      } catch {
        message.error('查询任务状态失败')
        setRunning(false)
        break
      }
    }
  }

  const handleCancel = async () => {
    if (jobId) {
      try {
        await cancelJob(jobId)
      } catch {
        // ignore cancel errors
      }
    }
    setRunning(false)
  }

  const handleHistoryChange = (historyId: string) => {
    const record = history.find((item) => item.id === historyId)
    if (record?.status === 'completed' && record.result) {
      applyCompletedJob(record)
    }
  }

  const formatHistoryTime = (value?: string) => {
    if (!value) return '未知时间'
    const isoValue = /(?:Z|[+-]\d\d:\d\d)$/.test(value) ? value : `${value}Z`
    return new Intl.DateTimeFormat('zh-CN', {
      timeZone: 'Asia/Shanghai',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    }).format(new Date(isoValue))
  }

  const getSignalColor = (signal?: string) => {
    switch (signal) {
      case 'buy':
        return 'green'
      case 'sell':
        return 'red'
      default:
        return 'default'
    }
  }

  const getSignalLabel = (signal?: string) => {
    switch (signal) {
      case 'buy':
        return '买入'
      case 'sell':
        return '卖出'
      default:
        return '持有'
    }
  }

  const renderResultCard = (stock: StockResult) => {
    const isUp = stock.change_pct >= 0
    const signalColor = getSignalColor(stock.ai_signal)

    return (
      <Card
        key={stock.stock_code}
        style={{
          marginBottom: 12,
          borderLeft: `4px solid ${
            stock.ai_signal === 'buy'
              ? '#52c41a'
              : stock.ai_signal === 'sell'
                ? '#ff4d4f'
                : '#8c8c8c'
          }`,
        }}
      >
        <Row gutter={16} align="middle">
          <Col span={3}>
            <div style={{ fontSize: 18, fontWeight: 700 }}>{stock.stock_code}</div>
            <div style={{ color: 'var(--color-text-secondary)', fontSize: 13 }}>
              {stock.stock_name}
            </div>
          </Col>
          <Col span={3}>
            <div style={{ fontSize: 20, fontWeight: 700 }}>
              {stock.close.toFixed(2)}
            </div>
            <div
              style={{
                color: isUp ? '#EB001B' : '#52C41A',
                fontSize: 13,
              }}
            >
              {isUp ? '+' : ''}
              {stock.change_pct.toFixed(2)}%
            </div>
          </Col>
          <Col span={3}>
            <Tag color={signalColor} style={{ fontSize: 13, padding: '2px 8px' }}>
              {getSignalLabel(stock.ai_signal)}
            </Tag>
            {stock.ai_confidence != null && (
              <div
                style={{
                  marginTop: 4,
                  fontSize: 12,
                  color: 'var(--color-text-secondary)',
                }}
              >
                置信度 {Math.round(stock.ai_confidence * 100)}%
              </div>
            )}
          </Col>
          <Col span={10}>
            <div
              style={{
                fontSize: 13,
                color: 'var(--color-text-secondary)',
                lineHeight: 1.6,
              }}
            >
              {stock.ai_reason || 'AI 分析中...'}
            </div>
          </Col>
          <Col span={5}>
            <div style={{ fontSize: 12, color: 'var(--color-text-tertiary)' }}>
              <div>
                MA5: {stock.ma5.toFixed(2)} MA10: {stock.ma10.toFixed(2)} MA20:{' '}
                {stock.ma20.toFixed(2)}
              </div>
              <div>
                RSI: {stock.rsi.toFixed(1)} | 量比: {stock.volume_ratio.toFixed(2)}
              </div>
              <div>综合评分: {stock.composite_score.toFixed(1)}</div>
            </div>
          </Col>
        </Row>
      </Card>
    )
  }

  return (
    <div className="fade-in">
      <div className="page-header">
        <div className="flex flex-between" style={{ gap: 16, flexWrap: 'wrap' }}>
          <div>
            <h1 className="page-title">AI 量化选股</h1>
            <p className="page-subtitle">
              基于多维度筛选 + AI 深度分析，智能推荐 A 股
            </p>
          </div>
          {history.some((record) => record.status === 'completed') && (
            <Select
              aria-label="筛选记录"
              value={selectedHistoryId}
              placeholder="筛选记录"
              suffixIcon={<HistoryOutlined />}
              onChange={handleHistoryChange}
              style={{ width: 260 }}
              options={history
                .filter((record) => record.status === 'completed' && record.result)
                .map((record) => ({
                  value: record.id,
                  label: `${formatHistoryTime(record.created_at)} · ${record.result?.results.length ?? 0} 只`,
                }))}
            />
          )}
        </div>
      </div>

      {/* 初始状态 */}
      {!running && !completed && (
        <Card style={{ textAlign: 'center', padding: '40px 0' }}>
          <Button
            type="primary"
            size="large"
            icon={<PlayCircleOutlined />}
            onClick={handleRun}
            style={{ borderRadius: 24, padding: '8px 48px', fontSize: 16, height: 48 }}
          >
            开始 AI 选股
          </Button>
          <div
            style={{
              marginTop: 16,
              color: 'var(--color-text-secondary)',
              fontSize: 13,
            }}
          >
            自动扫描全市场股票，综合评分排序后 AI 深度分析 TOP 5
          </div>
        </Card>
      )}

      {/* 进度显示 */}
      {running && (
        <Card style={{ padding: '24px' }}>
          <div style={{ marginBottom: 12, fontSize: 16, fontWeight: 600 }}>
            {STAGE_LABELS[stage] || '正在处理...'}
          </div>
          <Progress percent={progress} status="active" style={{ marginBottom: 8 }} />
          <div
            style={{
              color: 'var(--color-text-secondary)',
              fontSize: 13,
              marginBottom: 4,
            }}
          >
            {messageText}
          </div>
          {total > 0 && (
            <div style={{ color: 'var(--color-text-tertiary)', fontSize: 12 }}>
              已处理 {current} / {total} 只股票
            </div>
          )}
          <div style={{ marginTop: 16 }}>
            <Button onClick={handleCancel}>取消</Button>
          </div>
        </Card>
      )}

      {/* 结果展示 */}
      {completed && !running && (
        <div>
          <Card style={{ marginBottom: 16, background: 'var(--color-canvas-lifted)' }}>
            <div
              style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}
            >
              <CheckCircleOutlined
                style={{ color: 'var(--color-success)', fontSize: 20 }}
              />
              <span style={{ fontSize: 16, fontWeight: 600 }}>
                {results.length > 0 ? 'AI 精选 TOP 5' : '全市场扫描完成'}
              </span>
            </div>
            <div style={{ fontSize: 13, color: 'var(--color-text-secondary)' }}>
              共扫描 {totalScanned} 只有效股票
              {results.length > 0
                ? `，展示 ${results.length} 只深度分析结果`
                : '，本轮没有股票同时满足筛选条件'}
            </div>
          </Card>

          {results.length > 0 ? (
            results.map((stock) => renderResultCard(stock))
          ) : (
            <Card>
              <Empty
                description="当前市场没有股票同时满足均线多头、MACD 红柱和放量条件"
                image={Empty.PRESENTED_IMAGE_SIMPLE}
              />
            </Card>
          )}

          <Button
            type="default"
            icon={<ReloadOutlined />}
            onClick={() => {
              setResults([])
              setCompleted(false)
              setTotalScanned(0)
              setSelectedHistoryId(undefined)
              setRunning(false)
            }}
            style={{ marginTop: 16 }}
          >
            重新选股
          </Button>
        </div>
      )}
    </div>
  )
}

export default Screener
