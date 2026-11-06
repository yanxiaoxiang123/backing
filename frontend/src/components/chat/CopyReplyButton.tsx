import { useEffect, useRef, useState } from 'react'
import { CheckOutlined, CopyOutlined } from '@ant-design/icons'

export function CopyReplyButton({ content }: { content: string }) {
  const [status, setStatus] = useState<'idle' | 'copying' | 'copied' | 'failed'>('idle')
  const [revision, setRevision] = useState(0)
  const timer = useRef<ReturnType<typeof window.setTimeout>>()
  const mounted = useRef(true)

  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
      window.clearTimeout(timer.current)
    }
  }, [])

  const copy = async () => {
    window.clearTimeout(timer.current)
    setStatus('copying')
    try {
      await navigator.clipboard.writeText(content)
      if (!mounted.current) return
      setRevision((value) => value + 1)
      setStatus('copied')
    } catch {
      if (!mounted.current) return
      setStatus('failed')
    }
    timer.current = window.setTimeout(() => setStatus('idle'), 2500)
  }

  if (!content.trim()) return null
  return (
    <div className="chat-message-actions">
      <button
        type="button"
        className={`chat-copy-button${status === 'copied' ? ' is-copied' : ''}`}
        onClick={() => void copy()}
        disabled={status === 'copying'}
        aria-label="复制回复"
        title="复制回复"
      >
        <span key={revision} className="chat-copy-icon" aria-hidden="true">
          <CopyOutlined />
        </span>
        <span>复制</span>
        {status === 'copied' ? (
          <span
            key={`check-${revision}`}
            className="chat-copy-check"
            aria-hidden="true"
          >
            <CheckOutlined />
          </span>
        ) : null}
      </button>
      <span className="chat-copy-status" role="status" aria-live="polite">
        {status === 'copied' ? '已复制' : status === 'failed' ? '复制失败，请重试' : ''}
      </span>
    </div>
  )
}
