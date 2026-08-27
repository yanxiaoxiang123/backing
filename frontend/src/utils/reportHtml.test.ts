import { describe, expect, it } from 'vitest'
import type { AgentAnalyzeResponse } from '../types'
import { buildAgentReportHtml } from './reportHtml'

const report: AgentAnalyzeResponse = {
  success: true,
  stock_code: 'sh.600000',
  stock_name: '<img src=x onerror=alert(1)>',
  mode: 'standard',
  final_signal: 'buy',
  final_confidence: 0.8,
  final_reason: '<script>alert(1)</script>',
  opinions: [],
  stages: [
    {
      stage_name: 'decision<script>',
      status: 'completed',
      thinking: [],
      duration_s: 1,
      opinion: {
        agent_name: 'decision',
        signal: 'buy',
        confidence: 0.8,
        reason: 'safe & <unsafe>',
      },
    },
  ],
  news_items: [
    {
      title: 'headline <unsafe>',
      url: 'javascript:alert(1)',
      content: 'body <unsafe>',
    },
  ],
  duration_s: 1.234,
}

describe('buildAgentReportHtml', () => {
  it('escapes model content and rejects unsafe news links', () => {
    const html = buildAgentReportHtml(report)
    expect(html).not.toContain('<script>alert(1)</script>')
    expect(html).toContain('&lt;script&gt;alert(1)&lt;/script&gt;')
    expect(html).toContain('&lt;img src=x onerror=alert(1)&gt;')
    expect(html).not.toContain('href="javascript:')
    expect(html).toContain('headline &lt;unsafe&gt;')
  })
})
