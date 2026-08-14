import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { StrategyList } from './StrategyList'
import type { StrategyInfo } from '../../types'

const strategies: StrategyInfo[] = [
  { name: 'ma_cross', description: 'MA strategy', parameters: {} },
  { name: 'mean_reversion', description: 'Reversion strategy', parameters: {} },
  { name: 'breakout', description: 'Breakout strategy', parameters: {} },
  { name: 'bollinger_breakout', description: 'Bollinger strategy', parameters: {} }
]

function renderList(selectedStrategy: string | null = null) {
  return render(
    <StrategyList
      strategies={strategies}
      selectedStrategy={selectedStrategy}
      loading={false}
      onSelect={() => {}}
    />
  )
}

describe('StrategyList', () => {
  it('按 趋势/震荡/突破 分类分组并显示中文名', () => {
    renderList()
    expect(screen.getByText(/^趋势 ·/)).toBeInTheDocument()
    expect(screen.getByText(/^震荡 ·/)).toBeInTheDocument()
    expect(screen.getByText(/^突破 ·/)).toBeInTheDocument()
    expect(screen.getByText('均线交叉')).toBeInTheDocument()
    expect(screen.getByText('均值回归')).toBeInTheDocument()
    expect(screen.getByText('突破策略')).toBeInTheDocument()
    expect(screen.getByText('布林带突破')).toBeInTheDocument()
  })

  it('搜索可按中文名过滤策略', async () => {
    const user = userEvent.setup()
    renderList()
    await user.type(screen.getByLabelText('搜索策略'), '布林')
    expect(screen.getByText('布林带突破')).toBeInTheDocument()
    expect(screen.queryByText('均线交叉')).not.toBeInTheDocument()
    expect(screen.queryByText('均值回归')).not.toBeInTheDocument()
  })

  it('点击策略触发 onSelect', async () => {
    const user = userEvent.setup()
    const onSelect = vi.fn()
    render(
      <StrategyList
        strategies={strategies}
        selectedStrategy={null}
        loading={false}
        onSelect={onSelect}
      />
    )
    await user.click(screen.getByText('均线交叉'))
    expect(onSelect).toHaveBeenCalledWith('ma_cross')
  })

  it('选中项标记 aria-pressed', () => {
    renderList('ma_cross')
    const selected = screen.getByRole('button', { name: /均线交叉/ })
    expect(selected).toHaveAttribute('aria-pressed', 'true')
  })
})
