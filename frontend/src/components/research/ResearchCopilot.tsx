import { useState } from 'react'
import { Badge, Button, Drawer, Empty } from 'antd'
import { CloseOutlined, RobotOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { ChatConversation } from '../chat/ChatConversation'
import { ChatInput } from '../chat/ChatInput'
import { useAgentChat } from '../../hooks/useAgentChat'
import type { PageContext } from '../../types/chat'

interface ResearchCopilotProps {
  context?: PageContext
}

export function ResearchCopilot({ context }: ResearchCopilotProps) {
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const chat = useAgentChat({ context })

  return (
    <>
      <button
        type="button"
        className="research-copilot-trigger"
        aria-label="打开 AI 副驾驶"
        onClick={() => setOpen(true)}
      >
        <RobotOutlined />
        <span>AI 副驾驶</span>
        {chat.running ? <Badge status="processing" /> : null}
      </button>
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
          <ChatConversation
            messages={chat.messages}
            running={chat.running}
            streamState={chat.streamState}
            error={chat.error}
          />
          <div className="research-copilot-actions">
            <Button size="small" onClick={() => navigate('/workspace')}>
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
      </Drawer>
    </>
  )
}
