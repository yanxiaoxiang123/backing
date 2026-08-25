import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('../../services/api', async () => {
  const actual =
    await vi.importActual<typeof import('../../services/api')>('../../services/api')
  return {
    ...actual,
    submitScreener: vi.fn(),
    getScreenerStatus: vi.fn(),
    cancelJob: vi.fn(),
  }
})

import Screener from '../Screener'
import { getScreenerStatus, submitScreener } from '../../services/api'

const mockedSubmit = vi.mocked(submitScreener)
const mockedStatus = vi.mocked(getScreenerStatus)

describe('Screener', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockedSubmit.mockResolvedValue({ job_id: 'screen-1' })
  })

  it('扫描完成但零命中时展示完成摘要，而不是退回初始页面', async () => {
    mockedStatus.mockResolvedValue({
      status: 'completed',
      progress: 1,
      result: { success: true, total_scanned: 5200, results: [] },
    })

    const user = userEvent.setup()
    render(<Screener />)
    await user.click(screen.getByRole('button', { name: /开始 AI 选股/ }))

    expect(await screen.findByText('全市场扫描完成')).toBeInTheDocument()
    expect(screen.getByText(/共扫描 5200 只有效股票/)).toBeInTheDocument()
    expect(screen.getByText(/本轮没有股票同时满足筛选条件/)).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: /开始 AI 选股/ }),
    ).not.toBeInTheDocument()
  })

  it('扫描命中时展示返回的股票卡片', async () => {
    mockedStatus.mockResolvedValue({
      status: 'completed',
      progress: 1,
      result: {
        success: true,
        total_scanned: 5200,
        results: [
          {
            stock_code: 'sh.600000',
            stock_name: '浦发银行',
            close: 10.5,
            volume: 1000,
            change_pct: 1.2,
            ma5: 10.4,
            ma10: 10.2,
            ma20: 10,
            macd_dif: 0.2,
            macd_dea: 0.1,
            macd_hist: 0.1,
            rsi: 55,
            volume_ratio: 1.8,
            composite_score: 88,
            ai_signal: 'buy',
            ai_confidence: 0.8,
            ai_reason: '趋势向上',
          },
        ],
      },
    })

    const user = userEvent.setup()
    render(<Screener />)
    await user.click(screen.getByRole('button', { name: /开始 AI 选股/ }))

    await waitFor(() => expect(screen.getByText('浦发银行')).toBeInTheDocument())
    expect(screen.getByText('AI 精选 TOP 5')).toBeInTheDocument()
    expect(screen.getByText('趋势向上')).toBeInTheDocument()
  })
})
