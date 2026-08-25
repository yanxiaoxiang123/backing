import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Button, Empty, Tag } from 'antd'
import { DownOutlined } from '@ant-design/icons'
import type { ChatMessage, ToolRow } from '../../types/chat'
import type { ChatStreamState } from '../../services/agentChats'

interface ChatConversationProps {
  messages: ChatMessage[]
  running: boolean
  streamState: ChatStreamState
  error: string | null
}

function ToolRows({ tools }: { tools: ToolRow[] }) {
  const [collapsed, setCollapsed] = useState(false)
  if (tools.length === 0) return null
  return (
    <div className="chat-tools">
      <button
        type="button"
        className="chat-tools-toggle"
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
              {tool.summary && <span className="chat-tool-summary">{tool.summary}</span>}
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
        onClick={() => setOpen((v) => !v)}
      >
        {open ? '隐藏思考过程' : '思考过程'}
      </button>
      {open && <div className="chat-reasoning-body">{text}</div>}
    </div>
  )
}

export function ChatConversation({
  messages,
  running,
  streamState,
  error,
}: ChatConversationProps) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const [pinned, setPinned] = useState(true)
  const [showJump, setShowJump] = useState(false)

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
          <Empty
            description="可以先问候，也可以查询行情，或明确描述股票与策略后发起回测"
            style={{ marginTop: 64 }}
          />
        ) : (
          messages.map((msg, idx) =>
            msg.role === 'user' ? (
              <div key={`u-${msg.turnId}-${idx}`} className="chat-msg chat-msg-user">
                <div className="chat-bubble">{msg.content}</div>
              </div>
            ) : (
              <div key={`a-${msg.turnId}-${idx}`} className="chat-msg chat-msg-assistant">
                <div className="chat-bubble">
                  {msg.reasoning ? <ReasoningBlock text={msg.reasoning} /> : null}
                  {msg.tools.length > 0 ? <ToolRows tools={msg.tools} /> : null}
                  <div className="chat-markdown">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {msg.content}
                    </ReactMarkdown>
                  </div>
                  {msg.status === 'failed' || msg.status === 'interrupted' ? (
                    <div className="chat-msg-error">
                      {msg.error || `状态：${msg.status}`}
                    </div>
                  ) : null}
                </div>
              </div>
            )
          )
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
