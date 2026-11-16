;(() => {
  const doc = document
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches

  const safeNextPath = (value) => {
    if (
      !value ||
      !value.startsWith('/') ||
      Array.from(value).some((character) => {
        const code = character.charCodeAt(0)
        return character === '\\' || code < 32 || code === 127
      })
    )
      return null
    try {
      const destination = new window.URL(value, window.location.origin)
      return destination.origin === window.location.origin ? value : null
    } catch {
      return null
    }
  }

  const next = safeNextPath(new URLSearchParams(window.location.search).get('next'))
  if (next) {
    doc.querySelectorAll('a[href="/login"]').forEach((link) => {
      link.setAttribute('href', `/login?next=${encodeURIComponent(next)}`)
    })
  }

  const toggle = doc.querySelector('.nav-toggle')
  const menu = doc.getElementById('mobile-menu')
  const closeButton = doc.querySelector('.mobile-close')
  const menuLinks = menu ? Array.from(menu.querySelectorAll('a')) : []
  let lastFocused = null
  let closeTimer = 0
  let previousOverflow = ''
  let previousInert = []

  const onKeyDown = (event) => {
    if (event.key === 'Escape') {
      closeMenu()
      return
    }
    if (event.key !== 'Tab') return
    const items = [closeButton, ...menuLinks].filter(Boolean)
    const first = items[0]
    const last = items[items.length - 1]
    if (event.shiftKey && doc.activeElement === first) {
      event.preventDefault()
      last.focus()
    } else if (!event.shiftKey && doc.activeElement === last) {
      event.preventDefault()
      first.focus()
    }
  }

  const openMenu = () => {
    if (!menu || !toggle || !menu.hidden) return
    window.clearTimeout(closeTimer)
    lastFocused = doc.activeElement
    previousOverflow = doc.body.style.overflow
    previousInert = Array.from(doc.body.children)
      .filter((element) => element instanceof HTMLElement && element !== menu)
      .map((element) => [element, element.inert])
    previousInert.forEach(([element]) => {
      element.inert = true
    })
    menu.hidden = false
    requestAnimationFrame(() => menu.classList.add('is-open'))
    toggle.setAttribute('aria-expanded', 'true')
    doc.body.style.overflow = 'hidden'
    closeButton?.focus()
    doc.addEventListener('keydown', onKeyDown)
  }

  const closeMenu = () => {
    if (!menu || !toggle || menu.hidden) return
    menu.classList.remove('is-open')
    toggle.setAttribute('aria-expanded', 'false')
    doc.body.style.overflow = previousOverflow
    previousInert.forEach(([element, wasInert]) => {
      element.inert = wasInert
    })
    doc.removeEventListener('keydown', onKeyDown)
    closeTimer = window.setTimeout(
      () => {
        menu.hidden = true
      },
      reduceMotion ? 0 : 160,
    )
    const restore = lastFocused instanceof HTMLElement ? lastFocused : toggle
    restore.focus()
  }

  toggle?.addEventListener('click', openMenu)
  closeButton?.addEventListener('click', closeMenu)
  menuLinks.forEach((link) => link.addEventListener('click', closeMenu))
  window.matchMedia('(min-width: 651px)').addEventListener('change', (event) => {
    if (event.matches && menu && !menu.hidden) closeMenu()
  })

  const filters = doc.querySelector('.strategy-filters')
  const strategies = Array.from(doc.querySelectorAll('[data-strategy]'))
  if (filters) {
    filters.hidden = false
    filters.querySelectorAll('[data-filter]').forEach((button) => {
      button.addEventListener('click', () => {
        const category = button.dataset.filter
        let count = 0
        strategies.forEach((strategy) => {
          strategy.hidden = category !== 'all' && strategy.dataset.category !== category
          if (!strategy.hidden) count += 1
        })
        doc.querySelectorAll('[data-strategy-group]').forEach((group) => {
          group.hidden = category !== 'all' && group.dataset.strategyGroup !== category
        })
        const directory = doc.querySelector('.strategy-list')
        if (directory) directory.dataset.filtered = String(category !== 'all')
        filters.querySelectorAll('[data-filter]').forEach((item) => {
          item.setAttribute('aria-pressed', String(item === button))
        })
        const label = doc.querySelector('.strategy-count')
        if (label) label.textContent = `显示 ${count} 个内置策略`
      })
    })
  }

  const taglineWords = []
  doc.querySelectorAll('[data-tagline]').forEach((line) => {
    const text = (line.textContent || '').replace(/\s+/g, ' ').trim()
    line.textContent = ''
    const accessibleText = doc.createElement('span')
    accessibleText.className = 'sr-only'
    accessibleText.textContent = text
    line.appendChild(accessibleText)
    const tail = text.match(/[\p{Script=Han}]{2}[\p{P}]*\s*$/u)?.[0] || ''
    const body = tail ? text.slice(0, -tail.length) : text
    const segments =
      typeof Intl.Segmenter === 'function'
        ? Array.from(
            new Intl.Segmenter('zh-CN', { granularity: 'word' }).segment(body),
            (item) => item.segment,
          )
        : Array.from(body)
    if (tail) segments.push(tail)
    segments.forEach((segment) => {
      const word = doc.createElement('span')
      word.className = `tagline-word${segment === tail ? ' prose-tail' : ''}`
      word.setAttribute('aria-hidden', 'true')
      word.textContent = segment
      line.appendChild(word)
      taglineWords.push(word)
    })
  })

  // Register observers before enabling hidden entrance states; script failure leaves content readable.
  if (!reduceMotion && 'IntersectionObserver' in window) {
    const revealObserver = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return
          entry.target.classList.add('is-revealed')
          revealObserver.unobserve(entry.target)
        })
      },
      { threshold: 0.08 },
    )
    doc
      .querySelectorAll('[data-reveal]')
      .forEach((target) => revealObserver.observe(target))

    let taglineStarted = false
    const taglineObserver = new IntersectionObserver(
      (entries) => {
        if (taglineStarted || !entries.some((entry) => entry.isIntersecting)) return
        taglineStarted = true
        taglineWords.forEach((word, index) => {
          window.setTimeout(() => word.classList.add('is-lit'), index * 90)
        })
        taglineObserver.disconnect()
      },
      { rootMargin: '0px 0px -20% 0px' },
    )
    const tagline = doc.querySelector('.tagline')
    if (tagline) taglineObserver.observe(tagline)
    doc.documentElement.classList.add('motion-ready')
  } else {
    taglineWords.forEach((word) => word.classList.add('is-lit'))
  }

  const navLinks = Array.from(doc.querySelectorAll('.nav-links a[href^="#"]'))
  if ('IntersectionObserver' in window) {
    const navObserver = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return
          navLinks.forEach((link) => {
            if (link.getAttribute('href') === `#${entry.target.id}`)
              link.setAttribute('aria-current', 'true')
            else link.removeAttribute('aria-current')
          })
        })
      },
      { rootMargin: '-20% 0px -50% 0px' },
    )
    navLinks.forEach((link) => {
      const section = doc.querySelector(link.getAttribute('href'))
      if (section) navObserver.observe(section)
    })
  }
})()
