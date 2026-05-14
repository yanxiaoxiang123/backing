// frontend/src/pages/Chat.tsx
import { useState, useRef, useEffect, useCallback } from 'react'
import { Button } from 'antd'
import { SendOutlined, ClearOutlined } from '@ant-design/icons'
import { MessageBubble } from '../components/chat/MessageBubble'
import { CommandDropdown } from '../components/chat/CommandDropdown'
import { streamChat, streamAgent, COMMAND_LIST } from '../services/chatApi'
import type { ChatMessage } from '../types'

function generateId() {
  return Math.random().toString(36).substring(2, 15)
}

export default function Chat() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [inputValue, setInputValue] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [showCommands, setShowCommands] = useState(false)
  const [commandFilter, setCommandFilter] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  // 初始化欢迎消息
  useEffect(() => {
    if (messages.length === 0) {
      setMessages([{
        id: generateId(),
        role: 'assistant',
        content: '您好！我是 backing AI，您的智能投资研究助手。\n\n我可以帮您：\n• 回答股票相关问题\n• 输入 / 查看可用命令\n\n有什么可以帮您？',
        timestamp: Date.now(),
        type: 'normal'
      }])
    }
  }, [])

  // 滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // 解析斜杠命令
  const parseCommand = (text: string): { command: string; args: string } | null => {
    if (!text.startsWith('/')) return null
    const parts = text.trim().split(/\s+/)
    const cmd = parts[0]
    const args = parts.slice(1).join(' ')
    return { command: cmd, args }
  }

  // 发送消息
  const handleSend = useCallback(async () => {
    const text = inputValue.trim()
    if (!text || isLoading) return

    setShowCommands(false)

    const cmd = parseCommand(text)

    if (cmd) {
      const cmdItem = COMMAND_LIST.find(c => c.command === cmd.command)
      if (cmdItem) {
        await handleCommand(cmd.command, cmd.args)
        return
      }
    }

    await handleNormalChat(text)
  }, [inputValue, isLoading, messages])

  // 处理斜杠命令
  const handleCommand = async (command: string, args: string) => {
    const userMsg: ChatMessage = {
      id: generateId(),
      role: 'user',
      content: `${command} ${args}`.trim(),
      timestamp: Date.now(),
      type: 'command',
      command
    }
    setMessages(prev => [...prev, userMsg])
    setInputValue('')

    const aiMsgId = generateId()
    setMessages(prev => [...prev, {
      id: aiMsgId,
      role: 'assistant',
      content: '',
      timestamp: Date.now(),
      type: 'command',
      command
    }])

    setIsLoading(true)

    try {
      let fullContent = ''

      const endpointMap: Record<string, string> = {
        '/技术': '/chat/agent/technical',
        '/情绪': '/chat/agent/sentiment',
        '/新闻': '/chat/agent/news',
        '/基本面': '/chat/agent/fundamentals',
        '/政策': '/chat/agent/policy',
        '/热钱': '/chat/agent/hotmoney',
        '/解禁': '/chat/agent/lockup'
      }

      const endpoint = endpointMap[command]
      if (endpoint && args) {
        for await (const chunk of streamAgent(endpoint, { stock_code: args })) {
          fullContent += chunk
          setMessages(prev => prev.map(m =>
            m.id === aiMsgId ? { ...m, content: fullContent } : m
          ))
        }
      } else {
        fullContent = '请提供股票代码，例如: ' + command + ' 000001'
        setMessages(prev => prev.map(m =>
          m.id === aiMsgId ? { ...m, content: fullContent } : m
        ))
      }
    } catch (error: unknown) {
      const err = error as { message?: string }
      setMessages(prev => prev.map(m =>
        m.id === aiMsgId ? { ...m, content: `错误: ${err.message || '未知错误'}` } : m
      ))
    } finally {
      setIsLoading(false)
    }
  }

  // 处理普通对话
  const handleNormalChat = async (text: string) => {
    const userMsg: ChatMessage = {
      id: generateId(),
      role: 'user',
      content: text,
      timestamp: Date.now(),
      type: 'normal'
    }
    setMessages(prev => [...prev, userMsg])
    setInputValue('')

    const aiMsgId = generateId()
    setMessages(prev => [...prev, {
      id: aiMsgId,
      role: 'assistant',
      content: '',
      timestamp: Date.now(),
      type: 'normal'
    }])

    setIsLoading(true)

    try {
      let fullContent = ''

      for await (const chunk of streamChat(messages)) {
        fullContent += chunk
        setMessages(prev => prev.map(m =>
          m.id === aiMsgId ? { ...m, content: fullContent } : m
        ))
      }
    } catch (error: unknown) {
      const err = error as { message?: string }
      setMessages(prev => prev.map(m =>
        m.id === aiMsgId ? { ...m, content: `错误: ${err.message || '未知错误'}` } : m
      ))
    } finally {
      setIsLoading(false)
    }
  }

  // 清空对话
  const handleClear = () => {
    setMessages([{
      id: generateId(),
      role: 'assistant',
      content: '对话已清空。有什么可以帮您？',
      timestamp: Date.now(),
      type: 'normal'
    }])
  }

  // 处理输入框变化
  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const value = e.target.value
    setInputValue(value)

    if (value.startsWith('/')) {
      const filter = value.slice(1)
      setCommandFilter(filter)
      setShowCommands(true)
    } else {
      setShowCommands(false)
    }
  }

  // 处理命令选择
  const handleCommandSelect = (command: string) => {
    setInputValue(command + ' ')
    setShowCommands(false)
    inputRef.current?.focus()
  }

  // 键盘提交
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <div style={{
        padding: 'var(--space-md) var(--space-lg)',
        borderBottom: '1px solid var(--color-border)',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center'
      }}>
        <h1 style={{ margin: 0, fontSize: 'var(--font-size-lg)', fontWeight: 600 }}>
          AI 研究助手
        </h1>
        <Button
          icon={<ClearOutlined />}
          onClick={handleClear}
          size="small"
        >
          清空对话
        </Button>
      </div>

      {/* Messages */}
      <div style={{ flex: 1, overflow: 'auto', padding: 'var(--space-lg)' }}>
        {messages.map(msg => (
          <MessageBubble key={msg.id} message={msg} />
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div style={{
        padding: 'var(--space-md) var(--space-lg)',
        borderTop: '1px solid var(--color-border)'
      }}>
        <div style={{ position: 'relative' }}>
          <CommandDropdown
            commands={COMMAND_LIST}
            visible={showCommands}
            filter={commandFilter}
            onSelect={handleCommandSelect}
            onClose={() => setShowCommands(false)}
          />
          <textarea
            ref={inputRef}
            value={inputValue}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            placeholder="输入消息... 输入 / 查看可用命令"
            disabled={isLoading}
            style={{
              width: '100%',
              minHeight: '44px',
              maxHeight: '120px',
              padding: 'var(--space-sm) var(--space-md)',
              paddingRight: '50px',
              borderRadius: 'var(--radius-btn)',
              border: '1px solid var(--color-border)',
              resize: 'none',
              fontFamily: 'inherit',
              fontSize: 'var(--font-size-md)',
              lineHeight: 1.5,
              background: 'var(--color-canvas)'
            }}
            rows={1}
          />
          <Button
            type="primary"
            icon={<SendOutlined />}
            onClick={handleSend}
            disabled={isLoading || !inputValue.trim()}
            style={{
              position: 'absolute',
              right: 'var(--space-sm)',
              bottom: 'var(--space-sm)',
              height: '32px'
            }}
          >
            发送
          </Button>
        </div>
        {isLoading && (
          <div style={{ marginTop: 'var(--space-sm)', color: 'var(--color-text-secondary)', fontSize: 'var(--font-size-sm)' }}>
            AI 正在分析...
          </div>
        )}
      </div>
    </div>
  )
}
