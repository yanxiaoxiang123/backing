(() => {
  const doc = document
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches

  const safeNextPath = (value) => {
    if (!value) return null
    if (!value.startsWith('/')) return null
    if (value.startsWith('//')) return null
    if (value.startsWith('/\\')) return null
    return value
  }

  const params = new URLSearchParams(window.location.search)
  const next = safeNextPath(params.get('next'))
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

  const focusables = () => [closeButton, ...menuLinks].filter(Boolean)

  const onKeyDown = (event) => {
    if (event.key === 'Escape') {
      closeMenu()
      return
    }
    if (event.key !== 'Tab' || !menu) return
    const items = focusables()
    if (items.length === 0) return
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
    if (!menu || !toggle) return
    window.clearTimeout(closeTimer)
    lastFocused = doc.activeElement
    menu.hidden = false
    requestAnimationFrame(() => menu.classList.add('is-open'))
    toggle.setAttribute('aria-expanded', 'true')
    doc.body.style.overflow = 'hidden'
    closeButton?.focus()
    doc.addEventListener('keydown', onKeyDown)
  }

  const closeMenu = () => {
    if (!menu || !toggle) return
    menu.classList.remove('is-open')
    toggle.setAttribute('aria-expanded', 'false')
    doc.body.style.overflow = ''
    doc.removeEventListener('keydown', onKeyDown)
    closeTimer = window.setTimeout(
      () => {
        menu.hidden = true
      },
      reduceMotion ? 0 : 300,
    )
    const restore = lastFocused instanceof HTMLElement ? lastFocused : toggle
    restore.focus()
  }

  toggle?.addEventListener('click', openMenu)
  closeButton?.addEventListener('click', closeMenu)
  menuLinks.forEach((link) => link.addEventListener('click', closeMenu))

  const taglineLines = Array.from(doc.querySelectorAll('[data-tagline]'))
  taglineLines.forEach((line) => {
    const segments = []
    let buffer = ''
    line.childNodes.forEach((node) => {
      // 3 = text node, 1 = element node
      if (node.nodeType === 3) {
        buffer += node.textContent || ''
      } else if (
        node.nodeType === 1 &&
        node.classList &&
        node.classList.contains('tagline-break')
      ) {
        segments.push(buffer)
        buffer = ''
      }
    })
    segments.push(buffer)
    line.textContent = ''
    segments.forEach((segment, index) => {
      if (index > 0) {
        const br = doc.createElement('br')
        br.className = 'tagline-break'
        line.appendChild(br)
      }
      Array.from(segment).forEach((char) => {
        const span = doc.createElement('span')
        span.className = 'tagline-word'
        span.textContent = char === ' ' ? ' ' : char
        line.appendChild(span)
      })
    })
  })

  const taglineWords = Array.from(doc.querySelectorAll('.tagline-word'))
  if (reduceMotion || !('IntersectionObserver' in window)) {
    taglineWords.forEach((word) => word.classList.add('is-lit'))
  } else {
    const taglineObserver = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add('is-lit')
            taglineObserver.unobserve(entry.target)
          }
        })
      },
      { rootMargin: '0px 0px -20% 0px', threshold: 0 },
    )
    taglineWords.forEach((word) => taglineObserver.observe(word))
  }

  const revealTargets = Array.from(doc.querySelectorAll('[data-reveal]'))
  if (reduceMotion || !('IntersectionObserver' in window)) {
    revealTargets.forEach((target) => target.classList.add('is-revealed'))
  } else {
    const revealObserver = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add('is-revealed')
            revealObserver.unobserve(entry.target)
          }
        })
      },
      { threshold: 0.12 },
    )
    revealTargets.forEach((target) => revealObserver.observe(target))
  }

  const navLinks = Array.from(doc.querySelectorAll('.nav-links a[href^="#"]'))
  const sections = navLinks
    .map((link) => doc.querySelector(link.getAttribute('href')))
    .filter(Boolean)
  if (sections.length && 'IntersectionObserver' in window) {
    const navObserver = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return
          navLinks.forEach((link) => link.removeAttribute('aria-current'))
          const active = navLinks.find(
            (link) => link.getAttribute('href') === `#${entry.target.id}`,
          )
          active?.setAttribute('aria-current', 'true')
        })
      },
      { rootMargin: '-40% 0px -50% 0px', threshold: 0 },
    )
    sections.forEach((section) => navObserver.observe(section))
  }
})()
