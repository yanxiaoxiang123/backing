import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import PortfolioResearch from '../PortfolioResearch'
import {
  getPortfolioExperiment,
  listPortfolioExperiments,
  runPortfolioResearch,
} from '../../services/portfolioResearch'
import type { PortfolioExperiment } from '../../types/portfolioResearch'

const preparation = vi.hoisted(() => ({ ensure: vi.fn(), retry: vi.fn() }))
vi.mock('../../hooks/useResearchHistory', () => ({
  useResearchHistory: () => ({
    ...preparation,
    status: 'ready',
    progress: 100,
    error: '',
  }),
}))

vi.mock('../../components/StockSearch', () => ({
  default: ({
    value,
    onChange,
    id,
  }: {
    value?: string
    onChange?: (value: string) => void
    id?: string
  }) => (
    <input
      id={id}
      value={value ?? ''}
      onChange={(event) => onChange?.(event.target.value)}
    />
  ),
}))
vi.mock('../../services/portfolioResearch', () => ({
  runPortfolioResearch: vi.fn(),
  listPortfolioExperiments: vi.fn(),
  getPortfolioExperiment: vi.fn(),
  replayPortfolioExperiment: vi.fn(),
  exportPortfolioExperiment: vi.fn(),
}))
vi.mock('../../services/api', () => ({
  getApiErrorMessage: (error: Error) => error.message,
}))

function page() {
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <PortfolioResearch />
    </QueryClientProvider>,
  )
}

function enterStocks(first = '600000', second = '600004') {
  fireEvent.change(screen.getByLabelText('股票 1'), { target: { value: first } })
  fireEvent.change(screen.getByLabelText('股票 2'), { target: { value: second } })
}

describe('portfolio research', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    preparation.ensure.mockResolvedValue(undefined)
    vi.mocked(listPortfolioExperiments).mockResolvedValue({ total: 0, items: [] })
    vi.stubGlobal(
      'ResizeObserver',
      class {
        observe() {}
        disconnect() {}
      },
    )
  })

  it('sends normalized weights and cost units and shows coverage failures without success', async () => {
    vi.mocked(runPortfolioResearch).mockRejectedValue(
      new Error('Raw history incomplete'),
    )
    page()
    enterStocks()
    fireEvent.click(screen.getByRole('button', { name: '运行组合回测' }))
    expect(await screen.findByText('Raw history incomplete')).toBeInTheDocument()
    expect(runPortfolioResearch).toHaveBeenCalledWith(
      expect.objectContaining({
        weights: { 'sh.600000': 0.5, 'sh.600004': 0.5 },
        corporate_action_mode: 'verified',
        costs: expect.objectContaining({
          commission_rate: 0.00025,
          slippage_rate: 0.0001,
          max_participation: 0.1,
        }),
      }),
    )
    expect(screen.queryByRole('button', { name: '重放核验' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: '运行组合回测' })).toBeEnabled()
  })

  it('rejects duplicate securities before any research request', async () => {
    page()
    enterStocks('600000', 'sh.600000')
    fireEvent.click(screen.getByRole('button', { name: '运行组合回测' }))
    expect(
      await screen.findByText('请选择股票，且每只股票只添加一次'),
    ).toBeInTheDocument()
    expect(runPortfolioResearch).not.toHaveBeenCalled()
  })

  it('waits for selected historical data before submitting the portfolio', async () => {
    let finish!: () => void
    preparation.ensure.mockReturnValue(
      new Promise<void>((resolve) => {
        finish = resolve
      }),
    )
    vi.mocked(runPortfolioResearch).mockRejectedValue(new Error('backtest reached'))
    page()
    enterStocks()
    fireEvent.click(screen.getByRole('button', { name: '运行组合回测' }))
    await waitFor(() => expect(preparation.ensure).toHaveBeenCalled())
    expect(runPortfolioResearch).not.toHaveBeenCalled()
    await act(async () => finish())
    expect(await screen.findByText('backtest reached')).toBeInTheDocument()
  })

  it('stops the backtest when selected data cannot be fetched', async () => {
    preparation.ensure.mockRejectedValue(new Error('行情服务暂时不可用'))
    page()
    enterStocks()
    fireEvent.click(screen.getByRole('button', { name: '运行组合回测' }))
    expect(await screen.findByText('行情服务暂时不可用')).toBeInTheDocument()
    expect(runPortfolioResearch).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: '重新获取' }))
    expect(preparation.retry).toHaveBeenCalled()
    expect(screen.queryByText('行情服务暂时不可用')).not.toBeInTheDocument()
  })

  it('restores saved evidence with its original weights and period instead of the current form', async () => {
    const item: PortfolioExperiment = {
      experiment_id: 'saved',
      name: '已保存的组合',
      created_at: '2024-01-05',
      snapshot_sha256: 'a'.repeat(64),
      request: {
        name: '已保存的组合',
        weights: { 'sh.600000': 1 },
        start_date: '2024-01-02',
        end_date: '2024-01-04',
        initial_capital: 100000,
        rebalance: 'none',
        corporate_action_mode: 'price_only',
        dividend_tax_rate: 0,
        costs: {
          commission_rate: 0,
          minimum_commission: 0,
          sell_tax_rate: 0,
          transfer_rate: 0,
          slippage_rate: 0,
          max_participation: 1,
          lot_size: 100,
        },
      },
      metrics: { total_return: 0, max_drawdown: 0, total_fees: 0 },
      result: {
        initial_capital: 100000,
        final_capital: 100000,
        engine_version: 'portfolio-next-open-v1',
        metrics: { total_return: 0, max_drawdown: 0, total_fees: 0 },
        portfolio_values: [
          {
            date: '2024-01-02',
            total_value: 100000,
            cash: 100000,
            receivable: 0,
            positions: {},
          },
          {
            date: '2024-01-04',
            total_value: 100000,
            cash: 100000,
            receivable: 0,
            positions: {},
          },
        ],
        trades: [],
        unfilled_orders: [],
        limitations: [],
      },
    }
    vi.mocked(listPortfolioExperiments).mockResolvedValue({ total: 1, items: [item] })
    vi.mocked(getPortfolioExperiment).mockResolvedValue(item)
    page()
    await waitFor(() =>
      expect(screen.getByRole('button', { name: '重放核验' })).toBeInTheDocument(),
    )
    expect(
      screen.getByText('此实验仅计算价格收益，未计入分红和送转。'),
    ).toBeInTheDocument()
    expect(screen.getByText(/2024-01-02 至 2024-01-04 · 初始资金/)).toBeInTheDocument()
    expect(screen.getByText(/保存的目标配置.*sh.600000 100.00%/)).toBeInTheDocument()
    expect(
      screen.getByRole('img', { name: '组合与基准净值，初始资金归一为一' }),
    ).toBeInTheDocument()
  })
})
