import { Prose } from '../components/Prose'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Alert, Button, Drawer, Tabs, Tag } from 'antd'
import {
  CloseOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  MessageOutlined,
} from '@ant-design/icons'
import { LazyECharts } from '../components/charts/LazyECharts'
import { useLocation, useSearchParams } from 'react-router-dom'
import { ChatSidebar } from '../components/chat/ChatSidebar'
import { ChatConversation } from '../components/chat/ChatConversation'
import { ChatInput } from '../components/chat/ChatInput'
import { ResearchWelcome } from '../components/chat/ResearchWelcome'
import { EvidencePanel } from '../components/agent/EvidencePanel'
import { BacktestPanel } from '../components/agent/BacktestPanel'
import { RiskAssessmentPanel } from '../components/agent/RiskAssessmentPanel'
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
      animation: false,
      tooltip: { trigger: 'axis' },
      axisPointer: { type: 'cross' },
      grid: [
        { left: 40, right: 20, top: 30, height: '55%' },
        { left: 40, right: 20, top: '72%', height: '18%' },
      ],
      xAxis: [
        { type: 'category', data: dates, boundaryGap: true },
        { type: 'category', data: dates, gridIndex: 1, axisLabel: { show: false } },
      ],
      yAxis: [
        {
          scale: true,
          splitNumber: 4,
          axisLabel: { fontSize: 12 },
          splitLine: { lineStyle: { color: '#eaeaea' } },
        },
        { gridIndex: 1, axisLabel: { show: false }, splitLine: { show: false } },
      ],
      dataZoom: [
        { type: 'inside', xAxisIndex: [0, 1], start: 0, end: 100, throttle: 0 },
      ],
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
    detach,
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
  const [researchMobileOpen, setResearchMobileOpen] = useState(false)
  const [historyMobileOpen, setHistoryMobileOpen] = useState(false)
  const [draft, setDraft] = useState<{ value: string; revision: number }>()
  const [compactResearch, setCompactResearch] = useState(
    () =>
      typeof window !== 'undefined' && window.matchMedia('(max-width: 1279px)').matches,
  )
  const [researchTab, setResearchTab] = useState('market')
  const attachedThreadRef = useRef<string | null>(null)

  // 行情优先跟随当前会话最新确认的股票；没有会话目标时才回退到
  // 研究 run 的目标或页面 URL，避免普通查股后右栏仍停在旧研究标的。
  const runStockCode = useMemo(() => extractStockCode(run?.objective), [run?.objective])
  const stockCode = chat.stockCode ?? runStockCode ?? requestedStock
  const latestBar = klines[klines.length - 1]
  const previousBar = klines[klines.length - 2]
  const priceChange =
    latestBar && previousBar?.close
      ? ((latestBar.close - previousBar.close) / previousBar.close) * 100
      : null

  useEffect(() => {
    const media = window.matchMedia('(max-width: 1279px)')
    const update = () => {
      setCompactResearch(media.matches)
      if (!media.matches) setResearchMobileOpen(false)
    }
    update()
    media.addEventListener('change', update)
    return () => media.removeEventListener('change', update)
  }, [])

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
    // A target switch must never keep showing the previous stock's candles
    // under the new stock's label while the new request is in flight.
    setKlines([])
    if (!stockCode) return
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

  // 恢复/切换会话时，右栏自动跟随该会话最近一次量化 run；没有则清空，
  // 防止上一个会话的 run 与行情串到新会话。
  useEffect(() => {
    const threadId = chat.currentThread?.thread_id ?? null
    if (threadId === attachedThreadRef.current) return
    attachedThreadRef.current = threadId
    if (threadId === null) {
      detach()
      return
    }
    const lastRunId = chat.currentThread?.last_run_id
    if (lastRunId) void attach(lastRunId)
    else detach()
  }, [chat.currentThread?.thread_id, chat.currentThread?.last_run_id, attach, detach])

  const decideApproval = (
    approval: ApprovalRequest,
    decision: 'approved' | 'rejected',
  ) => {
    void decide(approval.id, decision)
  }

  const isResearchCollapsed = researchCollapsed && !compactResearch
  const renderSidebar = (collapsed: boolean, mobile = false) => (
    <ChatSidebar
      threads={chat.threads}
      currentThreadId={chat.currentThread?.thread_id ?? null}
      onSelect={(threadId) => {
        if (threadId !== chat.currentThread?.thread_id) detach()
        setHistoryMobileOpen(false)
        void chat.selectThread(threadId)
      }}
      onNew={() => {
        detach()
        setHistoryMobileOpen(false)
        void chat.newThread()
      }}
      onArchive={(threadId) => void chat.archive(threadId)}
      collapsed={collapsed}
      onToggleCollapsed={() =>
        mobile ? setHistoryMobileOpen(false) : setSidebarCollapsed((value) => !value)
      }
    />
  )
  const researchPanel = (
    <section
      className={`agent-workspace-research${isResearchCollapsed ? ' is-collapsed' : ''}`}
      aria-label="股票研究区"
    >
      {isResearchCollapsed ? (
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
              <Prose as="h2">研究面板</Prose>
            </div>
            <div className="agent-research-header-actions">
              <Button
                type="text"
                className="agent-mobile-research-close"
                icon={<CloseOutlined />}
                aria-label="关闭研究面板"
                onClick={() => setResearchMobileOpen(false)}
              />
              <Button
                type="text"
                icon={<MenuFoldOutlined />}
                aria-label="收起研究区"
                title="收起研究区"
                onClick={() => setResearchCollapsed(true)}
              />
            </div>
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
                          <span>当前研究</span>
                          <Tag
                            color={
                              run.status === 'completed'
                                ? 'green'
                                : run.status === 'failed'
                                  ? 'red'
                                  : 'blue'
                            }
                          >
                            {{
                              completed: '已完成',
                              failed: '未完成',
                              running: '研究中',
                              pending: '待执行',
                              awaiting_approval: '待审批',
                              cancelled: '已取消',
                              planned: '待执行',
                              superseded: '已替代',
                            }[run.status] ?? run.status}
                          </Tag>
                        </div>
                        <div className="agent-run-objective">{run.objective}</div>
                        <details className="agent-run-details">
                          <summary>研究记录</summary>
                          <dl>
                            <div>
                              <dt>研究编号</dt>
                              <dd>{run.run_id}</dd>
                            </div>
                            <div>
                              <dt>数据快照</dt>
                              <dd>{run.snapshot_id ?? '—'}</dd>
                            </div>
                          </dl>
                        </details>
                      </div>
                    ) : (
                      <div className="agent-research-intro" role="status">
                        <strong>
                          {stockCode ? '先看行情，再验证结论' : '等待研究标的'}
                        </strong>
                        <Prose as="p">
                          {stockCode
                            ? '研究证据、回测与风险结果会跟随当前会话。'
                            : '在对话中提到一只股票，让判断有据可查。'}
                        </Prose>
                      </div>
                    )}
                    {runError && (
                      <Alert
                        type="error"
                        showIcon
                        message={runError}
                        className="agent-research-error"
                      />
                    )}
                    {stockCode ? (
                      <div className="agent-market-heading">
                        <div>
                          <Prose as="h3">行情快照</Prose>
                          <span>股票：{stockCode}</span>
                        </div>
                        {runStockCode && runStockCode !== stockCode ? (
                          <span>研究股票：{runStockCode}</span>
                        ) : null}
                      </div>
                    ) : null}
                    {klines.length > 0 ? (
                      <div className="agent-market-data">
                        <div className="agent-market-quote">
                          <strong>{latestBar.close.toFixed(2)}</strong>
                          {priceChange !== null ? (
                            <span
                              className={
                                priceChange > 0
                                  ? 'price-up'
                                  : priceChange < 0
                                    ? 'price-down'
                                    : 'price-flat'
                              }
                            >
                              {priceChange > 0 ? '+' : ''}
                              {priceChange.toFixed(2)}%
                            </span>
                          ) : null}
                          <time>{latestBar.date}</time>
                        </div>
                        <KlineChart klines={klines} />
                        <Prose as="p" className="agent-market-caption">
                          日线 · 成交量
                          {priceChange !== null ? ' · 涨跌幅对比上一条收盘价' : ''}
                        </Prose>
                      </div>
                    ) : stockCode ? (
                      <div className="agent-empty-state">
                        暂无 {stockCode} 的 K 线数据
                      </div>
                    ) : (
                      <div className="agent-research-guide">
                        <div>
                          <span className="agent-guide-mark" />
                          <Prose as="h3">行情快照</Prose>
                          <Prose as="p">价格、成交量与趋势</Prose>
                        </div>
                        <div>
                          <span className="agent-guide-mark" />
                          <Prose as="h3">研究证据</Prose>
                          <Prose as="p">判断来源与可核对的依据</Prose>
                        </div>
                        <div>
                          <span className="agent-guide-mark" />
                          <Prose as="h3">策略验证</Prose>
                          <Prose as="p">回测表现、风险与下一步</Prose>
                        </div>
                        <Prose as="p" className="agent-research-guide-note">
                          结果随会话关联，切换研究时同步更新。
                        </Prose>
                      </div>
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
                    <RiskAssessmentPanel
                      key={`${run?.run_id ?? ''}:${stockCode ?? ''}`}
                      runId={run?.run_id}
                      stockCode={stockCode}
                      data={riskData}
                      onAssessed={() => {
                        if (run) void attach(run.run_id)
                      }}
                    />
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
  )

  return (
    <div
      className={`agent-workspace${sidebarCollapsed ? ' is-sidebar-collapsed' : ''}${isResearchCollapsed ? ' is-research-collapsed' : ''}${researchMobileOpen ? ' is-research-mobile-open' : ''}`}
    >
      <header className="agent-workspace-header">
        <div className="agent-workspace-title">
          <Prose as="h1">Agent 工作台</Prose>
          <span>对话 · 证据 · 策略验证</span>
        </div>
        <div className="agent-workspace-actions">
          <span
            className={`agent-workspace-status${chat.running ? ' is-running' : ''}`}
          >
            <i aria-hidden="true" />
            {chat.running
              ? '正在研究'
              : chat.runtimeStatus?.available === false
                ? '服务暂不可用'
                : chat.runtimeStatus?.available
                  ? '已就绪'
                  : '研究会话'}
          </span>
          <Button
            type="text"
            icon={<MessageOutlined />}
            className="agent-mobile-history-toggle"
            aria-label="打开会话列表"
            onClick={() => setHistoryMobileOpen(true)}
          >
            会话
          </Button>
          <Button
            type="text"
            icon={<MenuUnfoldOutlined />}
            className="agent-mobile-research-toggle"
            aria-label="打开研究面板"
            onClick={() => setResearchMobileOpen(true)}
          >
            研究
          </Button>
        </div>
      </header>
      <aside className="agent-workspace-chat-sidebar" aria-label="会话列表">
        {renderSidebar(sidebarCollapsed)}
      </aside>

      <section className="agent-workspace-conversation">
        <div className="chat-conversation-header">
          <div className="chat-conversation-heading">
            <Prose as="h2">{chat.currentThread?.title || '新研究会话'}</Prose>
            <span>{stockCode ? `研究标的 ${stockCode}` : '行情研究与策略验证'}</span>
          </div>
        </div>
        {!chat.runtimeStatus?.available && chat.runtimeStatus ? (
          <Alert
            type="warning"
            showIcon
            message="Agent 聊天暂不可用"
            description="可以继续查看已有会话与研究结果，或重新检测服务状态。"
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
          hasOlder={chat.hasMoreHistory}
          onLoadOlder={() => void chat.loadOlder()}
          emptyState={
            <ResearchWelcome
              onChoose={(value) =>
                setDraft((previous) => ({
                  value,
                  revision: (previous?.revision ?? 0) + 1,
                }))
              }
            />
          }
        />
        <ChatInput
          running={chat.running}
          draft={draft}
          disabled={Boolean(chat.runtimeStatus && !chat.runtimeStatus.available)}
          initialValue={
            searchParams.get('prompt') ??
            (requestedStock && !chat.currentThread ? `分析一下 ${requestedStock}` : '')
          }
          onSend={(content) => void chat.send(content)}
          onStop={() => void chat.stop()}
        />
      </section>

      {compactResearch ? (
        <Drawer
          aria-label="研究面板"
          open={researchMobileOpen}
          onClose={() => setResearchMobileOpen(false)}
          placement="right"
          width="min(420px, 100vw)"
          closable={false}
          destroyOnHidden
          rootClassName="agent-research-drawer"
          styles={{ body: { padding: 0 } }}
        >
          {researchPanel}
        </Drawer>
      ) : (
        researchPanel
      )}
      <Drawer
        aria-label="研究会话"
        open={historyMobileOpen}
        onClose={() => setHistoryMobileOpen(false)}
        placement="left"
        width="min(320px, calc(100vw - 40px))"
        closable={false}
        destroyOnHidden
        rootClassName="agent-history-drawer"
        styles={{ body: { padding: 0 } }}
      >
        {renderSidebar(false, true)}
      </Drawer>
    </div>
  )
}
