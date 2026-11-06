import { renderMarketChart } from './charts.js'

const STOCKS = [
  { code: 'sh.600519', name: '贵州茅台' },
  { code: 'sz.300750', name: '宁德时代' },
  { code: 'sh.600036', name: '招商银行' },
]
const fmt = (n, digits = 2) =>
  Number.isFinite(n)
    ? n.toLocaleString('zh-CN', {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
      })
    : '—'
const signed = (n) => (Number.isFinite(n) ? `${n > 0 ? '+' : ''}${fmt(n)}%` : '—')
const normalize = (code) =>
  String(code || '')
    .toLowerCase()
    .replace(/[.]/g, '')
const chinaTime = (value) => {
  if (!value) return null
  const date = new Date(typeof value === 'number' ? value * 1000 : value)
  return Number.isNaN(date.getTime())
    ? null
    : date.toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false })
}
const quoteDate = (quote, section) => quote?.market_at || section?.market_at || null
const phase = (value) => {
  if (!value) return '报价时间未提供'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '报价时间未提供'
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    weekday: 'short',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).formatToParts(new Date())
  const get = (key) => parts.find((part) => part.type === key)?.value
  const day = `${get('year')}-${get('month')}-${get('day')}`
  const quoteDay = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(date)
  const minutes = Number(get('hour')) * 60 + Number(get('minute'))
  if (
    get('weekday') === 'Sat' ||
    get('weekday') === 'Sun' ||
    minutes > 15 * 60 ||
    minutes < 9 * 60 + 15
  )
    return '休市时段 · 最近报价'
  if (quoteDay !== day || Date.now() - date.getTime() > 120 * 1000)
    return '最近报价 · 非当前行情'
  if (minutes > 11 * 60 + 30 && minutes < 13 * 60) return '午间休市 · 最近报价'
  return '行情快照 · 30 秒刷新'
}

export function initMarketBoard() {
  const board = document.querySelector('[data-market-board]')
  if (!board) return
  const el = (selector) => board.querySelector(selector)
  const text = (selector, value) => {
    const node = el(selector)
    if (node) node.textContent = value
  }
  let selected = STOCKS[0]
  let snapshot = null
  let visible = true
  let snapshotBusy = false
  let timer = 0
  let failures = 0
  let seriesVersion = 0
  let seriesController = null
  let snapshotController = null
  let seriesBusy = false
  let seriesSnapshot = null
  const getSelectedQuote = () => {
    const section = snapshot?.quotes
    const quote = section?.data?.find(
      (item) => normalize(item.symbol) === normalize(selected.code),
    )
    return quote ? { ...quote, market_at: quoteDate(quote, section) } : null
  }
  const redrawSeries = () => {
    if (seriesSnapshot?.code === selected.code)
      renderMarketChart(el('[data-price-chart]'), seriesSnapshot.data, {
        name: selected.name,
        code: selected.code,
        volumeContainer: el('[data-volume-chart]'),
        tableBody: el('tbody'),
        getQuote: getSelectedQuote,
      })
  }
  if ('ResizeObserver' in window) {
    let width = 0
    const resize = new window.ResizeObserver((entries) => {
      const nextWidth = Math.round(entries[0].contentRect.width)
      if (nextWidth !== width) {
        width = nextWidth
        redrawSeries()
      }
    })
    resize.observe(el('[data-price-chart]'))
  }
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  const setDirection = (node, value) => {
    node.dataset.direction = value > 0 ? 'up' : value < 0 ? 'down' : 'flat'
  }
  const clearQuote = () => {
    text('[data-price]', '—')
    text('[data-change]', '—')
    text('[data-amount]', '—')
    text('[data-volume]', '—')
  }
  const renderSnapshot = () => {
    const section = snapshot?.quotes
    const quote = section?.data?.find(
      (item) => normalize(item.symbol) === normalize(selected.code),
    )
    text('[data-selected-name]', selected.name)
    text('[data-selected-code]', selected.code.toUpperCase())
    if (quote && Number.isFinite(quote.close) && quote.close > 0) {
      const price = el('[data-price]'),
        before = price.textContent,
        after = fmt(quote.close)
      price.textContent = after
      if (!reduceMotion && before !== '—' && before !== after)
        price.animate(
          [
            { opacity: 0.45, transform: 'translateY(6px)' },
            { opacity: 1, transform: 'translateY(0)' },
          ],
          { duration: 160, easing: 'cubic-bezier(.22,1,.36,1)' },
        )
      text(
        '[data-change]',
        `${quote.change > 0 ? '+' : ''}${fmt(quote.change)} · ${signed(quote.change_percent)}`,
      )
      setDirection(el('[data-change]'), quote.change_percent)
      text(
        '[data-volume]',
        Number.isFinite(quote.volume)
          ? `${fmt(quote.volume / 10000, 2)} 万手`
          : '未提供',
      )
      text(
        '[data-amount]',
        Number.isFinite(quote.amount)
          ? `${fmt(quote.amount / 100000000, 2)} 亿元`
          : '未提供',
      )
      const marketAt = quoteDate(quote, section)
      text('[data-quote-time]', `报价时间 ${chinaTime(marketAt) || '未提供'}`)
      text('[data-market-state]', phase(marketAt))
      text(
        '[data-market-source]',
        `来源 ${section.provider || '未提供'} · 获取 ${chinaTime(section.fetched_at) || '时间未提供'}`,
      )
      const outdated = marketAt && Date.now() - new Date(marketAt).getTime() > 120000
      text(
        '[data-market-message]',
        outdated
          ? '历史/延迟报价 · 请以报价时间判断数据时效。'
          : section.stale
            ? '缓存快照 · 请核对报价时间，部分标的数据可能延迟。'
            : '公开行情快照，仅供研究；来源可能存在延迟。',
      )
      el('[data-market-retry]').hidden = true
    } else {
      clearQuote()
      text('[data-market-state]', '行情待恢复')
      text('[data-quote-time]', '报价时间未提供')
      text('[data-market-source]', `来源 ${section?.provider || '未提供'}`)
      text(
        '[data-market-message]',
        section?.status === 'empty'
          ? '当前标的暂无报价，稍后重试。'
          : '行情暂不可用，请稍后重新获取。',
      )
      el('[data-market-retry]').hidden = false
    }
    const indices = el('[data-indices]')
    indices.replaceChildren()
    const list = snapshot?.indices?.data || []
    ;['sh.000001', 'sz.399001', 'sz.399006'].forEach((code, i) => {
      const quote = list.find((item) => normalize(item.symbol) === normalize(code))
      const item = document.createElement('div'),
        name = document.createElement('span'),
        value = document.createElement('strong'),
        change = document.createElement('span')
      name.textContent = ['上证指数', '深证成指', '创业板指'][i]
      value.textContent = fmt(quote?.close)
      change.textContent = signed(quote?.change_percent)
      change.className = 'index-change'
      setDirection(change, quote?.change_percent)
      item.append(name, value, change)
      indices.appendChild(item)
    })
    text(
      '[data-index-source]',
      snapshot?.indices?.status === 'unavailable'
        ? '指数暂不可用'
        : `指数 ${snapshot?.indices?.stale ? '缓存 · ' : ''}${chinaTime(snapshot?.indices?.market_at) || '报价时间未提供'}`,
    )
  }
  const fetchJson = async (url, signal) => {
    const response = await window.fetch(url, {
      credentials: 'omit',
      signal,
      headers: { Accept: 'application/json' },
    })
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    return response.json()
  }
  const fetchSeries = async () => {
    const version = ++seriesVersion
    seriesController?.abort()
    const controller = new window.AbortController()
    seriesController = controller
    const code = selected.code,
      name = selected.name
    seriesBusy = true
    const timeout = window.setTimeout(() => controller.abort(), 12000)
    text('[data-chart-heading]', `${name} · 分时价格`)
    if (!seriesSnapshot || seriesSnapshot.code !== code)
      text('[data-series-meta]', '正在获取真实分时数据…')
    el('[data-price-chart]').setAttribute('aria-busy', 'true')
    try {
      const result = await fetchJson(
        `/api/v1/public/market/intraday?code=${encodeURIComponent(code)}`,
        controller.signal,
      )
      if (version !== seriesVersion) return
      if (!Array.isArray(result.data)) throw new Error('Invalid series')
      if (result.status === 'unavailable' && seriesSnapshot?.code === code)
        throw new Error('Series unavailable')
      seriesSnapshot =
        result.status === 'ok' && result.data.length
          ? { code, data: result.data }
          : null
      renderMarketChart(el('[data-price-chart]'), result.data, {
        name,
        code,
        volumeContainer: el('[data-volume-chart]'),
        tableBody: el('tbody'),
        getQuote: getSelectedQuote,
      })
      text(
        '[data-series-meta]',
        result.status === 'unavailable'
          ? '分时接口暂不可用 · 报价仍可独立查看'
          : `${result.stale ? '缓存分时 · ' : ''}${result.trade_date || '日期未提供'} · ${result.provider || '来源未提供'} · 分钟成交量（手）`,
      )
    } catch {
      if (version !== seriesVersion || !visible || document.hidden) return
      if (seriesSnapshot?.code === code) {
        text('[data-series-meta]', '分时连接中断 · 保留上次缓存曲线，请核对数据日期。')
      } else {
        renderMarketChart(el('[data-price-chart]'), [], {
          name,
          code,
          volumeContainer: el('[data-volume-chart]'),
          tableBody: el('tbody'),
          getQuote: getSelectedQuote,
        })
        text('[data-series-meta]', '分时数据暂不可用，报价与分时接口独立。')
      }
    } finally {
      window.clearTimeout(timeout)
      if (version === seriesVersion) {
        seriesBusy = false
        el('[data-price-chart]').setAttribute('aria-busy', 'false')
      }
    }
  }
  const schedule = () => {
    window.clearTimeout(timer)
    if (visible && !document.hidden)
      timer = window.setTimeout(refresh, Math.min(120000, 30000 * 2 ** failures))
  }
  const onScreen = () => {
    const rect = board.getBoundingClientRect()
    return (
      !document.hidden && rect.bottom >= -120 && rect.top <= window.innerHeight + 120
    )
  }
  const refresh = async () => {
    if (snapshotBusy || !visible || !onScreen()) return
    snapshotBusy = true
    const controller = new window.AbortController()
    snapshotController = controller
    const timeout = window.setTimeout(() => controller.abort(), 12000)
    try {
      const result = await fetchJson('/api/v1/public/market', controller.signal)
      if (!result.quotes || !result.indices) throw new Error('Invalid snapshot')
      snapshot = result
      failures = result.quotes.status === 'unavailable' ? Math.min(failures + 1, 2) : 0
      renderSnapshot()
    } catch {
      if (!visible || document.hidden) return
      failures = Math.min(failures + 1, 2)
      if (snapshot) {
        snapshot = {
          ...snapshot,
          quotes: { ...snapshot.quotes, stale: true },
          indices: { ...snapshot.indices, stale: true },
        }
        renderSnapshot()
        text('[data-market-message]', '连接中断 · 保留上次报价，当前行情未确认')
        el('[data-market-retry]').hidden = false
      } else {
        snapshot = {
          indices: { status: 'unavailable', data: [] },
          quotes: { status: 'unavailable', data: [] },
        }
        renderSnapshot()
      }
    } finally {
      window.clearTimeout(timeout)
      snapshotBusy = false
      schedule()
    }
    if (!seriesBusy && visible && onScreen()) fetchSeries()
  }
  board.querySelectorAll('[data-stock]').forEach((button) => {
    button.addEventListener('click', () => {
      const stock = STOCKS.find((item) => item.code === button.dataset.stock)
      if (!stock || stock === selected) return
      selected = stock
      seriesSnapshot = null
      board
        .querySelectorAll('[data-stock]')
        .forEach((item) => item.setAttribute('aria-pressed', String(item === button)))
      renderSnapshot()
      // Never keep another symbol's curve visible under the new stock name.
      renderMarketChart(el('[data-price-chart]'), [], {
        name: selected.name,
        code: selected.code,
        volumeContainer: el('[data-volume-chart]'),
        tableBody: el('tbody'),
        getQuote: getSelectedQuote,
      })
      fetchSeries()
    })
  })
  el('[data-market-retry]').addEventListener('click', () => {
    failures = 0
    refresh()
  })
  const pause = () => {
    window.clearTimeout(timer)
    snapshotController?.abort()
    seriesController?.abort()
  }
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) pause()
    else if (visible) refresh()
  })
  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver(
      (entries) => {
        visible = entries.some((entry) => entry.isIntersecting)
        if (visible && !document.hidden) refresh()
        else pause()
      },
      { rootMargin: '120px' },
    )
    observer.observe(board)
  }
  refresh()
}
initMarketBoard()
