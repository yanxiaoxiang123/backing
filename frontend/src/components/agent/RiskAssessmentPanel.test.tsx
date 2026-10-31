import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { RiskAssessmentPanel } from './RiskAssessmentPanel'
import { assessRunRisk, proposeRiskOrder } from '../../services/agentRuns'

vi.mock('../../services/agentRuns', () => ({
  assessRunRisk: vi.fn(),
  proposeRiskOrder: vi.fn(),
}))

beforeEach(() => vi.mocked(assessRunRisk).mockReset())

describe('RiskAssessmentPanel', () => {
  it('requires explicit target and rationale before requesting an assessment', async () => {
    render(<RiskAssessmentPanel runId="run-1" stockCode="sh.600000" />)
    await userEvent
      .setup()
      .click(screen.getByRole('button', { name: /计算风险与建议数量/ }))
    expect(await screen.findByText('请输入目标仓位')).toBeInTheDocument()
    expect(assessRunRisk).not.toHaveBeenCalled()
  })

  it('submits user intent and displays the calculated quantity and evidence outcome', async () => {
    vi.mocked(proposeRiskOrder).mockResolvedValue({
      order_id: 'paper-1',
      approval_id: 2,
      status: 'pending_approval',
    })
    vi.mocked(assessRunRisk).mockResolvedValue({
      account_id: 'default',
      equity: 100000,
      projected_cash: 89994,
      estimated_fees: 6,
      evidence_sha256: 'proof',
      artifact_id: 1,
      as_of: '2026-10-30T08:00:00',
      proposal: {
        rejected: false,
        constraints: [{ rule: 'cash_buffer', passed: true, detail: '保留现金缓冲' }],
      },
      orders: [
        {
          stock_code: 'sh.600000',
          side: 'buy',
          quantity: 1000,
          reference_price: 10,
          estimated_fees: 6,
          sizing_reasons: ['账户可用现金', '单票止损预算'],
        },
      ],
    })
    render(<RiskAssessmentPanel runId="run-1" stockCode="sh.600000" />)
    const user = userEvent.setup()
    await user.type(screen.getByRole('spinbutton', { name: '目标仓位（%）' }), '10')
    await user.type(screen.getByRole('spinbutton', { name: '止损距离（%）' }), '5')
    await user.type(
      screen.getByRole('textbox', { name: '调整理由' }),
      '明确研究后的目标',
    )
    await user.click(screen.getByRole('button', { name: /计算风险与建议数量/ }))
    await waitFor(() =>
      expect(assessRunRisk).toHaveBeenCalledWith('run-1', {
        targets: [
          {
            stock_code: 'sh.600000',
            target_weight: 0.1,
            stop_loss_pct: 0.05,
            reason: '明确研究后的目标',
          },
        ],
      }),
    )
    expect(await screen.findByText('1000')).toBeInTheDocument()
    expect(screen.getByText('保留现金缓冲')).toBeInTheDocument()
    expect(screen.getByText('账户可用现金、单票止损预算')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '提议开盘委托' }))
    expect(proposeRiskOrder).toHaveBeenCalledWith('run-1', {
      stock_code: 'sh.600000',
      side: 'buy',
      quantity: 1000,
      risk_artifact_id: 1,
    })
    expect(await screen.findByRole('button', { name: '已提议，待审批' })).toBeDisabled()
    await user.clear(screen.getByRole('spinbutton', { name: '目标仓位（%）' }))
    expect(screen.queryByText('1000')).not.toBeInTheDocument()
  })
})
