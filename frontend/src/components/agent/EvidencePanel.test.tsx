import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { EvidencePanel } from './EvidencePanel'
import type { Claim } from '../../types/agent'

const claims: Claim[] = [
  {
    claim: '业绩预增利好',
    category: 'fundamental',
    direction: 'bullish',
    confidence: 0.8,
    evidence: [
      {
        source_id: 'announcement-1',
        as_of: '2026-08-01T15:00:00+08:00',
        vendor: 'akshare',
        data_version: 'v1',
        summary: '公告披露业绩预增',
      },
    ],
    hypothesis: false,
  },
  {
    claim: '缺乏数据，仅为假设',
    category: 'other',
    direction: 'neutral',
    confidence: 0.3,
    evidence: [],
    hypothesis: true,
  },
]

describe('EvidencePanel', () => {
  it('渲染证据条目与假设标记', () => {
    render(<EvidencePanel claims={claims} />)
    expect(screen.getByText('业绩预增利好')).toBeInTheDocument()
    expect(screen.getByText('有证据')).toBeInTheDocument()
    expect(screen.getByText('假设（无证据）')).toBeInTheDocument()
    expect(screen.getByText('announcement-1')).toBeInTheDocument()
    expect(screen.getByText('置信度 80%')).toBeInTheDocument()
    expect(screen.getByText('announcement-1')).toHaveClass('agent-evidence-source-id')
    expect(screen.getByText('公告披露业绩预增')).toHaveClass('agent-evidence-summary')
  })

  it('空数据显示占位', () => {
    render(<EvidencePanel claims={[]} />)
    expect(screen.getByText('暂无证据条目')).toBeInTheDocument()
  })
})
