import { useState, useEffect } from 'react'
import { Card, Select, Button, Table, Tag, message, Tabs, Progress, Empty, Row, Col, Modal } from 'antd'
import { PlayCircleOutlined, PauseCircleOutlined, HistoryOutlined, TrophyOutlined, AlertOutlined, StockOutlined, ThunderboltOutlined, EyeOutlined, CopyOutlined, DownloadOutlined } from '@ant-design/icons'
import { getJobStatus, submitAnalyzeStock, getAnalysisHistory, getAnalysisDetail, cancelJob } from '../services/api'
import StockSearch from '../components/StockSearch'
import type { AgentAnalyzeRequest, AnalysisRecord, AgentAnalyzeResponse, AgentNewsItem, AgentStage, JobStatus } from '../types'
import { logger } from '../utils/logger'

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
  const [history, setHistory] = useState<AnalysisRecord[]>([])
  const [activeTab, setActiveTab] = useState('analyze')
  const [detailModalVisible, setDetailModalVisible] = useState(false)
  const [selectedDetail, setSelectedDetail] = useState<AgentAnalyzeResponse | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [jobProgress, setJobProgress] = useState(0)
  const [jobStages, setJobStages] = useState<AgentStage[]>([])
  const [currentJobId, setCurrentJobId] = useState<string | null>(null)

  // 加载历史记录
  useEffect(() => {
    loadHistory()
  }, [])

  const loadHistory = async () => {
    try {
      const data = await getAnalysisHistory(undefined, 0, 20)
      setHistory(data)
    } catch (error) {
      logger.error('Failed to load history:', error)
    }
  }

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
        mode
      }

      const submission = await submitAnalyzeStock(request)
      setCurrentJobId(submission.job_id)
      const data = await waitForJob<AgentAnalyzeResponse>(
        submission.job_id,
        (job) => {
          setJobProgress(Math.round((job.progress || 0) * 100))
          const stages = (job.payload as { stages?: AgentStage[] })?.stages
          if (stages) {
            setJobStages(stages)
          }
        },
      )
      setResult(data)

      if (data.success) {
        message.success('分析完成!')
      } else {
        message.error(data.error || '分析失败')
      }

      // 刷新历史记录
      loadHistory()
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } }; message?: string }
      const errMsg = err.response?.data?.detail || err.message || ''
      if (errMsg === 'Cancelled' || errMsg === 'Job cancelled by user') {
        message.info('分析已暂停')
      } else {
        message.error(errMsg || '分析失败，请检查API配置')
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

  const waitForJob = async <T,>(
    jobId: string,
    onProgress?: (job: JobStatus<T>) => void,
  ): Promise<T> => {
    while (true) {
      const job = await getJobStatus<T>(jobId)
      if (job.status === 'completed') {
        return job.result as T
      }
      if (job.status === 'failed') {
        throw new Error(job.error || job.message || '任务执行失败')
      }
      onProgress?.(job)
      await new Promise(resolve => setTimeout(resolve, 1500))
    }
  }

  const getSignalColor = (signal: string) => {
    switch (signal) {
      case 'buy': return 'green'
      case 'sell': return 'red'
      default: return 'default'
    }
  }

  const getSignalLabel = (signal: string) => {
    switch (signal) {
      case 'buy': return '买入'
      case 'sell': return '卖出'
      default: return '持有'
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

  const buildReportHtml = (r: AgentAnalyzeResponse) => {
    const stageLabels: Record<string, string> = {
      technical_analysis: '技术分析',
      intel: '情报分析',
      risk: '风险评估',
      strategy: '策略评估',
      decision: '决策',
    }
    const signalLabel = getSignalLabel(r.final_signal)
    const signalColor = r.final_signal === 'buy' ? '#52c41a' : r.final_signal === 'sell' ? '#ff4d4f' : '#8c8c8c'
    const signalArrow = r.final_signal === 'buy' ? '↑' : r.final_signal === 'sell' ? '↓' : '→'

    const stageRows = r.stages.map((s) => {
      const name = stageLabels[s.stage_name] || s.stage_name
      if (s.opinion) {
        const sc = s.opinion.signal === 'buy' ? '#52c41a' : s.opinion.signal === 'sell' ? '#ff4d4f' : '#8c8c8c'
        const sl = getSignalLabel(s.opinion.signal)
        return `<tr>
          <td style="padding:8px 12px;border:1px solid #e8e8e8;font-weight:600">${name}</td>
          <td style="padding:8px 12px;border:1px solid #e8e8e8"><span style="color:${sc};font-weight:600">${sl}</span></td>
          <td style="padding:8px 12px;border:1px solid #e8e8e8">${Math.round(s.opinion.confidence * 100)}%</td>
          <td style="padding:8px 12px;border:1px solid #e8e8e8">${s.opinion.reason || '—'}</td>
        </tr>`
      }
      return `<tr>
        <td style="padding:8px 12px;border:1px solid #e8e8e8;font-weight:600">${name}</td>
        <td colspan="3" style="padding:8px 12px;border:1px solid #e8e8e8;color:#999">${s.error || '无结果'}</td>
      </tr>`
    }).join('')

    const newsSection = r.news_items?.length
      ? `<h2 style="font-size:16px;margin:24px 0 12px">相关新闻</h2>
         <ul style="padding-left:20px">
           ${r.news_items.map(n => `<li style="margin-bottom:8px"><a href="${n.url}" style="color:#1677ff">${n.title || '新闻'}</a><br/><span style="font-size:13px;color:#666">${n.content ? n.content.slice(0, 200) : ''}</span></li>`).join('')}
         </ul>`
      : ''

    return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>AI Agent 分析报告 - ${r.stock_code}</title>
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 40px; color: #222; line-height: 1.6; }
  h1 { font-size: 22px; margin-bottom: 4px; }
  .subtitle { color: #666; font-size: 14px; margin-bottom: 24px; }
  .signal-card { text-align: center; padding: 24px; background: #f5f5f5; border-radius: 8px; margin-bottom: 24px; }
  .signal-card .arrow { font-size: 48px; font-weight: 700; }
  .signal-card .label { font-size: 20px; font-weight: 600; margin: 8px 0 4px; }
  .signal-card .meta { font-size: 14px; color: #666; }
  .reason-box { background: #fafafa; border: 1px solid #e8e8e8; border-radius: 6px; padding: 12px 16px; margin: 16px 0; font-size: 14px; }
  table { width: 100%; border-collapse: collapse; margin-top: 16px; }
  th { background: #fafafa; padding: 8px 12px; border: 1px solid #e8e8e8; text-align: left; font-weight: 600; font-size: 13px; }
  @media print { body { margin: 20px; } }
</style>
</head>
<body>
  <h1>AI Agent 分析报告</h1>
  <div class="subtitle">${r.stock_name} (${r.stock_code}) | ${r.mode}模式 | ${r.duration_s.toFixed(1)}s</div>

  <div class="signal-card">
    <div class="arrow" style="color:${signalColor}">${signalArrow}</div>
    <div class="label" style="color:${signalColor}">${signalLabel}</div>
    <div class="meta">置信度: ${Math.round(r.final_confidence * 100)}%</div>
  </div>

  <h2 style="font-size:16px;margin-bottom:8px">结论</h2>
  <div class="reason-box">${r.final_reason || '无'}</div>

  <h2 style="font-size:16px;margin:24px 0 12px">各阶段详情</h2>
  <table>
    <thead><tr><th style="width:22%">阶段</th><th style="width:10%">信号</th><th style="width:10%">置信度</th><th>分析理由</th></tr></thead>
    <tbody>${stageRows}</tbody>
  </table>

  ${newsSection}

  <p style="margin-top:32px;font-size:12px;color:#999;text-align:center">由 Backing AI Agent 系统生成</p>
</body>
</html>`
  }

  const exportPdf = (r: AgentAnalyzeResponse) => {
    const html = buildReportHtml(r)
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

  const handleViewDetail = async (record: AnalysisRecord) => {
    try {
      setDetailLoading(true)
      const data = await getAnalysisDetail(record.id)
      setSelectedDetail(data)
      setDetailModalVisible(true)
    } catch (error) {
      message.error('获取详情失败')
    } finally {
      setDetailLoading(false)
    }
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
        <span>{code} {record.stock_name && `(${record.stock_name})`}</span>
      ),
    },
    {
      title: '模式',
      dataIndex: 'mode',
      key: 'mode',
      width: 100,
      render: (mode: string) => (
        <Tag color="blue">{mode}</Tag>
      ),
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
        <Progress percent={Math.round(confidence * 100)} size="small" strokeColor="#0071e3" />
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
          loading={detailLoading}
        >
          查看
        </Button>
      ),
    },
  ]

  const renderNewsSection = (newsItems?: AgentNewsItem[]) => {
    if (!newsItems || newsItems.length === 0) {
      return null
    }

    return (
      <Card style={{ marginTop: 16 }}>
        <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>相关新闻</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {newsItems.map((item, index) => (
            <div
              key={`${item.url}-${index}`}
              style={{
                padding: 12,
                borderRadius: 8,
                background: 'var(--color-bg-secondary)',
                border: '1px solid var(--color-border)'
              }}
            >
              <a
                href={item.url}
                target="_blank"
                rel="noreferrer"
                style={{
                  display: 'block',
                  fontWeight: 600,
                  color: 'var(--color-accent)',
                  marginBottom: 6
                }}
              >
                {item.title || `新闻 ${index + 1}`}
              </a>
              <div style={{ fontSize: 13, color: 'var(--color-text-secondary)', lineHeight: 1.6, marginBottom: 8 }}>
                {item.content || '暂无摘要'}
              </div>
              <div style={{ fontSize: 12, color: 'var(--color-text-tertiary)' }}>
                来源: {item.url}
                {typeof item.score === 'number' ? ` | 相关度: ${item.score.toFixed(2)}` : ''}
              </div>
            </div>
          ))}
        </div>
      </Card>
    )
  }

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
            <Select
              value={mode}
              onChange={setMode}
              style={{ width: 160 }}
            >
              {modeOptions.map(opt => (
                <Option key={opt.value} value={opt.value}>
                  {opt.label}
                </Option>
              ))}
            </Select>
          </Col>
          <Col>
            {analyzing ? (
              <Button
                danger
                icon={<PauseCircleOutlined />}
                onClick={handleCancel}
              >
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
        <div style={{ marginTop: 12, color: 'var(--color-text-secondary)', fontSize: 13 }}>
          {modeOptions.find(m => m.value === mode)?.desc}
        </div>
      </Card>

      {/* 分析结果 */}
      {result && (
        <div className="fade-in">
          {/* 决策卡片 */}
          <Card style={{ marginBottom: 16 }}>
            <Row gutter={16} align="middle">
              <Col>
                <div style={{
                  fontSize: 48,
                  fontWeight: 700,
                  color: result.final_signal === 'buy' ? 'var(--color-success)' :
                         result.final_signal === 'sell' ? 'var(--color-danger)' :
                         'var(--color-text-secondary)'
                }}>
                  {result.final_signal === 'buy' ? '↑' : result.final_signal === 'sell' ? '↓' : '→'}
                </div>
              </Col>
              <Col flex="auto">
                <div style={{ fontSize: 24, fontWeight: 600, marginBottom: 4 }}>
                  {getSignalLabel(result.final_signal)}
                </div>
                <div style={{ color: 'var(--color-text-secondary)' }}>
                  置信度: {Math.round(result.final_confidence * 100)}% | 耗时: {result.duration_s.toFixed(1)}s
                </div>
              </Col>
              <Col>
                <Tag color={getSignalColor(result.final_signal)} style={{ fontSize: 16, padding: '4px 12px' }}>
                  {result.mode}
                </Tag>
              </Col>
            </Row>
            <div style={{ marginTop: 16, display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <Button size="small" icon={<CopyOutlined />} onClick={() => copyToClipboard(result.final_reason || '')}>
                复制结论
              </Button>
              <Button size="small" icon={<DownloadOutlined />} onClick={() => exportPdf(result)}>
                导出 PDF
              </Button>
            </div>
            {result.final_reason && (
              <div style={{ marginTop: 16, padding: 12, background: 'var(--color-bg-secondary)', borderRadius: 8 }}>
                {result.final_reason}
              </div>
            )}
          </Card>

          {/* 各阶段结果 */}
          <Row gutter={16}>
            {result.stages.map((stage, index) => (
              <Col span={24} key={stage.stage_name}>
                <Card
                  size="small"
                  title={
                    <span>
                      {index === 0 && <StockOutlined />}
                      {index === 1 && <ThunderboltOutlined />}
                      {index === 2 && <AlertOutlined />}
                      {index === 3 && <TrophyOutlined />}
                      {' '}{stage.stage_name === 'technical_analysis' ? '技术分析' :
                         stage.stage_name === 'intel' ? '情报分析' :
                         stage.stage_name === 'risk' ? '风险评估' :
                         stage.stage_name === 'strategy' ? '策略评估' : '决策'}
                    </span>
                  }
                  extra={
                    <Tag color={stage.status === 'completed' ? 'green' : stage.status === 'failed' ? 'red' : 'orange'}>
                      {stage.status === 'completed' ? '完成' : stage.status === 'failed' ? '失败' : '进行中'}
                    </Tag>
                  }
                  style={{ marginBottom: 8 }}
                >
                  {stage.opinion ? (
                    <Row gutter={16}>
                      <Col span={4}>
                        <Tag color={getSignalColor(stage.opinion.signal)} style={{ fontSize: 14 }}>
                          {getSignalLabel(stage.opinion.signal)}
                        </Tag>
                        <div style={{ fontSize: 12, color: 'var(--color-text-secondary)', marginTop: 4 }}>
                          置信度: {Math.round(stage.opinion.confidence * 100)}%
                        </div>
                      </Col>
                      <Col span={20}>
                        <div style={{ fontSize: 13 }}>{stage.opinion.reason || '无'}</div>
                      </Col>
                    </Row>
                  ) : stage.error ? (
                    <div style={{ color: 'var(--color-danger)' }}>{stage.error}</div>
                  ) : (
                    <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} />
                  )}
                </Card>
              </Col>
            ))}
          </Row>

          {renderNewsSection(result.news_items)}
        </div>
      )}

      {/* 加载状态 - 进度条 */}
      {analyzing && (
        <Card style={{ padding: 24 }}>
          <div style={{ textAlign: 'center', marginBottom: 20 }}>
            <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 8 }}>
              AI Agent 正在分析股票 {selectedStock}...
            </div>
            <div style={{ color: 'var(--color-text-secondary)', fontSize: 13, marginBottom: 16 }}>
              {modeOptions.find(m => m.value === mode)?.desc} | 模式: {mode}
            </div>
          </div>

          <Progress
            percent={jobProgress}
            status={jobProgress >= 100 ? 'success' : 'active'}
            strokeColor={{
              '0%': '#108ee9',
              '100%': '#87d068',
            }}
            style={{ marginBottom: 24 }}
          />

          {/* 阶段进度 */}
          <Row gutter={[0, 8]}>
            {jobStages.length > 0 ? (
              jobStages.map((stage, index) => {
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
                    <Card size="small" style={{ borderLeft: `3px solid ${
                      isCompleted ? 'var(--color-success)' :
                      isRunning ? 'var(--color-accent)' :
                      isFailed ? 'var(--color-danger)' :
                      'var(--color-border)'
                    }` }}>
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
                            status={isFailed ? 'exception' : isRunning ? 'active' : isCompleted ? 'success' : undefined}
                            strokeColor={isFailed ? '#ff4d4f' : undefined}
                          />
                        </Col>
                        <Col>
                          <Tag color={
                            isCompleted ? 'green' :
                            isFailed ? 'red' :
                            isRunning ? 'processing' : 'default'
                          }>
                            {isCompleted ? '完成' :
                             isFailed ? '失败' :
                             isRunning ? '运行中' : '等待'}
                          </Tag>
                        </Col>
                      </Row>
                      {stage.thinking && stage.thinking.length > 0 && (
                        <div style={{
                          marginTop: 12,
                          padding: '8px 12px',
                          background: 'var(--color-bg-secondary)',
                          borderRadius: 6,
                          fontSize: 13,
                          lineHeight: 1.8
                        }}>
                          {stage.thinking.map((t, i) => (
                            <div key={i} style={{ marginBottom: 4 }}>{t}</div>
                          ))}
                        </div>
                      )}
                    </Card>
                  </Col>
                )
              })
            ) : (
              /* 阶段骨架占位 */
              (() => {
                const skeletonNames = mode === 'quick'
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
                          <div style={{ fontWeight: 500, color: 'var(--color-text-tertiary)' }}>
                            {name}
                          </div>
                        </Col>
                        <Col span={6}>
                          <Progress percent={i === 0 ? 10 : 0} size="small" showInfo={false} />
                        </Col>
                        <Col>
                          <Tag color="default">等待</Tag>
                        </Col>
                      </Row>
                    </Card>
                  </Col>
                ))
              })()
            )}
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
    if (!selectedDetail) return null

    return (
      <Modal
        title={`${selectedDetail.stock_code} - ${selectedDetail.stock_name} 分析详情`}
        open={detailModalVisible}
        onCancel={() => setDetailModalVisible(false)}
        footer={null}
        width={800}
      >
        {/* 决策卡片 */}
        <Card style={{ marginBottom: 16 }}>
          <Row gutter={16} align="middle">
            <Col>
              <div style={{
                fontSize: 48,
                fontWeight: 700,
                color: selectedDetail.final_signal === 'buy' ? 'var(--color-success)' :
                       selectedDetail.final_signal === 'sell' ? 'var(--color-danger)' :
                       'var(--color-text-secondary)'
              }}>
                {selectedDetail.final_signal === 'buy' ? '↑' : selectedDetail.final_signal === 'sell' ? '↓' : '→'}
              </div>
            </Col>
            <Col flex="auto">
              <div style={{ fontSize: 24, fontWeight: 600, marginBottom: 4 }}>
                {getSignalLabel(selectedDetail.final_signal)}
              </div>
              <div style={{ color: 'var(--color-text-secondary)' }}>
                置信度: {Math.round(selectedDetail.final_confidence * 100)}% | 耗时: {selectedDetail.duration_s.toFixed(1)}s
              </div>
            </Col>
            <Col>
              <Tag color={getSignalColor(selectedDetail.final_signal)} style={{ fontSize: 16, padding: '4px 12px' }}>
                {selectedDetail.mode}
              </Tag>
            </Col>
          </Row>
          {selectedDetail.final_reason && (
            <div style={{ marginTop: 16, padding: 12, background: 'var(--color-bg-secondary)', borderRadius: 8 }}>
              {selectedDetail.final_reason}
            </div>
          )}
        </Card>

        {/* 各阶段结果 */}
        <Row gutter={16}>
          {selectedDetail.stages.map((stage: { stage_name: string; status: string; opinion?: { agent_name: string; signal: string; confidence: number; reason: string }; error?: string }, index: number) => (
            <Col span={24} key={stage.stage_name}>
              <Card
                size="small"
                title={
                  <span>
                    {index === 0 && <StockOutlined />}
                    {index === 1 && <ThunderboltOutlined />}
                    {index === 2 && <AlertOutlined />}
                    {index === 3 && <TrophyOutlined />}
                    {' '}{stage.stage_name === 'technical_analysis' ? '技术分析' :
                       stage.stage_name === 'intel' ? '情报分析' :
                       stage.stage_name === 'risk' ? '风险评估' :
                       stage.stage_name === 'strategy' ? '策略评估' : '决策'}
                  </span>
                }
                extra={
                  <Tag color={stage.status === 'completed' ? 'green' : stage.status === 'failed' ? 'red' : 'orange'}>
                    {stage.status === 'completed' ? '完成' : stage.status === 'failed' ? '失败' : '进行中'}
                  </Tag>
                }
                style={{ marginBottom: 8 }}
              >
                {stage.opinion ? (
                  <Row gutter={16}>
                    <Col span={4}>
                      <Tag color={getSignalColor(stage.opinion.signal)} style={{ fontSize: 14 }}>
                        {getSignalLabel(stage.opinion.signal)}
                      </Tag>
                      <div style={{ fontSize: 12, color: 'var(--color-text-secondary)', marginTop: 4 }}>
                        置信度: {Math.round(stage.opinion.confidence * 100)}%
                      </div>
                    </Col>
                    <Col span={20}>
                      <div style={{ fontSize: 13 }}>{stage.opinion.reason || '无'}</div>
                    </Col>
                  </Row>
                ) : stage.error ? (
                  <div style={{ color: 'var(--color-danger)' }}>{stage.error}</div>
                ) : (
                  <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} />
                )}
              </Card>
            </Col>
          ))}
        </Row>

        {renderNewsSection(selectedDetail.news_items)}
      </Modal>
    )
  }

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">AI Agent 分析</h1>
        <p className="page-subtitle">基于 DeepSeek + Tavily 的智能股票分析系统</p>
      </div>

      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          {
            key: 'analyze',
            label: (
              <span><PlayCircleOutlined /> 开始分析</span>
            ),
            children: renderAnalysisPanel(),
          },
          {
            key: 'history',
            label: (
              <span><HistoryOutlined /> 分析历史</span>
            ),
            children: renderHistoryPanel(),
          },
        ]}
      />

      {renderDetailModal()}
    </div>
  )
}
