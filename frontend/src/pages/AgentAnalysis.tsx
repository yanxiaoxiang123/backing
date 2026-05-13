import { useState, useEffect } from 'react'
import { Card, Select, Button, Table, Tag, Spin, message, Tabs, Progress, Empty, Row, Col, Modal } from 'antd'
import { PlayCircleOutlined, HistoryOutlined, TrophyOutlined, AlertOutlined, StockOutlined, ThunderboltOutlined, EyeOutlined } from '@ant-design/icons'
import { getJobStatus, submitAnalyzeStock, getAnalysisHistory, getAnalysisDetail } from '../services/api'
import StockSearch from '../components/StockSearch'
import type { AgentAnalyzeRequest, AnalysisRecord, AgentAnalyzeResponse, AgentNewsItem } from '../types'
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

      const request: AgentAnalyzeRequest = {
        stock_code: selectedStock,
        stock_name: stockName || selectedStock,
        mode
      }

      const submission = await submitAnalyzeStock(request)
      const data = await waitForJob<AgentAnalyzeResponse>(submission.job_id)
      setResult(data)

      if (data.success) {
        message.success('分析完成!')
      } else {
        message.error(data.error || '分析失败')
      }

      // 刷新历史记录
      loadHistory()
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail || '分析失败，请检查API配置')
    } finally {
      setAnalyzing(false)
    }
  }

  const waitForJob = async <T,>(jobId: string): Promise<T> => {
    while (true) {
      const job = await getJobStatus<T>(jobId)
      if (job.status === 'completed') {
        return job.result as T
      }
      if (job.status === 'failed') {
        throw new Error(job.error || job.message || '任务执行失败')
      }
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
            <Button
              type="primary"
              icon={<PlayCircleOutlined />}
              onClick={handleAnalyze}
              loading={analyzing}
              disabled={!selectedStock}
            >
              {analyzing ? '分析中...' : '开始分析'}
            </Button>
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

      {/* 加载状态 */}
      {analyzing && (
        <Card style={{ textAlign: 'center', padding: 40 }}>
          <Spin size="large" />
          <div style={{ marginTop: 16, color: 'var(--color-text-secondary)' }}>
            AI Agent 正在分析股票 {selectedStock}...
          </div>
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
