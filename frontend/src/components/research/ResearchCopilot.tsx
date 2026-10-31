import { lazy, Suspense, useState } from 'react'
import { Button, Drawer, Empty, Spin } from 'antd'
import { CloseOutlined, RobotOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { ChatInput } from '../chat/ChatInput'
import { useAgentChat } from '../../hooks/useAgentChat'
import type { PageContext } from '../../types/chat'

const ChatConversation = lazy(() =>
  import('../chat/ChatConversation').then((module) => ({
    default: module.ChatConversation,
  })),
)

interface ResearchCopilotProps {
  context?: PageContext
  open?: boolean
  onOpenChange?: (open: boolean) => void
  hideTrigger?: boolean
}

function CopilotContent({
  context,
  onClose,
}: {
  context?: PageContext
  onClose: () => void
}) {
  const navigate = useNavigate()
  const chat = useAgentChat({ context })

  return (
    <div className="research-copilot-body">
      {chat.messages.length === 0 && !chat.running ? (
        <Empty
          image={
            <RobotOutlined
              style={{ fontSize: 32, color: 'var(--color-accent-blue)' }}
            />
          }
          description="问我这只股票的走势、风险或下一步验证方向"
        />
      ) : null}
      <Suspense
        fallback={
          <div
            style={{
              padding: '24px',
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'center',
              minHeight: 120,
            }}
          >
            <Spin size="small" />
          </div>
        }
      >
        <ChatConversation
          messages={chat.messages}
          running={chat.running}
          streamState={chat.streamState}
          error={chat.error}
          hasOlder={chat.hasMoreHistory}
          onLoadOlder={() => void chat.loadOlder()}
        />
      </Suspense>
      <div className="research-copilot-actions">
        <Button
          size="small"
          onClick={() => {
            onClose()
            navigate('/workspace')
          }}
        >
          打开完整工作台
        </Button>
      </div>
      <ChatInput
        running={chat.running}
        disabled={chat.runtimeStatus?.available === false}
        onSend={(content) => void chat.send(content, context)}
        onStop={() => void chat.stop()}
      />
    </div>
  )
}

export function ResearchCopilot({
  context,
  open: controlledOpen,
  onOpenChange,
  hideTrigger = false,
}: ResearchCopilotProps) {
  const [internalOpen, setInternalOpen] = useState(false)
  const open = controlledOpen ?? internalOpen
  const setOpen = (next: boolean) => {
    if (controlledOpen === undefined) setInternalOpen(next)
    onOpenChange?.(next)
  }

  return (
    <>
      {hideTrigger ? null : (
        <button
          type="button"
          className="research-copilot-trigger"
          aria-label="打开 AI 副驾驶"
          onClick={() => setOpen(true)}
        >
          <RobotOutlined />
          <span>AI 副驾驶</span>
        </button>
      )}
      <Drawer
        title={
          <div className="copilot-title">
            <RobotOutlined />
            <span>研究副驾驶</span>
            {context?.entity_id ? <small>{context.entity_id}</small> : null}
          </div>
        }
        placement="right"
        width={420}
        open={open}
        destroyOnHidden
        onClose={() => setOpen(false)}
        extra={
          <Button
            type="text"
            icon={<CloseOutlined />}
            aria-label="关闭副驾驶"
            onClick={() => setOpen(false)}
          />
        }
        className="research-copilot-drawer"
      >
        {open ? (
          <CopilotContent context={context} onClose={() => setOpen(false)} />
        ) : null}
      </Drawer>
    </>
  )
}
