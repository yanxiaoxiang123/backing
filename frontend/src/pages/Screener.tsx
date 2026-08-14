import { useState } from 'react'
import { Card, Button, Progress, Tag, message, Row, Col } from 'antd'
import {
  PlayCircleOutlined,
  CheckCircleOutlined,
  ReloadOutlined,
} from '@ant-design/icons'
import { submitScreener, getScreenerStatus, cancelJob } from '../services/api'

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

  const handleRun = async () => {
    try {
      setRunning(true)
      setResults([])
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
          setStage('completed')
          setProgress(100)
          if (job.result?.results) {
            setResults(job.result.results)
            setTotalScanned(job.result.total_scanned || 0)
          }
          setRunning(false)
          message.success('选股完成！')
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
        <h1 className="page-title">AI 量化选股</h1>
        <p className="page-subtitle">基于多维度筛选 + AI 深度分析，智能推荐 A 股</p>
      </div>

      {/* 初始状态 */}
      {!running && results.length === 0 && (
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
      {results.length > 0 && (
        <div>
          <Card style={{ marginBottom: 16, background: 'var(--color-canvas-lifted)' }}>
            <div
              style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}
            >
              <CheckCircleOutlined
                style={{ color: 'var(--color-success)', fontSize: 20 }}
              />
              <span style={{ fontSize: 16, fontWeight: 600 }}>AI 精选 TOP 5</span>
            </div>
            <div style={{ fontSize: 13, color: 'var(--color-text-secondary)' }}>
              共扫描 {totalScanned} 只股票，符合条件的 TOP 5 深度分析结果
            </div>
          </Card>

          {results.map((stock) => renderResultCard(stock))}

          <Button
            type="default"
            icon={<ReloadOutlined />}
            onClick={() => {
              setResults([])
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
