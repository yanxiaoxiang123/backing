import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

vi.mock('echarts-for-react', () => ({
  default: () => <div data-testid="echarts-stub" />,
}))

const mockHook = vi.hoisted(() => ({
  run: null as Record<string, unknown> | null,
  events: [] as unknown[],
  researchClaims: [] as unknown[],
  backtestData: null as Record<string, unknown> | null,
  riskData: null as Record<string, unknown> | null,
  streamState: 'idle',
  artifacts: [] as unknown[],
  error: null as string | null,
  start: vi.fn(),
  cancel: vi.fn(),
  resume: vi.fn(),
}))

vi.mock('../../hooks/useAgentRun', () => ({
  useAgentRun: () => ({
    run: mockHook.run,
    events: mockHook.events,
    streamState: mockHook.streamState,
    artifacts: mockHook.artifacts,
    approvals: [],
    researchClaims: mockHook.researchClaims,
    backtestData: mockHook.backtestData,
    riskData: mockHook.riskData,
    error: mockHook.error,
    start: mockHook.start,
    cancel: mockHook.cancel,
    resume: mockHook.resume,
  }),
}))

vi.mock('../../services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../services/api')>()
  return { ...actual, getStockKline: vi.fn().mockResolvedValue([]) }
})

import AgentWorkspace from '../AgentWorkspace'

function renderWorkspace() {
  return render(
    <MemoryRouter initialEntries={['/workspace']}>
      <AgentWorkspace />
    </MemoryRouter>,
  )
}

beforeEach(() => {
  mockHook.run = null
  mockHook.events = []
  mockHook.researchClaims = []
  mockHook.backtestData = null
  mockHook.riskData = null
  mockHook.error = null
  mockHook.start.mockClear()
})

describe('AgentWorkspace', () => {
  it('渲染三栏布局：导航 / 对话 / 研究区', () => {
    renderWorkspace()
    expect(
      screen.getByRole('complementary', { name: /Agent 工作台导航/ }),
    ).toBeInTheDocument()
    expect(screen.getByLabelText('研究目标输入')).toBeInTheDocument()
    expect(screen.getByRole('region', { name: /股票研究区/ })).toBeInTheDocument()
  })

  it('研究区四页签可切换且不跳页', async () => {
    const user = userEvent.setup()
    renderWorkspace()
    expect(screen.getByText(/在左侧输入研究目标发起分析/)).toBeInTheDocument()

    await user.click(screen.getByRole('tab', { name: /证据/ }))
    expect(screen.getByText('暂无证据条目')).toBeInTheDocument()

    await user.click(screen.getByRole('tab', { name: /回测/ }))
    expect(screen.getByText('尚无回测结果')).toBeInTheDocument()

    await user.click(screen.getByRole('tab', { name: /风险/ }))
    expect(
      screen.getByText('演示：买入 sh.600519 100 股（模拟盘占位，无真实成交）'),
    ).toBeInTheDocument()
  })

  it('run 完成后研究面板展示结构化数据（证据/回测/风险）', async () => {
    const user = userEvent.setup()
    mockHook.run = {
      run_id: 'run-1',
      objective: '生成策略并回测验证 sh.600000',
      status: 'completed',
      steps: [],
    }
    mockHook.researchClaims = [
      {
        claim: 'K线收盘上穿MA5',
        category: 'technical',
        direction: 'bullish',
        confidence: 0.6,
        evidence: [],
        hypothesis: false,
      },
    ]
    mockHook.backtestData = {
      strategy_name: 'ma_cross_demo',
      total_return: 0.0143,
      annual_return: 0.0143,
      max_drawdown_pct: -0.9955,
      sharpe_out_of_sample: 0,
      passed: false,
      reasons: ['收益非正或回撤过大'],
    }
    mockHook.riskData = {
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

  it('审批卡批准后状态更新', async () => {
    const user = userEvent.setup()
    renderWorkspace()
    await user.click(screen.getByRole('tab', { name: /风险/ }))
    await user.click(screen.getByRole('button', { name: /批准（仅模拟盘）/ }))
    expect(screen.getByText('approved')).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: /批准（仅模拟盘）/ }),
    ).not.toBeInTheDocument()
  })
})
