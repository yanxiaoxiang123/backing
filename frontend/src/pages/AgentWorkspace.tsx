import { useEffect, useMemo, useState } from 'react'
import { Alert, Descriptions, Empty, Tabs, Tag } from 'antd'
import ReactECharts from 'echarts-for-react'
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
import '../styles/agent.css'
import '../styles/chat.css'

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
  return <ReactECharts option={option} style={{ height: 320 }} />
}

export default function AgentWorkspace() {
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
  })
  const [klines, setKlines] = useState<DailyKline[]>([])

  const stockCode = useMemo(
    () => run?.objective?.match(/\b(?:sh|sz)\.\d{6}\b/)?.[0] ?? null,
    [run],
  )

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
    <div className="agent-workspace">
      <aside className="agent-workspace-chat-sidebar" aria-label="会话列表">
        <ChatSidebar
          threads={chat.threads}
          currentThreadId={chat.currentThread?.thread_id ?? null}
          onSelect={(threadId) => void chat.selectThread(threadId)}
          onNew={() => void chat.newThread()}
          onArchive={(threadId) => void chat.archive(threadId)}
        />
      </aside>

      <section className="agent-workspace-conversation">
        <div className="chat-conversation-header">
          {chat.currentThread?.title || '新对话'}
        </div>
        <ChatConversation
          messages={chat.messages}
          running={chat.running}
          streamState={chat.streamState}
          error={chat.error}
        />
        <ChatInput
          running={chat.running}
          onSend={(content) => void chat.send(content)}
          onStop={() => void chat.stop()}
        />
      </section>

      <section className="agent-workspace-research" aria-label="股票研究区">
        <Tabs
          defaultActiveKey="market"
          items={[
            {
              key: 'market',
              label: '行情与结论',
              children: (
                <div>
                  {run ? (
                    <Descriptions size="small" column={1} bordered>
                      <Descriptions.Item label="目标">
                        {run.objective}
                      </Descriptions.Item>
                      <Descriptions.Item label="状态">
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
                      </Descriptions.Item>
                      <Descriptions.Item label="run_id">{run.run_id}</Descriptions.Item>
                      <Descriptions.Item label="数据快照">
                        {run.snapshot_id ?? '—'}
                      </Descriptions.Item>
                    </Descriptions>
                  ) : (
                    <Alert
                      type="info"
                      showIcon
                      message="在左侧发起新对话；助手调用量化工具产生的 run 将自动展示在右侧"
                    />
                  )}
                  {runError && (
                    <Alert type="error" showIcon message={runError} style={{ marginTop: 8 }} />
                  )}
                  {klines.length > 0 ? (
                    <KlineChart klines={klines} />
                  ) : (
                    <Empty description="暂无 K 线数据" style={{ marginTop: 16 }} />
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
              children: <AttributionPanel />,
            },
            {
              key: 'alerts',
              label: '告警',
              children: <AlertsPanel />,
            },
          ]}
        />
      </section>
    </div>
  )
}
