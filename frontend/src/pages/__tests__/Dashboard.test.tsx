import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import userEvent from '@testing-library/user-event'
import { AxiosError } from 'axios'

// Mock the api module so the Dashboard never reaches the network.
vi.mock('../../services/api', async () => {
  const actual =
    await vi.importActual<typeof import('../../services/api')>('../../services/api')
  return {
    ...actual,
    getRealtimeQuotes: vi.fn(),
    getRealtimeIndices: vi.fn(),
    getWatchlist: vi.fn(),
    getRealtimeBars: vi.fn(),
  }
})

// jsdom 无 canvas 2d 上下文，echarts 渲染会随机崩溃（"Cannot set properties
// of null (setting 'dpr')"）。该测试只断言功能行为，不测图表渲染，故 mock 掉
// echarts 组件以消除基线 flake。
vi.mock('echarts-for-react', () => ({
  default: () => <div data-testid="echarts-stub" />,
}))

import Dashboard from '../Dashboard'
import {
  getRealtimeQuotes,
  getRealtimeIndices,
  getWatchlist,
  getRealtimeBars,
} from '../../services/api'

const mockedQuotes = vi.mocked(getRealtimeQuotes)
const mockedIndices = vi.mocked(getRealtimeIndices)
const mockedWatchlist = vi.mocked(getWatchlist)
const mockedBars = vi.mocked(getRealtimeBars)

beforeEach(() => {
  vi.clearAllMocks()
  mockedWatchlist.mockReset()
  mockedQuotes.mockReset()
  mockedIndices.mockReset()
  mockedBars.mockReset()
  mockedWatchlist.mockResolvedValue({
    items: [
      {
        id: 1,
        stock_code: '600036',
        stock_name: '招商银行',
        added_at: '2026-08-14T00:00:00Z',
      },
    ],
    total: 1,
  })
  mockedQuotes.mockResolvedValue({
    success: true,
    data: [
      {
        symbol: '600036',
        open: 10,
        high: 11,
        low: 9.5,
        close: 10.5,
        volume: 1000,
        amount: 10000,
        change: 0.5,
        change_percent: 5,
        prev_close: 10,
      },
    ],
  })
  mockedIndices.mockResolvedValue({
    success: true,
    data: [
      {
        symbol: '000001',
        name: '上证指数',
        close: 3000,
        change: 10,
        change_percent: 0.33,
        prev_close: 2990,
      },
    ],
  })
  mockedBars.mockResolvedValue({
    success: true,
    code: '600036',
    data: [
      {
        date: '2026-08-13',
        open: 9.9,
        high: 10.1,
        low: 9.8,
        close: 10.0,
        volume: 100,
        amount: 1000,
        symbol: '600036',
      },
      {
        date: '2026-08-14',
        open: 10.0,
        high: 10.6,
        low: 10.0,
        close: 10.5,
        volume: 150,
        amount: 1500,
        symbol: '600036',
      },
    ],
  })
})

function renderDashboard() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('Dashboard partial degrade', () => {
  it('渲染指数、自选股和走势图', async () => {
    renderDashboard()
    await waitFor(() => expect(screen.getByText('上证指数')).toBeInTheDocument())
    await waitFor(() => expect(screen.getByText('招商银行')).toBeInTheDocument())
    expect(screen.getByText(/3,000|3000/)).toBeInTheDocument()
  })

  it('quotes 失败但 indices 成功时仍展示指数', async () => {
    const axiosError = new AxiosError(
      'Request failed',
      'ERR_BAD_REQUEST',
      undefined,
      undefined,
      {
        status: 503,
        data: {
          error: {
            code: 'provider_unavailable',
            message: '行情服务不可用',
            provider: 'mootdx',
            retryable: true,
            reason: 'no_healthy_server',
          },
        },
      } as never,
    )
    mockedQuotes.mockRejectedValueOnce(axiosError)

    renderDashboard()

    await waitFor(() => expect(screen.getByText('上证指数')).toBeInTheDocument())
    // quotes error renders an Alert + retry button. Verify the message appears.
    await waitFor(() => expect(screen.getByText('行情服务不可用')).toBeInTheDocument())
    // At least one retry button for the quotes block.
    expect(
      screen.getAllByRole('button', { name: /重试/ }).length,
    ).toBeGreaterThanOrEqual(1)
  })

  it('趋势图加载失败时显示重试按钮，点击后重新拉取', async () => {
    const axiosError = new AxiosError(
      'trend boom',
      'ERR_BAD_REQUEST',
      undefined,
      undefined,
      {
        status: 503,
        data: {
          error: {
            code: 'provider_unavailable',
            message: '行情服务不可用',
            provider: 'mootdx',
            retryable: true,
            reason: 'no_healthy_server',
          },
        },
      } as never,
    )
    mockedBars.mockRejectedValueOnce(axiosError)

    renderDashboard()

    // 等待 trend 加载失败 — at least one retry button visible
    await waitFor(() =>
      expect(
        screen.getAllByRole('button', { name: /重试/ }).length,
      ).toBeGreaterThanOrEqual(1),
    )

    mockedBars.mockResolvedValueOnce({
      success: true,
      code: '600036',
      data: [
        {
          date: '2026-08-14',
          open: 10.0,
          high: 10.6,
          low: 10.0,
          close: 10.5,
          volume: 150,
          amount: 1500,
          symbol: '600036',
        },
      ],
    })
    // Find the retry button inside the trend block (its onClick calls loadTrendData).
    // The page-level "刷新" button has icon-only label "刷新" (Refresh), and the
    // block-level retry buttons say "重试". Click the first "重试" button.
    const retryButtons = screen.getAllByRole('button', { name: /重试/ })
    await userEvent.click(retryButtons[0])

    await waitFor(() => expect(mockedBars).toHaveBeenCalledTimes(2))
  })
})
