import { expect, test, type Page } from '@playwright/test'

const reply = `## 研究口径

行情 ![标记](/test-dot.svg) 与风险要放在同一个时间区间里比较，先确认复权、成交量和交易成本，再核对研究依据。

本轮只整理验证条件，不生成交易指令。请先核对样本覆盖范围，再检查集中度与回撤约束，最后讨论策略是否适合继续验证。

| 项目 | 数值 |
| --- | --- |
| 示例参数 | 12.34 |
| 示例窗口 | 56.78 |

先核对数据，再评估风险。`

async function fixture(page: Page, streaming = false) {
  let sse = ': idle\n\n'
  let sequence = 0
  let savedReply = streaming ? '' : reply
  let completed = !streaming
  const frames: string[] = []
  const thread = {
    thread_id: 'polish-t1',
    title: '银行股估值与风险研究',
    status: streaming ? 'running' : 'idle',
    last_run_id: null,
    archived: false,
    created_at: '2026-11-05T09:00:00+08:00',
    updated_at: '2026-11-05T10:00:00+08:00',
  }
  await page.route('**/test-dot.svg', (route) =>
    route.fulfill({
      contentType: 'image/svg+xml',
      body: '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14"><circle cx="7" cy="7" r="5" fill="#636361"/></svg>',
    }),
  )
  await page.route('**/api/v1/**', (route) => {
    const path = new URL(route.request().url()).pathname
    let body: unknown = {}
    if (path.endsWith('/events'))
      return route.fulfill({ contentType: 'text/event-stream', body: sse })
    if (path.endsWith('/auth/me')) body = { authenticated: true }
    else if (path.endsWith('/agent-chats/status'))
      body = { backend: 'native', available: true, reason: null }
    else if (path.endsWith('/agent-chats'))
      body = {
        threads: [
          thread,
          { ...thread, thread_id: 'polish-t2', title: '均线策略与交易成本复核' },
        ],
        total: 2,
      }
    else if (path.includes('/agent-chats/'))
      body = {
        thread,
        turns: [
          {
            id: 1,
            thread_id: thread.thread_id,
            content: '整理银行股研究步骤',
            status: completed ? 'completed' : 'running',
            final_reply: savedReply || null,
            error: null,
            end_reason: null,
            created_at: thread.created_at,
          },
        ],
        has_more: false,
      }
    else if (path.endsWith('/paper/alerts')) body = { alerts: [] }
    else if (path.endsWith('/jobs/metrics'))
      body = { started_at: thread.created_at, counters: [], durations: [] }
    return route.fulfill({ json: body })
  })
  return (content: string, done = false) => {
    savedReply += content
    completed = done
    frames.push(
      `id: ${++sequence}\nevent: assistant_chunk\ndata: ${JSON.stringify({ turn_id: 1, content })}\n\n`,
    )
    if (done)
      frames.push(
        `id: ${++sequence}\nevent: turn.done\ndata: ${JSON.stringify({
          turn_id: 1,
          status: 'completed',
          final_reply: savedReply,
        })}\n\n`,
      )
    sse = frames.join('')
  }
}

test('微差底色分三层，网格撑满、等宽数字与行内图片对齐', async ({ page }) => {
  await fixture(page)
  await page.goto('/workspace?thread_id=polish-t1')
  await expect(page.getByRole('button', { name: '复制回复' })).toBeVisible()
  const styles = await page.evaluate(() => {
    const style = (selector: string) =>
      getComputedStyle(document.querySelector(selector)!)
    return {
      sidebar: style('.agent-workspace-chat-sidebar').backgroundColor,
      main: style('.agent-workspace-conversation').backgroundColor,
      card: style('.chat-msg-assistant .chat-bubble').backgroundColor,
      frame: style('.agent-workspace').borderWidth,
      field: style('.chat-input').borderWidth,
      newThread: style('.chat-sidebar-new').borderWidth,
      numbers: style('.chat-markdown').fontVariantNumeric,
      imageOffset: parseFloat(style('.chat-markdown img').top),
      fontSize: parseFloat(style('.chat-markdown').fontSize),
      scroll: style('.chat-scroll').scrollBehavior,
      tail: document.querySelector('.chat-nowrap-tail')?.textContent,
      row: document.querySelector('.chat-msg-assistant')!.getBoundingClientRect().width,
      cardWidth: document
        .querySelector('.chat-msg-assistant .chat-bubble')!
        .getBoundingClientRect().width,
    }
  })
  expect(styles.sidebar).toBe('rgb(240, 240, 240)')
  expect(styles.main).toBe('rgb(246, 246, 246)')
  expect(styles.card).toBe('rgb(252, 252, 252)')
  expect([styles.frame, styles.field, styles.newThread]).toEqual(['0px', '0px', '0px'])
  expect(styles.numbers).toContain('tabular-nums')
  expect(styles.imageOffset).toBeCloseTo(styles.fontSize / 8, 1)
  expect(styles.scroll).toBe('auto')
  expect(styles.tail!.replace(/\p{P}/gu, '').length).toBeGreaterThanOrEqual(2)
  expect(Math.abs(styles.row - styles.cardWidth)).toBeLessThan(1)
})

test('复制完整回复，成功对勾约 2.5 秒后消失', async ({ page }) => {
  await fixture(page)
  await page.addInitScript(() => {
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: {
        writeText: async (text: string) => {
          sessionStorage.setItem('copied-reply', text)
        },
      },
    })
  })
  await page.goto('/workspace?thread_id=polish-t1')
  await page.getByRole('button', { name: '复制回复' }).click()
  await expect(page.locator('.chat-copy-check')).toBeVisible()
  expect(
    await page
      .locator('.chat-copy-icon')
      .evaluate((node) => getComputedStyle(node).animationDuration),
  ).toBe('0.18s')
  await expect(page.locator('.chat-copy-status')).toHaveText('已复制')
  expect(await page.evaluate(() => sessionStorage.getItem('copied-reply'))).toBe(reply)
  await expect(page.locator('.chat-copy-check')).toHaveCount(0, { timeout: 4000 })
})

test('流式文字交叠对焦，停止后不重播历史，减少动态效果时保持清晰', async ({ page }) => {
  const emit = await fixture(page, true)
  await page.goto('/workspace?thread_id=polish-t1')
  await expect(page.locator('.chat-message-author')).toBeVisible()
  emit('银行估值和趋势需要同步验证，先核对数据。')
  await page.waitForFunction(() => document.querySelector('.chat-reveal-glyph'))
  const wave = await page.locator('.chat-markdown').evaluate((root) => {
    const letters = Array.from(root.querySelectorAll<HTMLElement>('.chat-reveal-glyph'))
    return {
      duration: getComputedStyle(letters[0]).animationDuration,
      delays: letters
        .slice(0, 5)
        .map((letter) => parseFloat(letter.style.animationDelay)),
      animations: letters.reduce(
        (total, letter) => total + letter.getAnimations().length,
        0,
      ),
    }
  })
  expect(wave.animations).toBeGreaterThan(1)
  expect(wave.duration).toBe('0.14s')
  expect(wave.delays[1] - wave.delays[0]).toBeGreaterThan(0)
  expect(wave.delays[1] - wave.delays[0]).toBeLessThanOrEqual(20)
  await expect(page.locator('.chat-reveal-glyph')).toHaveCount(0)
  await page.emulateMedia({ reducedMotion: 'reduce' })
  emit('再检查风险与交易成本。', true)
  await expect(page.locator('.chat-markdown')).toContainText('再检查风险与交易成本')
  expect(
    await page
      .locator('.chat-reveal-glyph')
      .evaluateAll((letters) =>
        letters.every(
          (letter) =>
            getComputedStyle(letter).filter === 'none' &&
            letter.getAnimations().length === 0,
        ),
      ),
  ).toBe(true)
  await page.reload()
  expect(await page.locator('.chat-markdown .chat-reveal-glyph').count()).toBe(0)
})

test('手机会话抽屉延续层次，回复和输入区不产生横向溢出', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await fixture(page)
  await page.goto('/workspace?thread_id=polish-t1')
  await expect(page.getByRole('button', { name: '复制回复' })).toBeVisible()
  await page.getByRole('button', { name: '打开会话列表' }).click()
  const drawer = page.getByRole('dialog', { name: '研究会话', exact: true })
  await expect(drawer).toBeVisible()
  await expect(
    page.locator('.agent-history-drawer .ant-drawer-content-wrapper'),
  ).toHaveCSS('transition-duration', '0.18s')
  await expect(drawer.locator('.chat-sidebar')).toHaveCSS(
    'background-color',
    'rgb(240, 240, 240)',
  )
  await drawer.getByRole('button', { name: /^银行股估值与风险研究/ }).click()
  await expect(drawer).toBeHidden()
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
  ).toBe(true)
  const input = await page.locator('.chat-input').boundingBox()
  expect(input!.y + input!.height).toBeLessThanOrEqual(844)
})
