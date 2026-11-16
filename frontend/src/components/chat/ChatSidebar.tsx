import { Prose } from '../Prose'
import { Button, Tooltip } from 'antd'
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

function ThreadTitle({ title }: { title: string }) {
  const tail = title.length > 6 ? title.match(/[\p{Script=Han}]{2}[\p{P}]*$/u) : null
  if (!tail) return title
  return (
    <>
      {title.slice(0, -tail[0].length)}
      <span className="chat-nowrap-tail">{tail[0]}</span>
    </>
  )
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
        <Prose as="h2">研究会话</Prose>
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
        type="default"
        block
        icon={<PlusOutlined />}
        onClick={onNew}
        className="chat-sidebar-new"
      >
        新对话
      </Button>
      <div className="chat-sidebar-list-label">最近会话</div>
      <div className="chat-sidebar-list">
        {threads.length === 0 ? (
          <Prose as="p" className="chat-sidebar-empty">
            暂无会话，开始一次新的研究。
          </Prose>
        ) : (
          threads.map((thread) => {
            const active = thread.thread_id === currentThreadId
            const running = thread.status === 'running'
            return (
              <div
                key={thread.thread_id}
                className={`chat-sidebar-item${active ? ' active' : ''}`}
              >
                <button
                  type="button"
                  className="chat-sidebar-select"
                  aria-current={active ? 'page' : undefined}
                  onClick={() => onSelect(thread.thread_id)}
                >
                  <span className="chat-sidebar-item-head">
                    {running ? (
                      <span className="chat-sidebar-dot" aria-label="运行中" />
                    ) : null}
                    <span className="chat-sidebar-title">
                      <ThreadTitle
                        title={
                          thread.title ||
                          (thread.title_pending ? '正在生成标题…' : '新研究会话')
                        }
                      />
                    </span>
                  </span>
                  <time
                    className="chat-sidebar-item-meta"
                    dateTime={thread.updated_at ?? undefined}
                  >
                    {formatTime(thread.updated_at)}
                  </time>
                </button>
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
            )
          })
        )}
      </div>
      <Prose as="p" className="chat-sidebar-note">
        研究记录随会话保存
      </Prose>
    </div>
  )
}
