import { useEffect, useId, useRef, useState, type KeyboardEvent } from 'react'
import { Button } from 'antd'
import { SendOutlined, StopOutlined } from '@ant-design/icons'

interface ChatInputProps {
  running: boolean
  disabled?: boolean
  onSend: (content: string) => void
  onStop: () => void
  initialValue?: string
  draft?: { value: string; revision: number }
}

export function ChatInput({
  running,
  disabled = false,
  onSend,
  onStop,
  initialValue = '',
  draft,
}: ChatInputProps) {
  const [value, setValue] = useState(initialValue)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const hintId = useId()

  useEffect(() => {
    if (initialValue) setValue(initialValue)
  }, [initialValue])

  useEffect(() => {
    if (!draft) return
    setValue(draft.value)
    textareaRef.current?.focus()
  }, [draft])

  const submit = () => {
    const text = value.trim()
    if (!text || running || disabled) return
    onSend(text)
    setValue('')
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.nativeEvent.isComposing) return
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  const rows = Math.min(6, Math.max(2, value.split('\n').length))

  return (
    <div className="chat-input">
      <textarea
        ref={textareaRef}
        className="chat-input-textarea"
        value={value}
        rows={rows}
        placeholder="输入股票、策略，或你想验证的研究问题…"
        aria-label="聊天输入"
        aria-describedby={hintId}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={running || disabled}
      />
      <div className="chat-input-footer">
        <span className="chat-input-hint" id={hintId}>
          <kbd>Enter</kbd> 发送 · <kbd>Shift + Enter</kbd> 换行
        </span>
        {running ? (
          <Button
            danger
            icon={<StopOutlined />}
            onClick={onStop}
            aria-label="停止生成"
            title="停止生成"
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
            title="发送消息"
          >
            发送
          </Button>
        )}
      </div>
    </div>
  )
}
