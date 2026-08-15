import { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { Alert, Descriptions, Tabs, Tag } from 'antd'
import { AgentConversation } from '../components/agent/AgentConversation'
import { EvidencePanel } from '../components/agent/EvidencePanel'
import { BacktestPanel } from '../components/agent/BacktestPanel'
import { RiskPanel } from '../components/agent/RiskPanel'
import { ApprovalCard } from '../components/agent/ApprovalCard'
import { ArtifactViewer } from '../components/agent/ArtifactViewer'
import { useAgentRun } from '../hooks/useAgentRun'
import type { ApprovalRequest } from '../types/agent'
import '../styles/agent.css'

const navItems = [
  { key: '/workspace', label: 'Agent 工作台' },
  { key: '/stocks', label: '行情中心' },
  { key: '/strategies', label: '策略研究' },
  { key: '/backtest', label: '回测执行' },
  { key: '/history', label: '回测历史' },
  { key: '/watchlist', label: '自选股' },
]

const DEMO_APPROVAL: ApprovalRequest = {
  id: 'demo-1',
  action: 'execution.paper.order',
  summary: '演示：买入 sh.600519 100 股（模拟盘占位，无真实成交）',
  direction: 'buy',
  target_position_pct: 0.05,
  risk_summary: '演示风险摘要；P3 前不产生成交',
  status: 'pending',
}

export default function AgentWorkspace() {
  const location = useLocation()
  const { run, events, streamState, artifacts, error, start, cancel, resume } =
    useAgentRun()
  const [approvals, setApprovals] = useState<ApprovalRequest[]>([DEMO_APPROVAL])

  const decideApproval = (
    approval: ApprovalRequest,
    decision: 'approved' | 'rejected',
  ) => {
    setApprovals((prev) =>
      prev.map((a) => (a.id === approval.id ? { ...a, status: decision } : a)),
    )
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
                </div>
              ),
            },
            {
              key: 'evidence',
              label: '证据',
              children: <EvidencePanel claims={[]} />,
            },
            {
              key: 'backtest',
              label: '回测',
              children: <BacktestPanel data={null} />,
            },
            {
              key: 'risk',
              label: '风险',
              children: (
                <div>
                  <RiskPanel data={null} />
                  {approvals.map((approval) => (
                    <ApprovalCard
                      key={approval.id}
                      approval={approval}
                      onDecide={decideApproval}
                    />
                  ))}
                </div>
              ),
            },
            {
              key: 'artifacts',
              label: '产物',
              children: <ArtifactViewer artifacts={artifacts} />,
            },
          ]}
        />
      </section>
    </div>
  )
}
