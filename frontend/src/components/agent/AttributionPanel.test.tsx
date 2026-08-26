import { render, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { getAttribution } from '../../services/agentRuns'
import type { AttributionData } from '../../types/agent'
import { AttributionPanel } from './AttributionPanel'

vi.mock('../../services/agentRuns', () => ({
  getAttribution: vi.fn(),
}))

const mockedGetAttribution = vi.mocked(getAttribution)

function attribution(runId: string, alpha: number): AttributionData {
  return {
    run_id: runId,
    start_date: '2026-08-01',
    end_date: '2026-08-25',
    total_portfolio_return: 0.02,
    total_benchmark_return: 0.01,
    alpha,
    beta: 0.5,
    exposure_effect: 0.005,
    selection_effect: 0.004,
    cost_drag: 0.001,
    benchmark_available: true,
  }
}

describe('AttributionPanel', () => {
  beforeEach(() => mockedGetAttribution.mockReset())

  it('切换 run 时重新加载对应归因', async () => {
    mockedGetAttribution
      .mockResolvedValueOnce(attribution('run-1', 0.01))
      .mockResolvedValueOnce(attribution('run-2', -0.02))

    const { rerender } = render(<AttributionPanel runId="run-1" />)
    await waitFor(() => expect(mockedGetAttribution).toHaveBeenCalledWith('run-1'))
    expect(
      within(screen.getByText('Alpha（超额）').parentElement!).getByText('1.00%'),
    ).toBeInTheDocument()

    rerender(<AttributionPanel runId="run-2" />)
    await waitFor(() => expect(mockedGetAttribution).toHaveBeenCalledWith('run-2'))
    expect(
      within(screen.getByText('Alpha（超额）').parentElement!).getByText('-2.00%'),
    ).toBeInTheDocument()
  })

  it('没有当前 run 时不请求全局归因', () => {
    render(<AttributionPanel runId={null} />)

    expect(screen.getByText('请先运行一次股票研究')).toBeInTheDocument()
    expect(mockedGetAttribution).not.toHaveBeenCalled()
  })
})
