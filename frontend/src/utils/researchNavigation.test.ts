import { describe, expect, it } from 'vitest'
import { readAlertId, readResearchPanel, workspaceHref } from './researchNavigation'

describe('research navigation', () => {
  it('hands off the exact conversation and normalized stock without unrelated page state', () => {
    expect(workspaceHref({ threadId: 'research/a?b', stockCode: '600000.SH' })).toBe(
      '/workspace?thread_id=research%2Fa%3Fb&stock=sh.600000',
    )
    expect(workspaceHref({ stockCode: 'not-a-stock' })).toBe('/workspace')
    expect(workspaceHref({ stockCode: '000002' })).toBe('/workspace?stock=sz.000002')
  })

  it('links to an alert while retaining an explicitly supplied conversation', () => {
    expect(workspaceHref({ threadId: 't-1', panel: 'alerts', alertId: 23 })).toBe(
      '/workspace?thread_id=t-1&panel=alerts&alert=23',
    )
    expect(workspaceHref({ panel: 'alerts', alertId: -1 })).toBe(
      '/workspace?panel=alerts',
    )
  })

  it.each([
    'market',
    'evidence',
    'backtest',
    'risk',
    'artifacts',
    'attribution',
    'alerts',
  ])('accepts the existing %s panel', (value) =>
    expect(readResearchPanel(value)).toBe(value),
  )
  it.each([null, '', 'unknown', '__proto__', 'ALERTS'])(
    'ignores unsupported panel %s',
    (value) => expect(readResearchPanel(value)).toBeNull(),
  )
  it.each([null, '', '0', '-1', '1.2', '1e2', '9007199254740992', 'abc'])(
    'rejects invalid alert ID %s',
    (value) => expect(readAlertId(value)).toBeNull(),
  )
  it('accepts positive safe integer alert IDs', () => {
    expect(readAlertId('23')).toBe(23)
  })
})
