import { MemoryRouter } from 'react-router-dom'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { StrategyResults } from './StrategyResults'
import { BacktestDetails } from './details/BacktestDetails'

const result = {
  success: true,
  result_id: 42,
  strategy_name: 'ma_cross',
  stock_code: 'sh.600000',
  start_date: '2024-01-01',
  end_date: '2024-01-03',
  initial_capital: 100000,
  final_capital: 101000,
  parameters: { short_period: 5, long_period: 20 },
  trades: [],
  metrics: {
    sharpe_ratio: 1.2,
    total_return: 1,
    annual_return: 5,
    max_drawdown: 0.5,
    win_rate: 50,
    profit_factor: 1.1,
    total_trades: 0,
  },
  portfolio_values: [
    {
      date: '2024-01-01',
      total_value: 100000,
      cash: 100000,
      position_value: 0,
      position: 0,
    },
    {
      date: '2024-01-03',
      total_value: 101000,
      cash: 101000,
      position_value: 0,
      position: 0,
    },
  ],
}

describe('StrategyResults', () => {
  it('exposes the four research result tabs and saved history link', async () => {
    render(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <StrategyResults
          klineData={[]}
          signals={[]}
          signalStats={null}
          backtestResult={result}
          loading={{ signals: false, backtest: false }}
          chartRef={{ current: null }}
          chartOption={{}}
          portfolioChartOption={{}}
        />
      </MemoryRouter>,
    )

    expect(screen.getByText('行情与信号')).toBeInTheDocument()
    expect(screen.getByText('资金曲线')).toBeInTheDocument()
    expect(screen.getByText('绩效指标')).toBeInTheDocument()
    expect(screen.getByText('交易记录')).toBeInTheDocument()
    await userEvent.setup().click(screen.getByRole('tab', { name: '绩效指标' }))
    expect(screen.getByRole('link', { name: /#42/ })).toHaveAttribute(
      'href',
      '/history',
    )
  })
})

describe('BacktestDetails', () => {
  it('only offers an explicit save action after optimization', () => {
    const onRunBestBacktest = vi.fn()
    render(
      <BacktestDetails
        optimizeResult={{
          success: true,
          strategy_name: 'ma_cross',
          stock_code: 'sh.600000',
          metric: 'sharpe_ratio',
          best_params: { short_period: 5, long_period: 20 },
          best_score: 1.2,
          best_metrics: { total_return: 3 },
          total_combinations: 1,
          all_results: [],
        }}
        compareResult={null}
        onRunBestBacktest={onRunBestBacktest}
      />,
    )

    expect(
      screen.getByRole('button', { name: '用最优参数回测并保存' }),
    ).toBeInTheDocument()
    expect(onRunBestBacktest).not.toHaveBeenCalled()
  })
})
