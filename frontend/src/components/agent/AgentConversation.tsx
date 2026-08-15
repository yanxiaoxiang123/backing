import { useMemo, useState } from 'react'
import { Button, Input, Space, Tag } from 'antd'
import { SendOutlined, StopOutlined } from '@ant-design/icons'
import { RunTimeline } from './RunTimeline'
import type { AgentRunEvent, RunRecord } from '../../types/agent'
import type { StreamState } from '../../services/agentRuns'

interface AgentConversationProps {
  run: RunRecord | null
  events: AgentRunEvent[]
  streamState: StreamState
  error: string | null
  onStart: (objective: string) => void
  onCancel: () => void
  onResume: () => void
}

const streamText: Record<StreamState, string> = {
  idle: '未开始',
  connecting: '连接中',
  active: '事件流进行中',
  closed: '已结束',
  error: '事件流异常',
}

export function AgentConversation({
  run,
  events,
  streamState,
  error,
  onStart,
  onCancel,
  onResume,
}: AgentConversationProps) {
  const [objective, setObjective] = useState('')
  const running = streamState === 'active' || streamState === 'connecting'
  const canStart = objective.trim().length > 0 && !running

  const summary = useMemo(() => {
    if (!run) return null
    const steps = events.filter((e) => e.type === 'step')
    const completed = steps.filter((e) => e.status === 'completed').length
    return { total: steps.length, completed }
  }, [run, events])

  return (
    <div className="agent-conversation">
      <div className="agent-conversation-input">
        <Input.TextArea
          value={objective}
          onChange={(e) => setObjective(e.target.value)}
          placeholder="输入研究目标，例如：研究 sh.600519 趋势并给出策略建议"
          autoSize={{ minRows: 2, maxRows: 5 }}
          aria-label="研究目标输入"
        />
        <Space style={{ marginTop: 8 }}>
          <Button
            type="primary"
            icon={<SendOutlined />}
            disabled={!canStart}
            onClick={() => {
              onStart(objective)
              setObjective('')
            }}
          >
            发起研究
          </Button>
          {running && (
            <Button danger icon={<StopOutlined />} onClick={onCancel}>
              取消
            </Button>
          )}
          {run?.status === 'failed' && !running && (
            <Button onClick={onResume}>恢复执行</Button>
          )}
        </Space>
      </div>

      {run && (
        <div className="agent-run-meta">
          <Tag color="blue">run_id: {run.run_id}</Tag>
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
          {summary && summary.total > 0 && (
            <span className="agent-run-progress">
              节点进度 {summary.completed}/{summary.total}
            </span>
          )}
          <span className="agent-stream-state">{streamText[streamState]}</span>
        </div>
      )}
      {error && <div className="agent-error-text">{error}</div>}

      <div className="agent-timeline">
        <RunTimeline events={events} />
      </div>
    </div>
  )
}
