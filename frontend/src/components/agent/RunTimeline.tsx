import { Collapse, Tag, Tooltip } from 'antd'
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  LoadingOutlined,
  ToolOutlined,
} from '@ant-design/icons'
import type { AgentRunEvent } from '../../types/agent'

const statusColor: Record<string, string> = {
  pending: 'default',
  running: 'processing',
  completed: 'success',
  failed: 'error',
  ok: 'success',
  denied: 'warning',
  cancelled: 'default',
}

const statusText: Record<string, string> = {
  pending: '等待',
  running: '执行中',
  completed: '完成',
  failed: '失败',
  ok: '成功',
  denied: '拒绝',
  cancelled: '已取消',
}

function statusIcon(status?: string) {
  if (status === 'running' || status === 'pending') return <LoadingOutlined />
  if (status === 'failed' || status === 'denied') return <CloseCircleOutlined />
  return <CheckCircleOutlined />
}

export function RunTimeline({ events }: { events: AgentRunEvent[] }) {
  if (events.length === 0) {
    return <div className="agent-empty">暂无运行事件</div>
  }
  return (
    <Collapse
      size="small"
      items={events.map((event, index) => ({
        key: String(index),
        label: (
          <span className="agent-timeline-item">
            {event.type === 'step' ? (
              <>
                <span className="agent-timeline-icon">{statusIcon(event.status)}</span>
                <span className="agent-timeline-node">
                  节点 {event.seq} · {event.node}
                </span>
                <Tag color={statusColor[event.status ?? '']}>
                  {statusText[event.status ?? 'pending']}
                </Tag>
                {event.duration_s != null && (
                  <span className="agent-timeline-meta">
                    {event.duration_s.toFixed(2)}s
                  </span>
                )}
              </>
            ) : (
              <>
                <ToolOutlined className="agent-timeline-icon" />
                <span className="agent-timeline-node">工具调用 · {event.tool}</span>
                <Tag color={statusColor[event.status ?? '']}>
                  {statusText[event.status ?? 'ok']}
                </Tag>
                {event.duration_s != null && (
                  <span className="agent-timeline-meta">
                    {event.duration_s.toFixed(2)}s
                  </span>
                )}
              </>
            )}
          </span>
        ),
        children: (
          <div className="agent-timeline-detail">
            {event.type === 'step' ? (
              <>
                <div>输出 schema：{event.output_schema ?? '—'}</div>
                <div>token 用量：{event.tokens_used ?? '—'}</div>
                {event.error && (
                  <div className="agent-error-text">错误：{event.error}</div>
                )}
              </>
            ) : (
              <>
                <div>权限：{event.permission ?? '—'}</div>
                <div>参数 hash：{event.params_hash ?? '—'}</div>
                {event.error && (
                  <div className="agent-error-text">错误：{event.error}</div>
                )}
              </>
            )}
          </div>
        ),
      }))}
    />
  )
}

export function TimelineTooltip({ children }: { children: React.ReactNode }) {
  return <Tooltip title="工具调用 timeline">{children}</Tooltip>
}
