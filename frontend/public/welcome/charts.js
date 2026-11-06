const NS = 'http://www.w3.org/2000/svg'
const number = (value, digits = 2) =>
  Number(value).toLocaleString('zh-CN', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })
const timeLabel = (value) => String(value).slice(11, 16)
const svgNode = (tag, attrs = {}) => {
  const node = document.createElementNS(NS, tag)
  Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, String(value)))
  return node
}

/** Single-price series and separate volume plot: no fabricated or interpolated samples. */
export function renderMarketChart(
  container,
  input,
  { name, code, volumeContainer, tableBody, getQuote = () => null },
) {
  const rows = input
    .filter(
      (row) =>
        Number.isFinite(row.price) &&
        row.price > 0 &&
        typeof row.time === 'string' &&
        Number.isFinite(Date.parse(row.time)),
    )
    .slice(-300)
  container.replaceChildren()
  if (volumeContainer) volumeContainer.replaceChildren()
  if (tableBody) tableBody.replaceChildren()
  container.dataset.code = code
  if (!rows.length) {
    const empty = document.createElement('p')
    empty.className = 'chart-empty'
    empty.textContent = '暂无可用分时数据。价格与分时数据可能由不同接口提供。'
    container.appendChild(empty)
    return
  }
  const w = Math.max(280, container.clientWidth),
    h = 176,
    pad = { left: 12, right: 60, top: 20, bottom: 28 }
  const values = rows.map((row) => row.price)
  const min = Math.min(...values),
    max = Math.max(...values)
  const spread = Math.max(max - min, max * 0.002)
  const bottom = min - spread * 0.12,
    top = max + spread * 0.12
  const timestamps = rows.map((row) => Date.parse(row.time))
  const firstTime = timestamps[0],
    timeRange = Math.max(60000, timestamps.at(-1) - firstTime)
  const x = (i) =>
    pad.left + ((timestamps[i] - firstTime) / timeRange) * (w - pad.left - pad.right)
  const y = (price) =>
    pad.top + ((top - price) / (top - bottom)) * (h - pad.top - pad.bottom)
  const svg = svgNode('svg', {
    viewBox: `0 0 ${w} ${h}`,
    role: 'img',
    'aria-label': `${name}分时价格，${rows.length}个数据点；可使用方向键查看明细`,
    tabindex: 0,
  })
  const title = svgNode('title')
  title.textContent = `${name}分时价格`
  svg.appendChild(title)
  ;[max, (min + max) / 2, min].forEach((price) => {
    svg.appendChild(
      svgNode('line', {
        x1: pad.left,
        x2: w - pad.right + 4,
        y1: y(price),
        y2: y(price),
        class: 'chart-grid',
      }),
    )
    const label = svgNode('text', {
      x: w - pad.right + 12,
      y: y(price) + 4,
      class: 'chart-axis',
    })
    label.textContent = number(price)
    svg.appendChild(label)
  })
  const path = svgNode('path', {
    d: rows
      .map(
        (row, i) =>
          `${!i || timestamps[i] - timestamps[i - 1] > 90000 ? 'M' : 'L'}${x(i).toFixed(2)},${y(row.price).toFixed(2)}`,
      )
      .join(' '),
    fill: 'none',
    class: 'price-line',
    'stroke-width': 2,
    'stroke-linejoin': 'round',
    'stroke-linecap': 'round',
  })
  svg.appendChild(path)
  const endpoints = [
    [0, 'start'],
    [rows.length - 1, 'end'],
  ]
  endpoints.forEach(([i, anchor]) => {
    const label = svgNode('text', {
      x: x(i),
      y: h - 4,
      'text-anchor': anchor,
      class: 'chart-axis',
    })
    label.textContent = timeLabel(rows[i].time)
    svg.appendChild(label)
  })
  const crosshair = svgNode('line', {
    x1: x(rows.length - 1),
    x2: x(rows.length - 1),
    y1: 8,
    y2: h - pad.bottom,
    class: 'chart-crosshair',
  })
  const marker = svgNode('circle', {
    cx: x(rows.length - 1),
    cy: y(rows.at(-1).price),
    r: 5,
    class: 'chart-marker',
  })
  svg.append(crosshair, marker)
  const readout = document.createElement('p')
  readout.className = 'chart-readout'
  readout.setAttribute('aria-live', 'off')
  const tooltip = document.createElement('div')
  tooltip.className = 'chart-tooltip'
  tooltip.setAttribute('role', 'tooltip')
  tooltip.id = `quote-detail-${code.replace(/[^a-z0-9]/gi, '')}`
  tooltip.hidden = true
  svg.setAttribute('aria-describedby', tooltip.id)
  const tipHeading = document.createElement('p')
  tipHeading.className = 'chart-tooltip-heading'
  const tipPrice = document.createElement('strong')
  tipPrice.className = 'chart-tooltip-price'
  const tipDetails = document.createElement('dl')
  const tipNote = document.createElement('p')
  tipNote.className = 'chart-tooltip-note'
  tooltip.append(tipHeading, tipPrice, tipDetails, tipNote)
  let active = rows.length - 1
  const fillTooltip = () => {
    const row = rows[active]
    const quote = getQuote()
    tipHeading.textContent = `${name} · ${row.time.slice(0, 10)} ${timeLabel(row.time)}`
    tipPrice.textContent = `¥ ${number(row.price)}`
    tipDetails.replaceChildren()
    const detail = (label, value) => {
      const pair = document.createElement('div'),
        term = document.createElement('dt'),
        description = document.createElement('dd')
      term.textContent = label
      description.textContent = value
      pair.append(term, description)
      tipDetails.appendChild(pair)
    }
    const value = (n) => (Number.isFinite(n) && n > 0 ? number(n) : '未提供')
    detail(
      '分钟成交量',
      Number.isFinite(row.volume) ? `${number(row.volume, 0)} 手` : '未提供',
    )
    if (quote && quote.market_at?.slice(0, 10) === row.time.slice(0, 10)) {
      const ended = quote.market_at.slice(11, 16) >= '15:00'
      detail('当日开盘', value(quote.open))
      detail(ended ? '当日收盘' : '当日最新价', value(quote.close))
      detail('当日最高', value(quote.high))
      detail('当日最低', value(quote.low))
      detail(
        '当日累计成交量',
        Number.isFinite(quote.volume) ? `${number(quote.volume, 0)} 手` : '未提供',
      )
      tipNote.textContent = `日行情截至 ${timeLabel(quote.market_at)}；分钟数据与日行情分别标注。`
    } else {
      tipNote.textContent = '日行情日期不同或时间未提供，仅展示所选分钟数据。'
    }
  }
  const showTooltip = () => {
    fillTooltip()
    tooltip.hidden = false
    marker.setAttribute('r', '8')
    container.classList.add('chart-inspecting')
    const width = tooltip.offsetWidth || 260
    const left = Math.max(8, Math.min(w - width - 8, x(active) - width / 2))
    tooltip.style.transform = `translate(${left}px, -8px)`
  }
  const hideTooltip = () => {
    tooltip.hidden = true
    marker.setAttribute('r', '5')
    container.classList.remove('chart-inspecting')
  }
  const inspect = (i) => {
    active = Math.min(rows.length - 1, Math.max(0, i))
    const row = rows[active]
    crosshair.setAttribute('x1', x(active))
    crosshair.setAttribute('x2', x(active))
    marker.setAttribute('cx', x(active))
    marker.setAttribute('cy', y(row.price))
    readout.textContent = `${timeLabel(row.time)} · ¥ ${number(row.price)} · 成交量 ${Number.isFinite(row.volume) ? `${number(row.volume, 0)} 手` : '未提供'}`
    svg.setAttribute(
      'aria-label',
      `${name}分时价格，${readout.textContent}；使用左右方向键查看明细`,
    )
  }
  const inspectPointer = (event) => {
    const rect = svg.getBoundingClientRect()
    const target =
      firstTime +
      ((((event.clientX - rect.left) / rect.width) * w - pad.left) /
        (w - pad.left - pad.right)) *
        timeRange
    const nearest = timestamps.reduce(
      (best, stamp, i) =>
        Math.abs(stamp - target) < Math.abs(timestamps[best] - target) ? i : best,
      0,
    )
    inspect(nearest)
    showTooltip()
  }
  svg.addEventListener('pointermove', inspectPointer)
  svg.addEventListener('pointerdown', inspectPointer)
  svg.addEventListener('pointerleave', () => {
    if (document.activeElement !== svg) hideTooltip()
  })
  svg.addEventListener('focus', showTooltip)
  svg.addEventListener('blur', hideTooltip)
  svg.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      hideTooltip()
      return
    }
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return
    event.preventDefault()
    inspect(
      event.key === 'Home'
        ? 0
        : event.key === 'End'
          ? rows.length - 1
          : active + (event.key === 'ArrowRight' ? 1 : -1),
    )
    showTooltip()
  })
  container.append(svg, readout, tooltip)
  inspect(active)
  if (volumeContainer) {
    const volume = svgNode('svg', {
      viewBox: `0 0 ${w} 64`,
      role: 'img',
      'aria-label': `${name}每分钟成交量，单位手；明细见数据表`,
    })
    const volumes = rows.map((row) =>
      Number.isFinite(row.volume) && row.volume >= 0 ? row.volume : null,
    )
    const cap = Math.max(1, ...volumes.filter((value) => value !== null))
    const barWidth = Math.max(
      0.5,
      Math.min(10, (w - pad.left - pad.right) / rows.length - 2),
    )
    volumes.forEach((v, i) => {
      if (v === null) return
      volume.appendChild(
        svgNode('rect', {
          x: x(i) - barWidth / 2,
          y: 60 - (v / cap) * 48,
          width: barWidth,
          height: (v / cap) * 48,
          rx: 2,
          class: 'volume-bar',
        }),
      )
    })
    volumeContainer.appendChild(volume)
  }
  if (tableBody)
    rows.forEach((row) => {
      const tr = document.createElement('tr')
      ;[
        timeLabel(row.time),
        number(row.price),
        Number.isFinite(row.volume) ? number(row.volume, 0) : '未提供',
      ].forEach((value) => {
        const td = document.createElement('td')
        td.textContent = value
        tr.appendChild(td)
      })
      tableBody.appendChild(tr)
    })
}
