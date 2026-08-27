import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Card,
  Alert,
  Select,
  Button,
  Table,
  Tag,
  message,
  Tabs,
  Progress,
  Spin,
  Row,
  Col,
  Modal,
} from 'antd'
import {
  PlayCircleOutlined,
  PauseCircleOutlined,
  HistoryOutlined,
  TrophyOutlined,
  AlertOutlined,
  StockOutlined,
  ThunderboltOutlined,
  EyeOutlined,
  CopyOutlined,
  DownloadOutlined,
} from '@ant-design/icons'
import { LazyECharts } from '../components/charts/LazyECharts'
import type { EChartsOption, TooltipComponentFormatterCallbackParams } from 'echarts'
import {
  submitAnalyzeStock,
  getAnalysisHistory,
  getAnalysisDetail,
  getApiErrorMessage,
} from '../services/agent'
import { cancelJob } from '../services/jobs'
import { getStockIndicators } from '../services/stocks'
import StockSearch from '../components/StockSearch'
import { useJobPolling } from '../hooks/useJobPolling'
import { agentKeys } from '../services/queryKeys'
import { useNavigate } from 'react-router-dom'
import type {
  AgentAnalyzeRequest,
  AnalysisRecord,
  AgentAnalyzeResponse,
  AgentStage,
  KlineIndicator,
} from '../types'
import { logger } from '../utils/logger'
import { DecisionCard } from '../components/analysis/DecisionCard'
import { StageCard } from '../components/analysis/StageCard'
import { NewsSection } from '../components/analysis/NewsSection'
import { buildAgentReportHtml } from '../utils/reportHtml'
import { PageHeader } from '../components/research/ResearchPrimitives'

const { Option } = Select

type AnalysisMode = 'quick' | 'standard' | 'full' | 'strategy'

const modeOptions = [
  { value: 'quick', label: '快速分析', desc: '技术分析 → 决策 (~2次API)' },
  { value: 'standard', label: '标准分析', desc: '技术 → 情报 → 决策' },
  { value: 'full', label: '完整分析', desc: '技术 → 情报 → 风控 → 决策' },
  { value: 'strategy', label: '策略分析', desc: '技术 → 情报 → 风控 → 策略 → 决策' },
]

export default function AgentAnalysis() {
  const [selectedStock, setSelectedStock] = useState<string>('')
  const [stockName, setStockName] = useState<string>('')
  const [mode, setMode] = useState<AnalysisMode>('standard')
  const [analyzing, setAnalyzing] = useState(false)
  const [result, setResult] = useState<AgentAnalyzeResponse | null>(null)
  const [activeTab, setActiveTab] = useState('history')
  const [detailModalVisible, setDetailModalVisible] = useState(false)
  const [selectedDetailId, setSelectedDetailId] = useState<number | null>(null)
  const [jobProgress, setJobProgress] = useState(0)
  const [jobStages, setJobStages] = useState<AgentStage[]>([])
  const [currentJobId, setCurrentJobId] = useState<string | null>(null)
  const [stockIndicators, setStockIndicators] = useState<KlineIndicator[]>([])
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const historyQuery = useQuery({
    queryKey: agentKeys.history(0, 20),
    queryFn: () => getAnalysisHistory(undefined, 0, 20),
    staleTime: 30_000,
  })
  const history = historyQuery.data ?? []
  const detailQuery = useQuery({
    queryKey: agentKeys.detail(selectedDetailId ?? 0),
    queryFn: () => getAnalysisDetail(selectedDetailId as number),
    enabled: selectedDetailId !== null && detailModalVisible,
    staleTime: 5 * 60_000,
  })
  const selectedDetail = detailQuery.data ?? null

  const handleAnalyze = async () => {
    if (!selectedStock) {
      message.warning('请选择股票')
      return
    }

    try {
      setAnalyzing(true)
      setResult(null)
      setJobProgress(0)
      setJobStages([])

      const request: AgentAnalyzeRequest = {
        stock_code: selectedStock,
        stock_name: stockName || selectedStock,
        mode,
      }

      const submission = await submitAnalyzeStock(request)
      setCurrentJobId(submission.job_id)
      const data = await waitForJob(submission.job_id, {
        onStatus: (job) => {
          setJobProgress(Math.round((job.progress || 0) * 100))
          const stages = (job.payload as { stages?: AgentStage[] })?.stages
          if (stages) {
            setJobStages(stages)
          }
        },
      })
      setResult(data)

      if (data.success) {
        message.success('分析完成!')
        // 获取 K 线数据用于图表
        try {
          const endDate = new Date().toISOString().split('T')[0]
          const startDate = new Date(Date.now() - 180 * 24 * 60 * 60 * 1000)
            .toISOString()
            .split('T')[0]
          const indicatorsRes = await getStockIndicators(
            selectedStock,
            'daily',
            startDate,
            endDate,
          )
          setStockIndicators(indicatorsRes.data)
        } catch (err) {
          logger.error('Failed to load stock indicators for chart:', err)
        }
      } else {
        message.error(data.error || '分析失败')
      }

      await queryClient.invalidateQueries({ queryKey: agentKeys.history(0, 20) })
    } catch (error: unknown) {
      const err = error as {
        response?: { data?: { detail?: string } }
        message?: string
      }
      const errMsg = err.response?.data?.detail || err.message || ''
      if (errMsg === 'Cancelled' || errMsg === 'Job cancelled by user') {
        message.info('分析已暂停')
      } else {
        message.error(getApiErrorMessage(error))
      }
    } finally {
      setAnalyzing(false)
      setCurrentJobId(null)
    }
  }

  const handleCancel = async () => {
    if (!currentJobId) return
    try {
      await cancelJob(currentJobId)
      message.info('分析已暂停')
    } catch {
      message.error('暂停失败')
    }
  }

  // 统一任务轮询（默认 10 分钟超时；卸载自动取消）
  const { waitForJob } = useJobPolling<AgentAnalyzeResponse>({ timeoutMs: 600000 })

  const getSignalColor = (signal: string) => {
    switch (signal) {
      case 'buy':
        return 'green'
      case 'sell':
        return 'red'
      default:
        return 'default'
    }
  }

  const getSignalLabel = (signal: string) => {
    switch (signal) {
      case 'buy':
        return '买入'
      case 'sell':
        return '卖出'
      default:
        return '持有'
    }
  }

  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text)
      message.success('已复制到剪贴板')
    } catch {
      message.error('复制失败')
    }
  }

  const getLightChartOption = (data: KlineIndicator[]): EChartsOption => {
    if (!data || data.length === 0) return {}

    const dates = data.map((d) => d.date)
    const ohlc = data.map((d) => [d.open, d.close, d.low, d.high])
    const ma5 = data.map((d) => d.ma5)
    const ma10 = data.map((d) => d.ma10)
    const ma20 = data.map((d) => d.ma20)

    return {
      backgroundColor: 'transparent',
      animation: false,
      legend: {
        top: 10,
        left: 'center',
        textStyle: { color: 'var(--color-text-secondary)', fontSize: 11 },
        data: ['K线', 'MA5', 'MA10', 'MA20'],
      },
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross' },
        backgroundColor: 'var(--color-canvas-lifted)',
        borderColor: 'var(--color-border)',
        textStyle: { color: 'var(--color-text-primary)' },
        formatter: (params: TooltipComponentFormatterCallbackParams) => {
          const list = Array.isArray(params) ? params : [params]
          if (list.length === 0) return ''
          const date = String(
            (list[0] as unknown as { axisValue?: string }).axisValue ?? '',
          )
          const kline = list.find((p) => p.seriesName === 'K线')
          if (!kline) return ''
          const [o, c, l, h] = kline.data as number[]
          const color = c >= o ? '#ff3b30' : '#34c759'
          return `<div style="font-weight:600;margin-bottom:4px">${date}</div>
            <div>开: <b>${o.toFixed(2)}</b> 收: <b style="color:${color}">${c.toFixed(2)}</b></div>
            <div>高: <b>${h.toFixed(2)}</b> 低: <b>${l.toFixed(2)}</b></div>`
        },
      },
      grid: { left: '10%', right: '8%', top: 50, bottom: 60 },
      xAxis: [
        {
          type: 'category',
          data: dates,
          boundaryGap: false,
          axisLine: { onZero: false },
          axisLabel: { color: 'var(--color-text-tertiary)', fontSize: 10 },
        },
      ],
      yAxis: [
        {
          scale: true,
          axisLabel: { color: 'var(--color-text-tertiary)', fontSize: 10 },
        },
      ],
      dataZoom: [
        { type: 'inside', start: 70, end: 100 },
        { show: true, type: 'slider', bottom: 10, start: 70, end: 100, height: 20 },
      ],
      series: [
        {
          name: 'K线',
          type: 'candlestick',
          data: ohlc,
          itemStyle: {
            color: '#ff3b30',
            color0: '#34c759',
            borderColor: '#ff3b30',
            borderColor0: '#34c759',
          },
        },
        {
          name: 'MA5',
          type: 'line',
          data: ma5,
          smooth: true,
          lineStyle: { opacity: 0.5 },
        },
        {
          name: 'MA10',
          type: 'line',
          data: ma10,
          smooth: true,
          lineStyle: { opacity: 0.5 },
        },
        {
          name: 'MA20',
          type: 'line',
          data: ma20,
          smooth: true,
          lineStyle: { opacity: 0.5 },
        },
      ],
    }
  }

  const exportPdf = (r: AgentAnalyzeResponse) => {
    const html = buildAgentReportHtml(r)
    const win = window.open('', '_blank')
    if (!win) {
      message.error('无法打开新窗口，请检查弹窗拦截设置')
      return
    }
    win.document.write(html)
    win.document.close()
    win.focus()
    // 延迟等待渲染完成后触发打印
    setTimeout(() => win.print(), 500)
  }

  const handleViewDetail = (record: AnalysisRecord) => {
    setSelectedDetailId(record.id)
    setDetailModalVisible(true)
  }

  const historyColumns = [
    {
      title: '日期',
      dataIndex: 'analysis_date',
      key: 'date',
      width: 120,
    },
    {
      title: '股票',
      dataIndex: 'stock_code',
      key: 'stock_code',
      width: 100,
      render: (code: string, record: AnalysisRecord) => (
        <span>
          {code} {record.stock_name && `(${record.stock_name})`}
        </span>
      ),
    },
    {
      title: '模式',
      dataIndex: 'mode',
      key: 'mode',
      width: 100,
      render: (mode: string) => <Tag color="blue">{mode}</Tag>,
    },
    {
      title: '信号',
      dataIndex: 'final_signal',
      key: 'signal',
      width: 80,
      render: (signal: string) => (
        <Tag color={getSignalColor(signal)}>{getSignalLabel(signal)}</Tag>
      ),
    },
    {
      title: '置信度',
      dataIndex: 'final_confidence',
      key: 'confidence',
      width: 100,
      render: (confidence: number) => (
        <Progress
          percent={Math.round(confidence * 100)}
          size="small"
          strokeColor="var(--color-ink)"
        />
      ),
    },
    {
      title: '耗时',
      dataIndex: 'duration_s',
      key: 'duration',
      width: 80,
      render: (s: number) => `${s.toFixed(1)}s`,
    },
    {
      title: '操作',
      key: 'action',
      width: 80,
      render: (_: unknown, record: AnalysisRecord) => (
        <Button
          type="link"
          icon={<EyeOutlined />}
          onClick={() => handleViewDetail(record)}
          loading={detailQuery.isFetching}
        >
          查看
        </Button>
      ),
    },
  ]

  const renderAnalysisPanel = () => (
    <div className="fade-in">
      {/* 分析表单 */}
      <Card style={{ marginBottom: 16 }}>
        <Row gutter={16} align="middle">
          <Col flex="auto">
            <StockSearch
              value={selectedStock || undefined}
              onChange={(code, option) => {
                setSelectedStock(code)
                setStockName(option?.label || code)
              }}
            />
          </Col>
          <Col>
            <Select value={mode} onChange={setMode} style={{ width: 160 }}>
              {modeOptions.map((opt) => (
                <Option key={opt.value} value={opt.value}>
                  {opt.label}
                </Option>
              ))}
            </Select>
          </Col>
          <Col>
            {analyzing ? (
              <Button danger icon={<PauseCircleOutlined />} onClick={handleCancel}>
                暂停分析
              </Button>
            ) : (
              <Button
                type="primary"
                icon={<PlayCircleOutlined />}
                onClick={handleAnalyze}
                disabled={!selectedStock}
              >
                开始分析
              </Button>
            )}
          </Col>
        </Row>
        <div
          style={{ marginTop: 12, color: 'var(--color-text-secondary)', fontSize: 13 }}
        >
          {modeOptions.find((m) => m.value === mode)?.desc}
        </div>
      </Card>

      {/* 分析结果 */}
      {result && (
        <div className="fade-in">
          {/* K线图表 - 轻量版 */}
          {stockIndicators.length > 0 && (
            <Card
              style={{ marginBottom: 16 }}
              title={
                <span>
                  {result.stock_name} ({result.stock_code}) 近期走势
                </span>
              }
              extra={
                <a
                  href={`/stocks/${result.stock_code}`}
                  target="_blank"
                  rel="noreferrer"
                  style={{ color: 'var(--color-accent)' }}
                >
                  查看完整图表 →
                </a>
              }
            >
              <LazyECharts
                option={getLightChartOption(stockIndicators)}
                style={{ height: 300 }}
                opts={{ renderer: 'canvas' }}
              />
            </Card>
          )}

          {/* 决策卡片 */}
          <DecisionCard result={result} />
          {/* 复制结论按钮组 */}
          <div
            style={{
              marginTop: 'var(--space-md)',
              display: 'flex',
              gap: 'var(--space-md)',
              justifyContent: 'flex-end',
            }}
          >
            <button
              onClick={() => copyToClipboard(result.final_reason || '')}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 'var(--space-sm)',
                padding: '6px 24px',
                background: '#FFFFFF',
                color: '#141413',
                border: '1.5px solid #141413',
                borderRadius: 'var(--radius-btn)',
                fontSize: 'var(--font-size-md)',
                fontWeight: 450,
                cursor: 'pointer',
                transition: 'transform 0.1s',
              }}
              onMouseDown={(e) => (e.currentTarget.style.transform = 'scale(0.98)')}
              onMouseUp={(e) => (e.currentTarget.style.transform = 'scale(1)')}
              onMouseLeave={(e) => (e.currentTarget.style.transform = 'scale(1)')}
            >
              <CopyOutlined />
              复制结论
            </button>
            <button
              onClick={() => exportPdf(result)}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 'var(--space-sm)',
                padding: '6px 24px',
                background: '#141413',
                color: '#F3F0EE',
                border: '1.5px solid #141413',
                borderRadius: 'var(--radius-btn)',
                fontSize: 'var(--font-size-md)',
                fontWeight: 500,
                letterSpacing: '-0.32px',
                cursor: 'pointer',
                transition: 'transform 0.1s',
              }}
              onMouseDown={(e) => (e.currentTarget.style.transform = 'scale(0.98)')}
              onMouseUp={(e) => (e.currentTarget.style.transform = 'scale(1)')}
              onMouseLeave={(e) => (e.currentTarget.style.transform = 'scale(1)')}
            >
              <DownloadOutlined />
              导出 PDF
            </button>
          </div>

          {/* 各阶段结果 */}
          <Row gutter={[0, 'var(--space-md)']} style={{ marginTop: 'var(--space-md)' }}>
            {result.stages.map((stage, index) => (
              <Col span={24} key={stage.stage_name}>
                <StageCard stage={stage} index={index} />
              </Col>
            ))}
          </Row>

          <NewsSection newsItems={result.news_items} />
        </div>
      )}

      {/* 加载状态 - 进度条 */}
      {analyzing && (
        <Card style={{ padding: 'var(--space-lg)' }}>
          <div style={{ textAlign: 'center', marginBottom: 'var(--space-lg)' }}>
            <div
              style={{
                fontSize: 'var(--font-size-md)',
                fontWeight: 600,
                marginBottom: 'var(--space-sm)',
              }}
            >
              AI Agent 正在分析股票 {selectedStock}...
            </div>
            <div
              style={{
                color: 'var(--color-text-secondary)',
                fontSize: 'var(--font-size-sm)',
                marginBottom: 'var(--space-md)',
              }}
            >
              {modeOptions.find((m) => m.value === mode)?.desc} | 模式: {mode}
            </div>
          </div>

          <Progress
            percent={jobProgress}
            status={jobProgress >= 100 ? 'success' : 'active'}
            style={{ marginBottom: 'var(--space-lg)' }}
          />

          {/* 阶段进度 */}
          <Row gutter={[0, 8]}>
            {jobStages.length > 0
              ? jobStages.map((stage, index) => {
                  const stageNames: Record<string, string> = {
                    technical_analysis: '技术分析',
                    intel: '情报分析',
                    risk: '风险评估',
                    strategy: '策略评估',
                    decision: '决策',
                  }
                  const isRunning = stage.status === 'running'
                  const isCompleted = stage.status === 'completed'
                  const isFailed = stage.status === 'failed'
                  const stagePercent = isCompleted ? 100 : isRunning ? 50 : 0

                  return (
                    <Col span={24} key={stage.stage_name}>
                      <Card
                        size="small"
                        style={{
                          borderLeft: `3px solid ${
                            isCompleted
                              ? 'var(--color-success)'
                              : isRunning
                                ? 'var(--color-ink)'
                                : isFailed
                                  ? 'var(--color-danger)'
                                  : 'var(--color-border)'
                          }`,
                          marginBottom: 'var(--space-sm)',
                          borderRadius: 'var(--radius-btn)',
                        }}
                      >
                        <Row align="middle" gutter={12}>
                          <Col style={{ lineHeight: 1 }}>
                            {index === 0 && <StockOutlined />}
                            {index === 1 && <ThunderboltOutlined />}
                            {index === 2 && <AlertOutlined />}
                            {index === 3 && <TrophyOutlined />}
                          </Col>
                          <Col flex="auto">
                            <div style={{ fontWeight: 500 }}>
                              {stageNames[stage.stage_name] || stage.stage_name}
                            </div>
                          </Col>
                          <Col span={6}>
                            <Progress
                              percent={stagePercent}
                              size="small"
                              status={
                                isFailed
                                  ? 'exception'
                                  : isRunning
                                    ? 'active'
                                    : isCompleted
                                      ? 'success'
                                      : undefined
                              }
                              strokeColor={isFailed ? '#ff4d4f' : undefined}
                            />
                          </Col>
                          <Col>
                            <Tag
                              color={
                                isCompleted
                                  ? 'green'
                                  : isFailed
                                    ? 'red'
                                    : isRunning
                                      ? 'processing'
                                      : 'default'
                              }
                            >
                              {isCompleted
                                ? '完成'
                                : isFailed
                                  ? '失败'
                                  : isRunning
                                    ? '运行中'
                                    : '等待'}
                            </Tag>
                          </Col>
                        </Row>
                        {stage.thinking && stage.thinking.length > 0 && (
                          <div
                            style={{
                              marginTop: 'var(--space-md)',
                              padding: 'var(--space-sm) var(--space-md)',
                              background: 'var(--color-bg-secondary)',
                              borderRadius: 'var(--radius-btn)',
                              fontSize: 'var(--font-size-sm)',
                              lineHeight: 1.8,
                            }}
                          >
                            {stage.thinking.map((t, i) => (
                              <div key={i} style={{ marginBottom: 'var(--space-xs)' }}>
                                {t}
                              </div>
                            ))}
                          </div>
                        )}
                      </Card>
                    </Col>
                  )
                })
              : /* 阶段骨架占位 */
                (() => {
                  const skeletonNames =
                    mode === 'quick'
                      ? ['技术分析', '决策']
                      : mode === 'standard'
                        ? ['技术分析', '情报分析', '决策']
                        : ['技术分析', '情报分析', '风险评估', '决策']
                  return skeletonNames.map((name, i) => (
                    <Col span={24} key={name}>
                      <Card size="small">
                        <Row align="middle" gutter={12}>
                          <Col style={{ lineHeight: 1 }}>
                            {i === 0 && <StockOutlined />}
                            {i === 1 && <ThunderboltOutlined />}
                            {i === 2 && <AlertOutlined />}
                            {i === 3 && <TrophyOutlined />}
                          </Col>
                          <Col flex="auto">
                            <div
                              style={{
                                fontWeight: 500,
                                color: 'var(--color-text-tertiary)',
                              }}
                            >
                              {name}
                            </div>
                          </Col>
                          <Col span={6}>
                            <Progress
                              percent={i === 0 ? 10 : 0}
                              size="small"
                              showInfo={false}
                            />
                          </Col>
                          <Col>
                            <Tag color="default">等待</Tag>
                          </Col>
                        </Row>
                      </Card>
                    </Col>
                  ))
                })()}
          </Row>
        </Card>
      )}
    </div>
  )

  const renderHistoryPanel = () => (
    <div className="fade-in">
      <Card>
        <Table
          columns={historyColumns}
          dataSource={history}
          rowKey="id"
          pagination={{ pageSize: 10 }}
          locale={{ emptyText: '暂无分析历史' }}
        />
      </Card>
    </div>
  )

  const renderDetailModal = () => {
    if (detailQuery.isError) {
      return (
        <Modal
          title="分析详情"
          open={detailModalVisible}
          onCancel={() => setDetailModalVisible(false)}
          footer={null}
          width={800}
        >
          <Alert
            type="error"
            showIcon
            message="获取详情失败"
            action={<Button onClick={() => void detailQuery.refetch()}>重试</Button>}
          />
        </Modal>
      )
    }
    if (!selectedDetail) {
      return detailModalVisible ? (
        <Modal
          title="加载分析详情"
          open
          onCancel={() => setDetailModalVisible(false)}
          footer={null}
          width={800}
        >
          <div className="loading-container" aria-busy="true" aria-live="polite">
            <Spin size="large" />
          </div>
        </Modal>
      ) : null
    }

    return (
      <Modal
        title={`${selectedDetail.stock_code} - ${selectedDetail.stock_name} 分析详情`}
        open={detailModalVisible}
        onCancel={() => setDetailModalVisible(false)}
        footer={null}
        width={800}
      >
        {/* 决策卡片 */}
        <DecisionCard result={selectedDetail} />

        {/* 各阶段结果 */}
        <Row gutter={[0, 'var(--space-md)']} style={{ marginTop: 'var(--space-md)' }}>
          {selectedDetail.stages.map((stage, index) => (
            <Col span={24} key={stage.stage_name}>
              <StageCard stage={stage} index={index} />
            </Col>
          ))}
        </Row>

        <NewsSection newsItems={selectedDetail.news_items} />
      </Modal>
    )
  }

  return (
    <div>
      <PageHeader
        eyebrow="RESEARCH REPORTS"
        title="分析报告"
        subtitle="查看历史研究结论，或在 Agent 工作台开启新的多轮研究"
        actions={
          <Button type="primary" onClick={() => navigate('/workspace')}>
            新建工作台研究
          </Button>
        }
      />

      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          {
            key: 'analyze',
            label: (
              <span>
                <PlayCircleOutlined /> 开始分析
              </span>
            ),
            children: renderAnalysisPanel(),
          },
          {
            key: 'history',
            label: (
              <span>
                <HistoryOutlined /> 分析历史
              </span>
            ),
            children: renderHistoryPanel(),
          },
        ]}
      />

      {renderDetailModal()}
    </div>
  )
}
