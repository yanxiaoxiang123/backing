import type { Page } from '@playwright/test'
import { mockDashboardApi } from './dashboard'

export async function mockResearchEntry(page: Page) {
  await mockDashboardApi(page)
  const state = {
    failList: false,
    failRead: false,
    writes: [] as string[],
    contexts: [] as unknown[],
    alerts: [
      {
        id: 1,
        alert_type: 'data_quality',
        severity: 'warning',
        message: '浦发银行数据覆盖需要核验',
        is_read: false,
        created_at: '2026-11-05T03:30:00Z',
      },
      {
        id: 2,
        alert_type: 'risk',
        severity: 'critical',
        message: '万科A风险记录需要复核',
        is_read: false,
        created_at: '2026-11-05T04:30:00Z',
      },
    ],
  }
  const thread = (id: string) => ({
    thread_id: id,
    title: id === 'bank' ? '银行研究会话' : '地产研究会话',
    status: 'idle',
    last_run_id: null,
    archived: false,
    created_at: '2026-11-05T09:00:00Z',
    updated_at: '2026-11-05T09:42:00Z',
  })
  const turn = (id: string) => ({
    id: id === 'bank' ? 1 : 2,
    thread_id: id,
    content: '核验当前研究证据',
    status: 'completed',
    final_reply:
      id === 'bank'
        ? '银行研究已保存，请继续核验证据。'
        : '地产研究已保存，请关注风险。',
    error: null,
    end_reason: 'completed',
    created_at: '2026-11-05T09:42:00Z',
  })
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request()
    const path = new URL(request.url()).pathname
    if (request.method() === 'POST') state.writes.push(path)
    if (path.endsWith('/paper/alerts')) {
      return route.fulfill({
        status: state.failList ? 503 : 200,
        json: state.failList
          ? { error: { code: 'provider_unavailable', message: '告警读取失败' } }
          : { alerts: state.alerts },
      })
    }
    if (/\/paper\/alerts\/\d+\/read$/.test(path)) {
      if (state.failRead)
        return route.fulfill({
          status: 503,
          json: { error: { code: 'unavailable', message: '暂时无法标记已读' } },
        })
      const selected = state.alerts.find((alert) => path.endsWith(`/${alert.id}/read`))
      if (selected) selected.is_read = true
      return route.fulfill({ json: { success: true } })
    }
    if (path.endsWith('/agent-chats/status'))
      return route.fulfill({ json: { backend: 'fake', available: true, reason: null } })
    if (path.endsWith('/agent-chats'))
      return route.fulfill({
        json:
          request.method() === 'POST'
            ? thread('bank')
            : { threads: [thread('bank'), thread('property')], total: 2 },
      })
    if (path.includes('/agent-chats/')) {
      if (path.endsWith('/events'))
        return route.fulfill({
          contentType: 'text/event-stream',
          body: ': connected\n\n',
        })
      const id = path.split('/agent-chats/')[1].split('/')[0]
      if (path.endsWith('/turns')) {
        state.contexts.push(request.postDataJSON()?.context)
        return route.fulfill({ json: { turn: turn(id) } })
      }
      return route.fulfill({
        json: { thread: thread(id), turns: [turn(id)], has_more: false },
      })
    }
    return route.fallback()
  })
  return state
}
