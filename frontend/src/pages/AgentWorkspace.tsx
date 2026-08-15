import { useEffect, useMemo, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { Alert, Descriptions, Empty, Tabs, Tag } from 'antd'
import ReactECharts from 'echarts-for-react'
import { AgentConversation } from '../components/agent/AgentConversation'
import { EvidencePanel } from '../components/agent/EvidencePanel'
import { BacktestPanel } from '../components/agent/BacktestPanel'
import { RiskPanel } from '../components/agent/RiskPanel'
import { ApprovalCard } from '../components/agent/ApprovalCard'
import { ArtifactViewer } from '../components/agent/ArtifactViewer'
import { AttributionPanel } from '../components/agent/AttributionPanel'
import { useAgentRun } from '../hooks/useAgentRun'
import { getStockKline } from '../services/api'
import type { ApprovalRequest } from '../types/agent'
import type { DailyKline } from '../types'
import '../styles/agent.css'

const navItems = [
  { key: '/workspace', label: 'Agent 工作台' },
  { key: '/stocks', label: '行情中心' },
  { key: '/strategies', label: '策略研究' },
  { key: '/backtest', label: '回测执行' },
  { key: '/history', label: '回测历史' },
  { key: '/watchlist', label: '自选股' },
]

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
  const location = useLocation()
  const {
    run,
    events,
    streamState,
    artifacts,
    approvals,
    researchClaims,
    backtestData,
    riskData,
    error,
    start,
    cancel,
    resume,
    decide,
  } = useAgentRun()
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

  const decideApproval = (
    approval: ApprovalRequest,
    decision: 'approved' | 'rejected',
  ) => {
    void decide(approval.id, decision)
  }

  return (
    <div className="agent-workspace">
      <aside className="agent-workspace-nav" aria-label="Agent 工作台导航">
        {navItems.map((item) => (
          <Link
            key={item.key}
            to={item.key}
            className={`agent-workspace-nav-item${
              location.pathname.startsWith(item.key) ? ' active' : ''
            }`}
          >
            {item.label}
          </Link>
        ))}
      </aside>

      <section className="agent-workspace-conversation">
        <AgentConversation
          run={run}
          events={events}
          streamState={streamState}
          error={error}
          onStart={(objective) => void start(objective)}
          onCancel={() => void cancel()}
          onResume={() => void resume()}
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
                      message="在左侧输入研究目标发起分析；K 线/结论数据将随事件流渲染"
                    />
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
          ]}
        />
      </section>
    </div>
  )
}
