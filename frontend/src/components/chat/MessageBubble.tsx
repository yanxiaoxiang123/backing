// frontend/src/components/chat/MessageBubble.tsx
import type { ChatMessage } from '../../types'

interface Props {
  message: ChatMessage
}

export function MessageBubble({ message }: Props) {
  const isUser = message.role === 'user'
  const time = new Date(message.timestamp).toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit'
  })

  return (
    <div
      style={{
        display: 'flex',
        justifyContent: isUser ? 'flex-end' : 'flex-start',
        marginBottom: 'var(--space-md)'
      }}
    >
      <div
        style={{
          maxWidth: '70%',
          padding: 'var(--space-md)',
          borderRadius: 'var(--radius-btn)',
          background: isUser ? 'var(--color-accent)' : 'var(--color-bg-secondary)',
          color: isUser ? '#fff' : 'var(--color-text-primary)',
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word'
        }}
      >
        {message.content}
        <div
          style={{
            fontSize: 'var(--font-size-xs)',
            color: isUser ? 'rgba(255,255,255,0.7)' : 'var(--color-text-tertiary)',
            marginTop: 'var(--space-xs)',
            textAlign: 'right'
          }}
        >
          {time}
        </div>
      </div>
    </div>
  )
}