import { useState, type KeyboardEvent } from 'react'
import { Button } from 'antd'
import { SendOutlined, StopOutlined } from '@ant-design/icons'

interface ChatInputProps {
  running: boolean
  disabled?: boolean
  onSend: (content: string) => void
  onStop: () => void
}

export function ChatInput({ running, disabled = false, onSend, onStop }: ChatInputProps) {
  const [value, setValue] = useState('')

  const submit = () => {
    const text = value.trim()
    if (!text || running || disabled) return
    onSend(text)
    setValue('')
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  const rows = Math.min(6, Math.max(1, value.split('\n').length))

  return (
    <div className="chat-input">
      <textarea
        className="chat-input-textarea"
        value={value}
        rows={rows}
        placeholder="输入消息，Enter 发送，Shift+Enter 换行"
        aria-label="聊天输入"
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={running || disabled}
      />
      {running ? (
        <Button
          danger
          icon={<StopOutlined />}
          onClick={onStop}
          aria-label="停止生成"
        >
          停止
        </Button>
      ) : (
        <Button
          type="primary"
          icon={<SendOutlined />}
          disabled={disabled || value.trim().length === 0}
          onClick={submit}
          aria-label="发送消息"
        >
          发送
        </Button>
      )}
    </div>
  )
}
