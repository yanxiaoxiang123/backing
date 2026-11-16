import { useEffect, useId, useRef, useState, type KeyboardEvent } from 'react'
import { Button } from 'antd'
import { SendOutlined, StopOutlined } from '@ant-design/icons'

interface ChatInputProps {
  running: boolean
  disabled?: boolean
  onSend: (content: string) => void | boolean | Promise<void | boolean>
  onStop: () => void
  value?: string
  onChange?: (value: string) => void
  submitting?: boolean
  sendDisabled?: boolean
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
  value: controlledValue,
  onChange,
  submitting = false,
  sendDisabled = false,
}: ChatInputProps) {
  const [localValue, setLocalValue] = useState(initialValue)
  const [pending, setPending] = useState(false)
  const pendingRef = useRef(false)
  const controlled = controlledValue !== undefined
  const value = controlledValue ?? localValue
  const setValue = onChange ?? setLocalValue
  const busy = pending || submitting
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const hintId = useId()

  const [submitError, setSubmitError] = useState(false)

  useEffect(() => {
    if (initialValue && !controlled) setLocalValue(initialValue)
  }, [initialValue, controlled])

  useEffect(() => {
    if (!draft) return
    if (!controlled) setLocalValue(draft.value)
    textareaRef.current?.focus()
  }, [draft, controlled])

  const submit = async () => {
    const text = value.trim()
    if (!text || running || disabled || sendDisabled || busy || pendingRef.current)
      return
    pendingRef.current = true
    setPending(true)
    setSubmitError(false)
    try {
      const result = onSend(text)
      const accepted = result && typeof result === 'object' ? await result : result
      // Controlled hosts clear only their acknowledged draft revision.
      if (accepted !== false && controlledValue === undefined)
        setLocalValue((current) => (current.trim() === text ? '' : current))
    } catch {
      setSubmitError(true)
    } finally {
      pendingRef.current = false
      setPending(false)
    }
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.nativeEvent.isComposing) return
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      void submit()
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
        disabled={running || disabled || busy}
      />
      {submitError ? (
        <p role="alert" className="chat-input-hint">
          消息未发送，输入已保留，请重试
        </p>
      ) : null}
      <div className="chat-input-footer">
        <span className="chat-input-hint" id={hintId}>
          {sendDisabled ? (
            '会话尚未加载完成，可继续编辑草稿'
          ) : (
            <>
              <kbd>Enter</kbd> 发送 · <kbd>Shift + Enter</kbd> 换行
            </>
          )}
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
            disabled={disabled || sendDisabled || busy || value.trim().length === 0}
            loading={busy}
            onClick={() => void submit()}
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
