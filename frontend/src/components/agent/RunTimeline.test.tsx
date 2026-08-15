import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { RunTimeline, mergeTimelineEvents } from './RunTimeline'
import type { AgentRunEvent } from '../../types/agent'

const events: AgentRunEvent[] = [
  { type: 'step', seq: 1, node: 'supervisor', status: 'completed', duration_s: 0.1 },
  { type: 'tool_call', tool: 'market.kline', status: 'ok', duration_s: 0.2 },
  { type: 'step', seq: 2, node: 'data_qa', status: 'failed', error: '无 K 线数据' },
]

describe('RunTimeline', () => {
  it('渲染节点与工具调用事件', () => {
    render(<RunTimeline events={events} />)
    expect(screen.getByText(/节点 1 · supervisor/)).toBeInTheDocument()
    expect(screen.getByText(/工具调用 · market.kline/)).toBeInTheDocument()
    expect(screen.getByText(/节点 2 · data_qa/)).toBeInTheDocument()
    expect(screen.getByText('失败')).toBeInTheDocument()
  })

  it('空事件显示占位', () => {
    render(<RunTimeline events={[]} />)
    expect(screen.getByText('暂无运行事件')).toBeInTheDocument()
  })

  it('展开可见错误详情', async () => {
    const user = userEvent.setup()
    render(<RunTimeline events={events} />)
    await user.click(screen.getByText(/节点 2 · data_qa/))
    expect(screen.getByText(/无 K 线数据/)).toBeInTheDocument()
  })

  it('同一 seq 的瞬态 running 被 completed 就地替换（不残留"执行中"）', () => {
    const stream: AgentRunEvent[] = [
      { type: 'step', seq: 2, node: 'data_qa', status: 'running' },
      { type: 'step', seq: 2, node: 'data_qa', status: 'completed' },
      { type: 'step', seq: 3, node: 'research', status: 'completed' },
    ]
    const merged = mergeTimelineEvents(stream)
    expect(merged.filter((e) => e.type === 'step' && e.seq === 2)).toHaveLength(1)
    render(<RunTimeline events={stream} />)
    expect(screen.getAllByText(/节点 2 · data_qa/)).toHaveLength(1)
    expect(screen.queryByText('执行中')).not.toBeInTheDocument()
    expect(screen.getAllByText('完成')).toHaveLength(2)
  })
})
