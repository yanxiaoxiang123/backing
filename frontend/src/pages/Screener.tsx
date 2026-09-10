import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button, Card, Select, message } from 'antd'
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
import { useJobPolling } from '../hooks/useJobPolling'
import type { JobStatus } from '../types'
import {
  EmptyState,
  JobProgressPanel,
  PageHeader,
  ResearchResultCard,
} from '../components/research/ResearchPrimitives'

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

interface ScreenerResult {
  success: boolean
  total_scanned: number
  results: StockResult[]
}

const STAGE_LABELS: Record<string, string> = {
  scanning: '📊 正在扫描全市场股票...',
  scoring: '🏆 正在综合评分排序...',
  ai_analysis: '🤖 AI 深度分析中',
  completed: '✅ 选股完成',
  initializing: '⏳ 正在初始化...',
}

function Screener() {
  const navigate = useNavigate()
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
  const { waitForJob, cancel } = useJobPolling<ScreenerResult>({
    intervalMs: 2000,
    timeoutMs: 10 * 60 * 1000,
    getStatus: async (id, signal) => {
      const job = await getScreenerStatus(id)
      if (signal.aborted) throw new DOMException('Aborted', 'AbortError')
      return {
        id: job.id,
        job_type: job.job_type ?? 'screener',
        status: job.status as JobStatus<unknown>['status'],
        message: job.payload?.message ?? '',
        progress: job.progress,
        payload: (job.payload ?? {}) as Record<string, unknown>,
        result: job.result as ScreenerResult | undefined,
        error: job.error,
        created_at: job.created_at ?? '',
        updated_at: job.updated_at ?? '',
      }
    },
  })

  const applyCompletedJob = useCallback((job: ScreenerJobRecord, notify = false) => {
    const nextResults = (job.result?.results ?? []) as unknown as StockResult[]
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
  }, [])

  const refreshHistory = useCallback(
    async (restoreLatest = false) => {
      const records = await getScreenerHistory()
      setHistory(records)
      if (restoreLatest) {
        const latestCompleted = records.find(
          (record) => record.status === 'completed' && record.result,
        )
        if (latestCompleted) applyCompletedJob(latestCompleted)
      }
    },
    [applyCompletedJob],
  )

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
      let latestJob: ScreenerJobRecord | null = null
      const result = await waitForJob(res.job_id, {
        onStatus: (status) => {
          const payload = status.payload
          const current = Number(payload.current ?? 0)
          const nextTotal = Number(payload.total ?? 0)
          setStage(String(payload.stage ?? ''))
          setCurrent(current)
          setTotal(nextTotal)
          setMessageText(
            String(
              payload.message ?? STAGE_LABELS[String(payload.stage)] ?? '处理中...',
            ),
          )
          setProgress(
            nextTotal > 0 ? Math.round((current / nextTotal) * 100) : status.progress,
          )
          latestJob = {
            id: status.id,
            job_type: status.job_type,
            status: status.status,
            progress: status.progress,
            payload: {
              stage: String(payload.stage ?? ''),
              current,
              total: nextTotal,
              message: String(payload.message ?? ''),
            },
            result: status.result as unknown as ScreenerJobRecord['result'],
            error: status.error,
          }
        },
      })
      applyCompletedJob(
        latestJob ?? {
          id: res.job_id,
          status: 'completed',
          progress: 100,
          result: { ...result, results: result.results as unknown[] },
        },
        true,
      )
      refreshHistory().catch(() => {})
    } catch (error: unknown) {
      const detail = error as {
        response?: { data?: { detail?: string } }
        message?: string
      }
      message.error(
        detail.response?.data?.detail || detail.message || '提交选股任务失败',
      )
      setRunning(false)
    }
  }

  const handleCancel = async () => {
    cancel()
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

  const renderResultCard = (stock: StockResult) => (
    <ResearchResultCard
      key={stock.stock_code}
      code={stock.stock_code}
      name={stock.stock_name}
      price={stock.close}
      changePercent={stock.change_pct}
      signal={stock.ai_signal}
      confidence={stock.ai_confidence}
      summary={stock.ai_reason || 'AI 分析中...'}
      metadata={
        <>
          <div>
            MA5: {stock.ma5.toFixed(2)} · MA10: {stock.ma10.toFixed(2)} · MA20:{' '}
            {stock.ma20.toFixed(2)}
          </div>
          <div>
            RSI: {stock.rsi.toFixed(1)} · 量比: {stock.volume_ratio.toFixed(2)} · 评分:{' '}
            {stock.composite_score.toFixed(1)}
          </div>
        </>
      }
      actions={
        <div className="research-result-card__actions-group">
          <Button
            type="link"
            size="small"
            onClick={() => navigate(`/stocks/${encodeURIComponent(stock.stock_code)}`)}
          >
            个股研究
          </Button>
          <Button
            type="link"
            size="small"
            onClick={() =>
              navigate(`/workspace?stock=${encodeURIComponent(stock.stock_code)}`)
            }
          >
            Agent
          </Button>
        </div>
      }
    />
  )

  return (
    <div className="fade-in">
      <PageHeader
        eyebrow="DISCOVERY"
        title="AI 量化选股"
        subtitle="基于多维度筛选与 AI 深度分析，发现值得研究的 A 股"
        actions={
          history.some((record) => record.status === 'completed') ? (
            <Select
              aria-label="筛选记录"
              value={selectedHistoryId}
              placeholder="历史筛选"
              suffixIcon={<HistoryOutlined />}
              onChange={handleHistoryChange}
              className="screener-history-select"
              options={history
                .filter((record) => record.status === 'completed' && record.result)
                .map((record) => ({
                  value: record.id,
                  label: `${formatHistoryTime(record.created_at)} · ${record.result?.results.length ?? 0} 只`,
                }))}
            />
          ) : undefined
        }
      />

      {/* 初始状态 */}
      {!running && !completed && (
        <Card className="screener-start-card">
          <Button
            type="primary"
            size="large"
            icon={<PlayCircleOutlined />}
            onClick={handleRun}
            className="screener-start-card__button"
          >
            开始 AI 选股
          </Button>
          <div className="screener-start-card__hint">
            自动扫描全市场股票，综合评分排序后 AI 深度分析 TOP 5
          </div>
        </Card>
      )}

      {/* 进度显示 */}
      {running && (
        <JobProgressPanel
          title={STAGE_LABELS[stage] || '正在处理...'}
          progress={progress}
          message={messageText}
          detail={total > 0 ? `已处理 ${current} / ${total} 只股票` : undefined}
          onCancel={handleCancel}
        />
      )}

      {/* 结果展示 */}
      {completed && !running && (
        <div>
          <Card className="screener-summary-card">
            <div className="screener-summary-card__heading">
              <CheckCircleOutlined />
              <span>{results.length > 0 ? 'AI 精选 TOP 5' : '全市场扫描完成'}</span>
            </div>
            <div className="screener-summary-card__description">
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
              <EmptyState description="当前市场没有股票同时满足均线多头、MACD 红柱和放量条件" />
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
            className="screener-restart-button"
          >
            重新选股
          </Button>
        </div>
      )}
    </div>
  )
}

export default Screener
