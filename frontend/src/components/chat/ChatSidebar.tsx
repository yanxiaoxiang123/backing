import { Button, Empty, Tooltip } from 'antd'
import {
  DeleteOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  PlusOutlined,
} from '@ant-design/icons'
import type { ChatThread } from '../../types/chat'

interface ChatSidebarProps {
  threads: ChatThread[]
  currentThreadId: string | null
  onSelect: (threadId: string) => void
  onNew: () => void
  onArchive: (threadId: string) => void
  collapsed?: boolean
  onToggleCollapsed?: () => void
}

function formatTime(value: string | null): string {
  if (!value) return ''
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return ''
  const now = new Date()
  const sameDay = d.toDateString() === now.toDateString()
  return sameDay
    ? d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : d.toLocaleDateString([], { month: '2-digit', day: '2-digit' })
}

export function ChatSidebar({
  threads,
  currentThreadId,
  onSelect,
  onNew,
  onArchive,
  collapsed = false,
  onToggleCollapsed,
}: ChatSidebarProps) {
  if (collapsed) {
    return (
      <div className="chat-sidebar chat-sidebar-collapsed" aria-label="会话列表">
        <Button
          type="text"
          icon={<MenuUnfoldOutlined />}
          className="chat-sidebar-rail-button"
          aria-label="展开会话列表"
          title="展开会话列表"
          onClick={onToggleCollapsed}
        />
        <Button
          type="text"
          icon={<PlusOutlined />}
          className="chat-sidebar-rail-new"
          aria-label="新对话"
          title="新对话"
          onClick={onNew}
        />
      </div>
    )
  }

  return (
    <div className="chat-sidebar" aria-label="会话列表">
      <div className="chat-sidebar-heading">
        <div>
          <span className="chat-sidebar-kicker">CONVERSATIONS</span>
          <strong>会话</strong>
        </div>
        <Button
          type="text"
          icon={<MenuFoldOutlined />}
          aria-label="收起会话列表"
          title="收起会话列表"
          className="chat-sidebar-toggle"
          onClick={onToggleCollapsed}
        />
      </div>
      <Button
        type="primary"
        block
        icon={<PlusOutlined />}
        onClick={onNew}
        className="chat-sidebar-new"
      >
        新对话
      </Button>
      <div className="chat-sidebar-list">
        {threads.length === 0 ? (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="暂无会话"
            className="chat-sidebar-empty"
          />
        ) : (
          threads.map((thread) => {
            const active = thread.thread_id === currentThreadId
            const running = thread.status === 'running'
            return (
              <div
                key={thread.thread_id}
                role="button"
                tabIndex={0}
                className={`chat-sidebar-item${active ? ' active' : ''}`}
                onClick={() => onSelect(thread.thread_id)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') onSelect(thread.thread_id)
                }}
              >
                <div className="chat-sidebar-item-head">
                  {running ? (
                    <span className="chat-sidebar-dot" aria-label="运行中" />
                  ) : null}
                  <span className="chat-sidebar-title">
                    {thread.title || '未命名会话'}
                  </span>
                </div>
                <div className="chat-sidebar-item-meta">
                  <span>{formatTime(thread.updated_at)}</span>
                  <Tooltip title="归档会话">
                    <Button
                      type="text"
                      size="small"
                      icon={<DeleteOutlined />}
                      className="chat-sidebar-archive"
                      aria-label={`归档 ${thread.title || thread.thread_id}`}
                      onClick={(e) => {
                        e.stopPropagation()
                        onArchive(thread.thread_id)
                      }}
                    />
                  </Tooltip>
                </div>
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}
