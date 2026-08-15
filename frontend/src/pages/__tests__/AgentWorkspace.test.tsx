import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import AgentWorkspace from '../AgentWorkspace'

function renderWorkspace() {
  return render(
    <MemoryRouter initialEntries={['/workspace']}>
      <AgentWorkspace />
    </MemoryRouter>,
  )
}

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
