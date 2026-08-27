import { useEffect, useMemo, useState } from 'react'
import { Alert, Button, Empty, Tabs, Tag } from 'antd'
import { MenuFoldOutlined, MenuUnfoldOutlined } from '@ant-design/icons'
import { LazyECharts } from '../components/charts/LazyECharts'
import { useLocation, useSearchParams } from 'react-router-dom'
import { ChatSidebar } from '../components/chat/ChatSidebar'
import { ChatConversation } from '../components/chat/ChatConversation'
import { ChatInput } from '../components/chat/ChatInput'
import { EvidencePanel } from '../components/agent/EvidencePanel'
import { BacktestPanel } from '../components/agent/BacktestPanel'
import { RiskPanel } from '../components/agent/RiskPanel'
import { ApprovalCard } from '../components/agent/ApprovalCard'
import { ArtifactViewer } from '../components/agent/ArtifactViewer'
import { AttributionPanel } from '../components/agent/AttributionPanel'
import { AlertsPanel } from '../components/agent/AlertsPanel'
import { useAgentRun } from '../hooks/useAgentRun'
import { useAgentChat } from '../hooks/useAgentChat'
import { getStockKline } from '../services/api'
import type { ApprovalRequest } from '../types/agent'
import type { DailyKline } from '../types'
import { extractStockCode } from '../utils/stockIdentity'
import '../styles/agent.css'
import '../styles/chat.css'

const SIDEBAR_COLLAPSED_KEY = 'agent-workspace.sidebar-collapsed'
const RESEARCH_COLLAPSED_KEY = 'agent-workspace.research-collapsed'

function readPanelPreference(key: string): boolean {
  if (typeof window === 'undefined') return false
  try {
    return window.localStorage.getItem(key) === 'true'
  } catch {
    return false
  }
}

function KlineChart({ klines }: { klines: DailyKline[] }) {
  const option = useMemo(() => {
    const dates = klines.map((k) => k.date)
    const candles = klines.map((k) => [k.open, k.close, k.low, k.high])
    const volumes = klines.map((k) => ({
      value: k.volume,
      itemStyle: { color: k.close >= k.open ? '#ef232a' : '#14b143' },
      xAxisIndex: 0,
      yAxisIndex: 0,
    }))
    return {
      tooltip: { trigger: 'axis' },
      axisPointer: { type: 'cross' },
      legend: { data: ['K线', '成交量'] },
      grid: [
        { left: 40, right: 20, top: 30, height: '55%' },
        { left: 40, right: 20, top: '72%', height: '18%' },
      ],
      xAxis: [
        { type: 'category', data: dates, boundaryGap: true },
        { type: 'category', data: dates, gridIndex: 1, axisLabel: { show: false } },
      ],
      yAxis: [
        { scale: true },
        { gridIndex: 1, axisLabel: { show: false }, splitLine: { show: false } },
      ],
      dataZoom: [{ type: 'inside', xAxisIndex: [0, 1], start: 0, end: 100 }],
      series: [
        {
          name: 'K线',
          type: 'candlestick',
          data: candles,
          itemStyle: {
            color: '#ef232a',
            color0: '#14b143',
            borderColor: '#ef232a',
            borderColor0: '#14b143',
          },
        },
        { name: '成交量', type: 'bar', xAxisIndex: 1, yAxisIndex: 1, data: volumes },
      ],
    }
  }, [klines])
  return <LazyECharts option={option} className="agent-kline-chart" />
}

export default function AgentWorkspace() {
  const location = useLocation()
  const [searchParams] = useSearchParams()
  const requestedStock = extractStockCode(searchParams.get('stock'))
  const pageContext = useMemo(
    () => ({
      route: location.pathname,
      entity_type: requestedStock ? 'stock' : 'page',
      entity_id: requestedStock ?? undefined,
    }),
    [location.pathname, requestedStock],
  )
  const {
    run,
    artifacts,
    approvals,
    researchClaims,
    backtestData,
    riskData,
    error: runError,
    attach,
    start,
    decide,
  } = useAgentRun()
  const chat = useAgentChat({
    onRunLinked: (runId) => void attach(runId),
    context: pageContext,
  })
  const [klines, setKlines] = useState<DailyKline[]>([])
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() =>
    readPanelPreference(SIDEBAR_COLLAPSED_KEY),
  )
  const [researchCollapsed, setResearchCollapsed] = useState(() =>
    readPanelPreference(RESEARCH_COLLAPSED_KEY),
  )
  const [researchTab, setResearchTab] = useState('market')

  const stockCode = useMemo(() => {
    return extractStockCode(run?.objective) ?? requestedStock
  }, [requestedStock, run])

  useEffect(() => {
    try {
      window.localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(sidebarCollapsed))
    } catch {
      // 存储不可用时不影响当前会话的布局状态
    }
  }, [sidebarCollapsed])

  useEffect(() => {
    try {
      window.localStorage.setItem(RESEARCH_COLLAPSED_KEY, String(researchCollapsed))
    } catch {
      // 存储不可用时不影响当前会话的布局状态
    }
  }, [researchCollapsed])

  useEffect(() => {
    if (!stockCode) {
      setKlines([])
      return
    }
    let cancelled = false
    void getStockKline(stockCode)
      .then((data) => {
        if (!cancelled) setKlines(data)
      })
      .catch(() => {
        if (!cancelled) setKlines([])
      })
    return () => {
      cancelled = true
    }
  }, [stockCode])

  // 恢复/切换会话时，右栏自动跟随该会话最近一次量化 run
  useEffect(() => {
    const lastRunId = chat.currentThread?.last_run_id
    if (lastRunId) void attach(lastRunId)
  }, [chat.currentThread?.last_run_id, attach])

  const decideApproval = (
    approval: ApprovalRequest,
    decision: 'approved' | 'rejected',
  ) => {
    void decide(approval.id, decision)
  }

  return (
    <div
      className={`agent-workspace${sidebarCollapsed ? ' is-sidebar-collapsed' : ''}${researchCollapsed ? ' is-research-collapsed' : ''}`}
    >
      <aside className="agent-workspace-chat-sidebar" aria-label="会话列表">
        <ChatSidebar
          threads={chat.threads}
          currentThreadId={chat.currentThread?.thread_id ?? null}
          onSelect={(threadId) => void chat.selectThread(threadId)}
          onNew={() => void chat.newThread()}
          onArchive={(threadId) => void chat.archive(threadId)}
          collapsed={sidebarCollapsed}
          onToggleCollapsed={() => setSidebarCollapsed((value) => !value)}
        />
      </aside>

      <section className="agent-workspace-conversation">
        <div className="chat-conversation-header">
          <div className="chat-conversation-heading">
            <span className="chat-conversation-kicker">RESEARCH SESSION</span>
            <strong>{chat.currentThread?.title || '新对话'}</strong>
          </div>
        </div>
        {!chat.runtimeStatus?.available && chat.runtimeStatus ? (
          <Alert
            type="warning"
            showIcon
            message="Agent 聊天暂不可用"
            description="请配置 DEEPSEEK_API_KEY 并安装 backend/requirements.txt 中的依赖。行情与回测功能仍可继续使用。"
            action={
              <Button size="small" onClick={() => void chat.refreshStatus()}>
                重新检测
              </Button>
            }
            className="agent-chat-runtime-alert"
          />
        ) : null}
        <ChatConversation
          messages={chat.messages}
          running={chat.running}
          streamState={chat.streamState}
          error={chat.error}
        />
        <ChatInput
          running={chat.running}
          disabled={Boolean(chat.runtimeStatus && !chat.runtimeStatus.available)}
          initialValue={
            searchParams.get('prompt') ??
            (requestedStock && !chat.currentThread ? `分析一下 ${requestedStock}` : '')
          }
          onSend={(content) => void chat.send(content)}
          onStop={() => void chat.stop()}
        />
      </section>

      <section
        className={`agent-workspace-research${researchCollapsed ? ' is-collapsed' : ''}`}
        aria-label="股票研究区"
      >
        {researchCollapsed ? (
          <div className="agent-research-rail">
            <Button
              type="text"
              icon={<MenuUnfoldOutlined />}
              aria-label="展开研究区"
              title="展开研究区"
              onClick={() => setResearchCollapsed(false)}
            />
            <span>研究</span>
          </div>
        ) : (
          <>
            <div className="agent-research-header">
              <div className="agent-research-heading">
                <span className="agent-research-kicker">RESEARCH</span>
                <strong>研究面板</strong>
              </div>
              <Button
                type="text"
                icon={<MenuFoldOutlined />}
                aria-label="收起研究区"
                title="收起研究区"
                onClick={() => setResearchCollapsed(true)}
              />
            </div>
            <Tabs
              activeKey={researchTab}
              onChange={setResearchTab}
              items={[
                {
                  key: 'market',
                  label: '行情与结论',
                  children: (
                    <div>
                      {run ? (
                        <div className="agent-run-summary">
                          <div className="agent-run-summary-head">
                            <span className="agent-run-kicker">当前研究</span>
                            <Tag
                              color={
                                run.status === 'completed'
                                  ? 'green'
                                  : run.status === 'failed'
                                    ? 'red'
                                    : 'blue'
                              }
                            >
                              {run.status}
                            </Tag>
                          </div>
                          <div className="agent-run-objective">{run.objective}</div>
                          <div className="agent-run-meta-line">
                            <span>run_id</span>
                            <code>{run.run_id}</code>
                            <span>数据快照</span>
                            <code>{run.snapshot_id ?? '—'}</code>
                          </div>
                        </div>
                      ) : (
                        <Alert
                          type="info"
                          showIcon
                          message="在左侧发起新对话；助手调用量化工具产生的 run 将自动展示在右侧"
                        />
                      )}
                      {runError && (
                        <Alert
                          type="error"
                          showIcon
                          message={runError}
                          className="agent-research-error"
                        />
                      )}
                      {klines.length > 0 ? (
                        <KlineChart klines={klines} />
                      ) : (
                        <Empty
                          description="暂无 K 线数据"
                          className="agent-empty-state"
                        />
                      )}
                    </div>
                  ),
                },
                {
                  key: 'evidence',
                  label: '证据',
                  children: <EvidencePanel claims={researchClaims} />,
                },
                {
                  key: 'backtest',
                  label: '回测',
                  children: (
                    <BacktestPanel
                      data={backtestData}
                      objective={run?.objective ?? null}
                      onRerun={(params) => {
                        if (!run?.objective) return
                        void start(run.objective, params)
                      }}
                    />
                  ),
                },
                {
                  key: 'risk',
                  label: '风险',
                  children: (
                    <div>
                      <RiskPanel data={riskData} />
                      {approvals.length === 0 ? (
                        <div className="agent-approval-empty">暂无待审批事项</div>
                      ) : (
                        approvals.map((approval) => (
                          <ApprovalCard
                            key={approval.id}
                            approval={approval}
                            onDecide={decideApproval}
                          />
                        ))
                      )}
                    </div>
                  ),
                },
                {
                  key: 'artifacts',
                  label: '产物',
                  children: (
                    <ArtifactViewer artifacts={artifacts} runId={run?.run_id ?? null} />
                  ),
                },
                {
                  key: 'attribution',
                  label: '归因',
                  children: <AttributionPanel runId={run?.run_id ?? null} />,
                },
                {
                  key: 'alerts',
                  label: '告警',
                  children: <AlertsPanel />,
                },
              ]}
            />
          </>
        )}
      </section>
    </div>
  )
}
