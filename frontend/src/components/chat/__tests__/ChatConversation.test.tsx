import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ChatConversation } from '../ChatConversation'
import type { ChatMessage } from '../../../types/chat'

function message(overrides: Partial<ChatMessage>): ChatMessage {
  return {
    turnId: 1,
    role: 'assistant',
    content: '',
    reasoning: null,
    tools: [],
    status: 'completed',
    runId: null,
    error: null,
    ...overrides,
  }
}

describe('ChatConversation', () => {
  it('渲染用户右气泡与助手 Markdown（不启用原始 HTML）', () => {
    const messages: ChatMessage[] = [
      message({ turnId: 1, role: 'user', content: '分析 sh.600000' }),
      message({ turnId: 1, content: '结论：**看多** 且 `<script>alert(1)</script>` 不渲染' }),
    ]
    render(
      <ChatConversation messages={messages} running={false} streamState="idle" error={null} />,
    )
    expect(screen.getByText('分析 sh.600000')).toBeInTheDocument()
    expect(screen.getByText('看多').tagName).toBe('STRONG')
    expect(screen.queryByText('alert(1)')).not.toBeInTheDocument()
  })

  it('思考过程可折叠', async () => {
    const user = userEvent.setup()
    const messages: ChatMessage[] = [
      message({ content: '正文', reasoning: '推理内容' }),
    ]
    render(
      <ChatConversation messages={messages} running={false} streamState="idle" error={null} />,
    )
    expect(screen.queryByText('推理内容')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /思考过程/ }))
    expect(screen.getByText('推理内容')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /隐藏思考过程/ }))
    expect(screen.queryByText('推理内容')).not.toBeInTheDocument()
  })

  it('工具行可折叠并展示 run 标签', async () => {
    const user = userEvent.setup()
    const messages: ChatMessage[] = [
      message({
        content: '已完成',
        tools: [
          { tool: 'quant_run_analysis', summary: 'run 创建', runId: 'run-77' },
        ],
      }),
    ]
    render(
      <ChatConversation messages={messages} running={false} streamState="idle" error={null} />,
    )
    expect(screen.getByText('quant_run_analysis')).toBeInTheDocument()
    expect(screen.getByText('run-77')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /折叠工具调用/ }))
    expect(screen.queryByText('quant_run_analysis')).not.toBeInTheDocument()
  })

  it('running 时显示 Deep diving 状态', () => {
    render(
      <ChatConversation messages={[]} running streamState="connecting" error={null} />,
    )
    expect(screen.getByText(/Deep diving/)).toBeInTheDocument()
  })

  it('SSE 已连接但没有运行中 turn 时不显示 Deep diving', () => {
    render(
      <ChatConversation messages={[]} running={false} streamState="active" error={null} />,
    )
    expect(screen.queryByText(/Deep diving/)).not.toBeInTheDocument()
  })

  it('失败消息展示错误', () => {
    const messages: ChatMessage[] = [
      message({ content: '失败', status: 'failed', error: '模型超时' }),
    ]
    render(
      <ChatConversation messages={messages} running={false} streamState="idle" error={null} />,
    )
    expect(screen.getByText('模型超时')).toBeInTheDocument()
  })
})
