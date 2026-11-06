import { beforeEach, describe, expect, it, vi } from 'vitest'
import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

const mockRun = vi.hoisted(() => ({
  run: null as Record<string, unknown> | null,
  events: [] as unknown[],
  streamState: 'idle',
  artifacts: [] as unknown[],
  approvals: [] as Array<Record<string, unknown>>,
  researchClaims: [] as unknown[],
  backtestData: null as Record<string, unknown> | null,
  riskData: null as Record<string, unknown> | null,
  error: null as string | null,
  start: vi.fn(),
  attach: vi.fn(),
  detach: vi.fn(),
  cancel: vi.fn(),
  resume: vi.fn(),
  decide: vi.fn(),
}))

const mockChat = vi.hoisted(() => ({
  threads: [] as Array<Record<string, unknown>>,
  currentThread: null as Record<string, unknown> | null,
  messages: [] as Array<Record<string, unknown>>,
  stockCode: null as string | null,
  streamState: 'idle',
  running: false,
  error: null as string | null,
  selectThread: vi.fn(),
  newThread: vi.fn(),
  send: vi.fn(),
  stop: vi.fn(),
  archive: vi.fn(),
}))

vi.mock('../../hooks/useAgentRun', () => ({
  useAgentRun: () => ({
    run: mockRun.run,
    events: mockRun.events,
    streamState: mockRun.streamState,
    artifacts: mockRun.artifacts,
    approvals: mockRun.approvals,
    researchClaims: mockRun.researchClaims,
    backtestData: mockRun.backtestData,
    riskData: mockRun.riskData,
    error: mockRun.error,
    start: mockRun.start,
    attach: mockRun.attach,
    detach: mockRun.detach,
    cancel: mockRun.cancel,
    resume: mockRun.resume,
    decide: mockRun.decide,
  }),
}))

vi.mock('../../hooks/useAgentChat', () => ({
  useAgentChat: () => ({
    threads: mockChat.threads,
    currentThread: mockChat.currentThread,
    messages: mockChat.messages,
    stockCode: mockChat.stockCode,
    streamState: mockChat.streamState,
    running: mockChat.running,
    error: mockChat.error,
    selectThread: mockChat.selectThread,
    newThread: mockChat.newThread,
    send: mockChat.send,
    stop: mockChat.stop,
    archive: mockChat.archive,
  }),
}))

vi.mock('../../services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../services/api')>()
  return { ...actual, getStockKline: vi.fn().mockResolvedValue([]) }
})

import AgentWorkspace from '../AgentWorkspace'
import { getStockKline } from '../../services/api'

vi.mock('../../components/charts/LazyECharts', () => ({
  LazyECharts: ({ option }: { option: { xAxis: Array<{ data: string[] }> } }) => (
    <div data-testid="workspace-candles">{option.xAxis[0].data.join(',')}</div>
  ),
}))

function renderWorkspace(path = '/workspace') {
  return render(
    <MemoryRouter
      initialEntries={[path]}
      future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
    >
      <AgentWorkspace />
    </MemoryRouter>,
  )
}

beforeEach(() => {
  localStorage.clear()
  mockRun.run = null
  mockRun.events = []
  mockRun.researchClaims = []
  mockRun.backtestData = null
  mockRun.riskData = null
  mockRun.error = null
  mockRun.approvals = []
  mockRun.start.mockClear()
  mockRun.attach.mockClear()
  mockRun.detach.mockClear()
  vi.mocked(getStockKline).mockReset().mockResolvedValue([])
  mockRun.decide.mockClear()
  mockChat.threads = []
  mockChat.currentThread = null
  mockChat.messages = []
  mockChat.stockCode = null
  mockChat.running = false
  mockChat.error = null
  mockChat.selectThread.mockClear()
  mockChat.newThread.mockClear()
  mockChat.send.mockClear()
  mockChat.stop.mockClear()
  mockChat.archive.mockClear()
})

describe('AgentWorkspace', () => {
  it('渲染三栏布局：会话列表 / 聊天 / 研究区', () => {
    renderWorkspace()
    expect(
      screen.getByRole('heading', { level: 1, name: 'Agent 工作台' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('complementary', { name: /会话列表/ })).toBeInTheDocument()
    expect(screen.getByLabelText('聊天输入')).toBeInTheDocument()
    expect(screen.getByRole('region', { name: /股票研究区/ })).toBeInTheDocument()
    expect(screen.getByText('等待研究标的').closest('[role="status"]')).not.toBeNull()
  })

  it('桌面侧栏可以折叠并恢复', async () => {
    const user = userEvent.setup()
    renderWorkspace()

    await user.click(screen.getByRole('button', { name: '收起会话列表' }))
    expect(screen.getByRole('button', { name: '展开会话列表' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '收起研究区' }))
    expect(screen.getByRole('button', { name: '展开研究区' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '展开会话列表' }))
    await user.click(screen.getByRole('button', { name: '展开研究区' }))
    expect(screen.getByRole('button', { name: '收起会话列表' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '收起研究区' })).toBeInTheDocument()
  })

  it('发送消息调用 chat.send', async () => {
    const user = userEvent.setup()
    renderWorkspace()
    await user.type(screen.getByLabelText('聊天输入'), '分析 sh.600000')
    await user.click(screen.getByRole('button', { name: /发送/ }))
    expect(mockChat.send).toHaveBeenCalledWith('分析 sh.600000')
  })

  it('研究示例填入草稿并聚焦，等待用户确认后才发送', async () => {
    const user = userEvent.setup()
    renderWorkspace()
    await user.click(screen.getByRole('button', { name: /验证一个策略/ }))
    const input = screen.getByLabelText('聊天输入')
    expect((input as HTMLTextAreaElement).value).toContain('5 日与 20 日均线交叉策略')
    expect(input).toHaveFocus()
    expect(mockChat.send).not.toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: '发送消息' }))
    expect(mockChat.send).toHaveBeenCalledWith(expect.stringContaining('交易成本'))
    await user.click(screen.getByRole('button', { name: /验证一个策略/ }))
    expect((input as HTMLTextAreaElement).value).toContain('5 日与 20 日均线交叉策略')
  })

  it('研究区页签可切换且不跳页', async () => {
    const user = userEvent.setup()
    renderWorkspace()
    expect(screen.getByText('等待研究标的')).toBeInTheDocument()

    await user.click(screen.getByRole('tab', { name: /证据/ }))
    expect(screen.getByText('暂无证据条目')).toBeInTheDocument()

    await user.click(screen.getByRole('tab', { name: /回测/ }))
    expect(screen.getByText('尚无回测结果')).toBeInTheDocument()

    await user.click(screen.getByRole('tab', { name: /风险/ }))
    expect(screen.getByText('暂无待审批事项')).toBeInTheDocument()
  })

  it('run 完成后研究面板展示结构化数据（证据/回测/风险）', async () => {
    const user = userEvent.setup()
    mockRun.run = {
      run_id: 'run-1',
      objective: '生成策略并回测验证 sh.600000',
      status: 'completed',
      steps: [],
    }
    mockRun.researchClaims = [
      {
        claim: 'K线收盘上穿MA5',
        category: 'technical',
        direction: 'bullish',
        confidence: 0.6,
        evidence: [],
        hypothesis: false,
      },
    ]
    mockRun.backtestData = {
      strategy_name: 'ma_cross_demo',
      total_return: 0.0143,
      annual_return: 0.0143,
      max_drawdown_pct: -0.9955,
      sharpe_out_of_sample: 0,
      passed: false,
      reasons: ['收益非正或回撤过大'],
    }
    mockRun.riskData = {
      positions: [{ code: 'sh.600000', action: 'buy', weight: 0.1, confidence: 0.5 }],
      constraints: [{ rule: 'lot_size', passed: true, detail: '整手' }],
      rejected: false,
    }
    renderWorkspace()

    await user.click(screen.getByRole('tab', { name: /证据/ }))
    expect(screen.getByText('K线收盘上穿MA5')).toBeInTheDocument()

    await user.click(screen.getByRole('tab', { name: /回测/ }))
    expect(screen.getByText('回测审计拒绝')).toBeInTheDocument()
    expect(screen.getAllByText('收益非正或回撤过大').length).toBeGreaterThanOrEqual(1)

    await user.click(screen.getByRole('tab', { name: /风险/ }))
    expect(screen.getByText('sh.600000')).toBeInTheDocument()
    expect(screen.getByText('整手')).toBeInTheDocument()
  })

  it('研究 run 未包含回测时给出补充策略提示', async () => {
    const user = userEvent.setup()
    mockRun.run = {
      run_id: 'run-research-only',
      objective: '分析 sz.000001',
      status: 'completed',
      steps: [],
    }
    mockRun.backtestData = null
    renderWorkspace()

    await user.click(screen.getByRole('tab', { name: /回测/ }))
    expect(
      screen.getByText('本次研究未执行回测；请在对话中指定策略和回测目标'),
    ).toBeInTheDocument()
  })

  it('审批卡批准调用 decide（真实审批 API 由 hook 封装）', async () => {
    const user = userEvent.setup()
    mockRun.approvals = [
      {
        id: 1,
        action: 'paper.order',
        summary: '买入 100 股 sh.600000',
        direction: 'buy',
        status: 'pending',
      },
    ]
    renderWorkspace()
    await user.click(screen.getByRole('tab', { name: /风险/ }))
    await user.click(screen.getByRole('button', { name: /批准（仅模拟盘）/ }))
    expect(mockRun.decide).toHaveBeenCalledWith(1, 'approved')
  })

  it('参数修改 → 新 run：提交编辑后的策略参数（US-2.8）', async () => {
    const user = userEvent.setup()
    mockRun.run = {
      run_id: 'run-1',
      objective: '生成策略并回测验证 sh.600000',
      status: 'completed',
      steps: [],
    }
    mockRun.backtestData = {
      strategy_name: 'ma_cross_demo',
      total_return: 0.0143,
      annual_return: 0.0143,
      max_drawdown_pct: -0.9955,
      sharpe_out_of_sample: 0,
      passed: false,
      reasons: ['收益非正或回撤过大'],
    }
    renderWorkspace()
    await user.click(screen.getByRole('tab', { name: /回测/ }))
    const inputs = screen.getAllByRole('spinbutton')
    await user.clear(inputs[1])
    await user.type(inputs[1], '30')
    await user.click(screen.getByRole('button', { name: /参数修改 → 新 run/ }))
    expect(mockRun.start).toHaveBeenCalledWith('生成策略并回测验证 sh.600000', {
      short_period: 5,
      long_period: 30,
    })
  })

  it('confirmed chat stock drives candles while older research keeps its identity', () => {
    mockChat.currentThread = { thread_id: 't-1', last_run_id: 'run-1' }
    mockChat.stockCode = 'sz.000001'
    mockRun.run = {
      run_id: 'run-1',
      objective: '分析 sh.600000',
      status: 'completed',
      steps: [],
    }
    renderWorkspace()
    expect(getStockKline).toHaveBeenLastCalledWith('sz.000001')
    expect(screen.getByText('股票：sz.000001')).toBeInTheDocument()
    expect(screen.getByText('研究股票：sh.600000')).toBeInTheDocument()
  })

  it('URL suffix stock remains a fallback before selecting a thread', () => {
    renderWorkspace('/workspace?stock=000001.sz')
    expect(getStockKline).toHaveBeenCalledWith('sz.000001')
  })

  it('new thread detaches current research immediately', async () => {
    const user = userEvent.setup()
    mockChat.currentThread = { thread_id: 't-1', last_run_id: 'run-1' }
    renderWorkspace()
    mockRun.detach.mockClear()
    await user.click(screen.getByRole('button', { name: /新对话/ }))
    expect(mockRun.detach).toHaveBeenCalledTimes(1)
    expect(mockChat.newThread).toHaveBeenCalledTimes(1)
  })

  it('clears loaded candles immediately when the target changes', async () => {
    let resolveNew!: (value: Awaited<ReturnType<typeof getStockKline>>) => void
    const row = (date: string) => ({
      date,
      open: 1,
      close: 2,
      low: 1,
      high: 2,
      volume: 100,
    })
    vi.mocked(getStockKline)
      .mockResolvedValueOnce([row('old-date')] as Awaited<
        ReturnType<typeof getStockKline>
      >)
      .mockReturnValueOnce(
        new Promise((resolve) => {
          resolveNew = resolve
        }),
      )
    mockChat.stockCode = 'sz.000001'
    const { rerender } = renderWorkspace()
    await act(async () => {})
    expect(screen.getByTestId('workspace-candles')).toHaveTextContent('old-date')
    mockChat.stockCode = 'sh.600000'
    rerender(
      <MemoryRouter>
        <AgentWorkspace />
      </MemoryRouter>,
    )
    expect(screen.queryByTestId('workspace-candles')).toBeNull()
    expect(screen.getByText('暂无 sh.600000 的 K 线数据')).toBeInTheDocument()
    await act(async () => {
      resolveNew([row('new-date')] as Awaited<ReturnType<typeof getStockKline>>)
    })
    expect(screen.getByTestId('workspace-candles')).toHaveTextContent('new-date')
  })

  it('ignores the obsolete candle response after a target switch', async () => {
    let resolveOld!: (value: Awaited<ReturnType<typeof getStockKline>>) => void
    let resolveNew!: (value: Awaited<ReturnType<typeof getStockKline>>) => void
    vi.mocked(getStockKline)
      .mockReturnValueOnce(
        new Promise((resolve) => {
          resolveOld = resolve
        }),
      )
      .mockReturnValueOnce(
        new Promise((resolve) => {
          resolveNew = resolve
        }),
      )
    mockChat.stockCode = 'sz.000001'
    const { rerender } = renderWorkspace()
    mockChat.stockCode = 'sh.600000'
    rerender(
      <MemoryRouter>
        <AgentWorkspace />
      </MemoryRouter>,
    )
    const row = (date: string) => ({
      date,
      open: 1,
      close: 2,
      low: 1,
      high: 2,
      volume: 100,
    })
    await act(async () => {
      resolveNew([row('new-date')] as Awaited<ReturnType<typeof getStockKline>>)
    })
    await act(async () => {
      resolveOld([row('old-date')] as Awaited<ReturnType<typeof getStockKline>>)
    })
    expect(screen.getByTestId('workspace-candles')).toHaveTextContent('new-date')
    expect(screen.getByTestId('workspace-candles')).not.toHaveTextContent('old-date')
  })

  it('当前会话带 last_run_id 时右栏自动 attach', () => {
    mockChat.currentThread = {
      thread_id: 't-1',
      title: '会话',
      last_run_id: 'run-99',
      status: 'active',
      archived: false,
    }
    renderWorkspace()
    expect(mockRun.attach).toHaveBeenCalledWith('run-99')
  })
})
