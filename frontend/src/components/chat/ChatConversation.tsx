import { memo, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { Button, Empty, Tag } from 'antd'
import { DownOutlined } from '@ant-design/icons'
import '../../styles/chat.css'
import type { ChatMessage, ToolRow } from '../../types/chat'
import type { ChatStreamState } from '../../services/agentChats'
import { StreamingMarkdown } from './StreamingMarkdown'
import { CopyReplyButton } from './CopyReplyButton'

interface ChatConversationProps {
  messages: ChatMessage[]
  running: boolean
  streamState: ChatStreamState
  error: string | null
  onLoadOlder?: () => void
  hasOlder?: boolean
  emptyState?: ReactNode
}

function ToolRows({ tools }: { tools: ToolRow[] }) {
  const [collapsed, setCollapsed] = useState(true)
  if (tools.length === 0) return null
  return (
    <div className="chat-tools">
      <button
        type="button"
        className="chat-tools-toggle"
        aria-expanded={!collapsed}
        onClick={() => setCollapsed((v) => !v)}
      >
        {collapsed ? '展开' : '折叠'}工具调用（{tools.length}）
      </button>
      {!collapsed && (
        <ul className="chat-tools-list">
          {tools.map((tool, idx) => (
            <li key={`${tool.tool}-${idx}`} className="chat-tool-row">
              <code>{tool.tool}</code>
              {tool.runId && <Tag color="blue">{tool.runId}</Tag>}
              {tool.summary && (
                <span className="chat-tool-summary">{tool.summary}</span>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function ReasoningBlock({ text }: { text: string }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="chat-reasoning">
      <button
        type="button"
        className="chat-reasoning-toggle"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        {open ? '隐藏思考过程' : '思考过程'}
      </button>
      {open && <div className="chat-reasoning-body">{text}</div>}
    </div>
  )
}

const ChatMessageRow = memo(function ChatMessageRow({ msg }: { msg: ChatMessage }) {
  if (msg.role === 'user') {
    return (
      <div className="chat-msg chat-msg-user">
        <div className="chat-bubble">{msg.content}</div>
      </div>
    )
  }
  return (
    <div className="chat-msg chat-msg-assistant">
      <div className="chat-bubble">
        <div className="chat-message-author">研究助手</div>
        {msg.reasoning ? <ReasoningBlock text={msg.reasoning} /> : null}
        {msg.tools.length > 0 ? <ToolRows tools={msg.tools} /> : null}
        <div className="chat-markdown">
          <StreamingMarkdown
            content={msg.content}
            streaming={msg.status === 'queued' || msg.status === 'running'}
          />
        </div>
        <CopyReplyButton content={msg.content} />
        {msg.status === 'failed' || msg.status === 'interrupted' ? (
          <div className="chat-msg-error">{msg.error || `状态：${msg.status}`}</div>
        ) : null}
      </div>
    </div>
  )
})

export function ChatConversation({
  messages,
  running,
  streamState,
  error,
  onLoadOlder,
  hasOlder = false,
  emptyState,
}: ChatConversationProps) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const [pinned, setPinned] = useState(true)
  const [showJump, setShowJump] = useState(false)
  const [showAll, setShowAll] = useState(false)

  const visibleMessages = useMemo(() => {
    if (showAll || messages.length <= 200) return messages
    return messages.slice(-200)
  }, [messages, showAll])

  const handleScroll = () => {
    const el = scrollRef.current
    if (!el) return
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 80
    setPinned(nearBottom)
    setShowJump(!nearBottom)
  }

  useEffect(() => {
    if (!pinned) return
    const el = scrollRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages, running, pinned])

  return (
    <div className="chat-conversation" data-stream-state={streamState}>
      <div className="chat-scroll" ref={scrollRef} onScroll={handleScroll}>
        {messages.length === 0 && !running ? (
          (emptyState ?? (
            <Empty
              description="可以先问候，也可以查询行情，或明确描述股票与策略后发起回测"
              className="chat-conversation-empty"
            />
          ))
        ) : (
          <>
            {hasOlder && onLoadOlder ? (
              <Button
                type="text"
                size="small"
                className="chat-load-older"
                onClick={onLoadOlder}
              >
                加载更早会话
              </Button>
            ) : null}
            {!showAll && messages.length > 200 ? (
              <Button
                type="text"
                size="small"
                className="chat-load-older"
                onClick={() => setShowAll(true)}
              >
                显示更早消息（{messages.length - 200} 条）
              </Button>
            ) : null}
            {visibleMessages.map((msg) => (
              <ChatMessageRow key={`${msg.role}-${msg.turnId}`} msg={msg} />
            ))}
          </>
        )}
        {running ? (
          <div className="chat-deep-diving" aria-live="polite">
            <span className="chat-deep-diving-dots">
              <i />
              <i />
              <i />
            </span>
            Deep diving…
          </div>
        ) : null}
        {error && <div className="chat-stream-error">{error}</div>}
      </div>
      {showJump && (
        <Button
          className="chat-jump-bottom"
          icon={<DownOutlined />}
          aria-label="回到底部"
          title="回到底部"
          onClick={() => {
            setPinned(true)
            const el = scrollRef.current
            if (el) el.scrollTop = el.scrollHeight
          }}
        >
          回到底部
        </Button>
      )}
    </div>
  )
}
