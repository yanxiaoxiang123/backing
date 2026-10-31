import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import userEvent from '@testing-library/user-event'

import { DataQualityPanel } from './DataQualityPanel'
import { getDataQuality, syncRawHistory } from '../../services/marketData'

const waitForJob = vi.hoisted(() => vi.fn())
vi.mock('../../services/marketData', () => ({
  getDataQuality: vi.fn(),
  syncRawHistory: vi.fn(),
}))
vi.mock('../../hooks/useJobPolling', () => ({ useJobPolling: () => ({ waitForJob }) }))

function page(codes = ['sh.600000']) {
  return render(
    <QueryClientProvider
      client={
        new QueryClient({
          defaultOptions: { queries: { retry: false } },
        })
      }
    >
      <DataQualityPanel codes={codes} />
    </QueryClientProvider>,
  )
}

describe('DataQualityPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(getDataQuality).mockResolvedValue({
      total_stocks: 5913,
      covered_stocks: 2,
      missing_stocks: 5911,
      coverage_pct: 0.04,
      invalid_bars: 0,
      total_bars: 3304,
      raw_covered_stocks: 0,
      versioned_bars: 3304,
      calendar_rows: 20,
    })
  })

  it('distinguishes legacy coverage from actual zero raw-price coverage', async () => {
    page([])
    expect(await screen.findByText('0 只')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '补齐本页原始价格' })).toBeDisabled()
    expect(screen.getByText('0 根')).toBeInTheDocument()
  })

  it('only reports completion after the persisted job completes', async () => {
    vi.mocked(syncRawHistory).mockResolvedValue('history-job')
    waitForJob.mockResolvedValue({ success: true })
    page()
    await userEvent.click(screen.getByRole('button', { name: '补齐本页原始价格' }))
    expect(await screen.findByText('补数完成，已核对交易日历覆盖')).toBeInTheDocument()
    expect(syncRawHistory).toHaveBeenCalledWith(['sh.600000'])
    expect(waitForJob).toHaveBeenCalledWith('history-job')
  })

  it('shows failed ingestion and never labels it completed', async () => {
    vi.mocked(syncRawHistory).mockResolvedValue('history-job')
    waitForJob.mockRejectedValue(new Error('Missing trading sessions'))
    page()
    await userEvent.click(screen.getByRole('button', { name: '补齐本页原始价格' }))
    expect(await screen.findByText('Missing trading sessions')).toBeInTheDocument()
    expect(screen.queryByText('补数完成，已核对交易日历覆盖')).not.toBeInTheDocument()
  })
})
