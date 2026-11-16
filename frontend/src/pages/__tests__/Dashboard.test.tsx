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
    getAnalysisHistory: vi.fn(),
  }
})

// The shell status is not the dashboard's concern; keep it quiet.
vi.mock('../../hooks/useSystemStatus', () => ({
  useSystemStatus: () => ({
    alerts: [],
    unreadAlerts: 0,
    completed: 0,
    failed: 0,
    isLoading: false,
    alertsError: false,
    metricsError: false,
    isError: false,
    refetch: vi.fn(),
  }),
}))

// jsdom 无 canvas 2d 上下文，echarts 渲染会随机崩溃（"Cannot set properties
// of null (setting 'dpr')"）。该测试只断言功能行为，不测图表渲染，故 mock 掉
// echarts 组件以消除基线 flake。
import Dashboard from '../Dashboard'
import {
  getRealtimeQuotes,
  getRealtimeIndices,
  getWatchlist,
  getRealtimeBars,
  getAnalysisHistory,
} from '../../services/api'

const mockedQuotes = vi.mocked(getRealtimeQuotes)
const mockedIndices = vi.mocked(getRealtimeIndices)
const mockedWatchlist = vi.mocked(getWatchlist)
const mockedBars = vi.mocked(getRealtimeBars)
const mockedAnalysisHistory = vi.mocked(getAnalysisHistory)

beforeEach(() => {
  vi.clearAllMocks()
  mockedWatchlist.mockReset()
  mockedQuotes.mockReset()
  mockedIndices.mockReset()
  mockedBars.mockReset()
  mockedAnalysisHistory.mockReset()
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
  mockedAnalysisHistory.mockResolvedValue([
    {
      id: 1,
      stock_code: '600036',
      stock_name: '招商银行',
      analysis_date: '2026-08-14',
      mode: 'quick',
      final_signal: 'buy',
      final_confidence: 0.72,
      final_reason: '量价配合，短线偏强，关注 10.80 附近的压力位。',
      duration_s: 12,
      created_at: '2026-08-14T09:30:00',
    },
  ])
})

function renderDashboard() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <Dashboard />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('Dashboard partial degrade', () => {
  it('按所选月份筛选真实日线，日期以最后可用交易日为准', async () => {
    mockedBars.mockResolvedValue({
      success: true,
      code: '600036',
      data: ['2026-01-05', '2026-07-20', '2026-08-14'].map((date, index) => ({
        date,
        open: 10,
        high: 13,
        low: 9,
        close: 10 + index,
        volume: 100,
        amount: 1000,
        symbol: '600036',
      })),
    })
    renderDashboard()
    await screen.findByRole('img', { name: /近6个月收盘价走势，2个交易日/ })
    await userEvent.click(screen.getByRole('button', { name: /^1月$/ }))
    expect(
      screen.getByRole('img', { name: /近1个月收盘价走势，2个交易日/ }),
    ).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /^1年$/ }))
    expect(
      screen.getByRole('img', { name: /近12个月收盘价走势，3个交易日/ }),
    ).toBeInTheDocument()
    expect(screen.getByText(/2026-01-05 — 2026-08-14/)).toBeInTheDocument()
    expect(mockedBars).toHaveBeenCalledTimes(1)
  })

  it('没有分析记录时展示发起入口与空状态，不生成研究信号', async () => {
    mockedAnalysisHistory.mockResolvedValue([])
    renderDashboard()
    await screen.findByRole('heading', { name: '今天还没有研究结论' })
    expect(screen.getByRole('button', { name: '发起分析' })).toBeInTheDocument()
    expect(screen.getByText('未分析')).toBeInTheDocument()
    expect(screen.queryByText('买入')).not.toBeInTheDocument()
    expect(screen.getByText('上证指数')).toBeInTheDocument()
  })

  it('渲染指数、自选股、走势图和最新研究结论', async () => {
    renderDashboard()
    await waitFor(() => expect(screen.getByText('上证指数')).toBeInTheDocument())
    expect(screen.getAllByText('招商银行').length).toBeGreaterThan(0)
    expect(screen.getByText(/3,000|3000/)).toBeInTheDocument()
    await waitFor(() => expect(screen.getAllByText('买入').length).toBeGreaterThan(0))
    expect(screen.getByText('72%')).toBeInTheDocument()
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
    await waitFor(() => expect(screen.getByText('行情服务不可用')).toBeInTheDocument())
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

    const retryButtons = screen.getAllByRole('button', { name: /重试/ })
    await userEvent.click(retryButtons[0])

    await waitFor(() => expect(mockedBars).toHaveBeenCalledTimes(2))
  })

  it('研究结论失败时只降级 hero，不影响行情概览', async () => {
    mockedAnalysisHistory.mockRejectedValueOnce(new Error('研究摘要暂不可用'))

    renderDashboard()

    await waitFor(() => expect(screen.getByText('上证指数')).toBeInTheDocument())
    await waitFor(() =>
      expect(screen.getByText('研究摘要暂不可用')).toBeInTheDocument(),
    )
    expect(
      screen.getByText(
        (_, node) => node?.tagName === 'P' && node.textContent === '分析记录暂不可用。',
      ),
    ).toBeInTheDocument()
    expect(
      screen.getAllByRole('button', { name: /重试/ }).length,
    ).toBeGreaterThanOrEqual(1)
  })
})
