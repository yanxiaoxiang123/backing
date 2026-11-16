const reduce = window.matchMedia('(prefers-reduced-motion: reduce)')
const desktop = window.matchMedia('(min-width: 801px)')

function initHero() {
  if (!reduce.matches) document.documentElement.classList.add('hero-entered')
}

function initCinema() {
  const section = document.querySelector('.cinematic-section')
  const stage = document.querySelector('.cinema-stage')
  if (!section || !stage) return
  const panels = Array.from(stage.querySelectorAll('[data-scene]'))
  const steps = Array.from(section.querySelectorAll('[data-scene-trigger]'))
  const progress = Array.from(stage.querySelectorAll('.scene-progress span'))
  const wrapper = document.createElement('div')
  wrapper.className = 'cinema-panels'
  stage.insertBefore(wrapper, panels[0])
  panels.forEach((panel) => wrapper.appendChild(panel))
  let observer = null
  let inView = false
  const active = (key) => {
    panels.forEach((panel) => {
      const current = panel.dataset.scene === key
      panel.classList.toggle('is-active', current)
      panel.inert = desktop.matches && !reduce.matches && !current
    })
    steps.forEach((step, i) => {
      const current = step.dataset.sceneTrigger === key
      step.classList.toggle('is-active', current)
      progress[i]?.classList.toggle('is-active', current)
    })
    stage.dataset.activeScene = key
  }
  const setup = () => {
    observer?.disconnect()
    section.classList.toggle('cinema-ready', desktop.matches && !reduce.matches)
    if (!desktop.matches || reduce.matches) {
      panels.forEach((panel) => {
        panel.inert = false
        panel.classList.add('is-active')
      })
      return
    }
    active('market')
    observer = new IntersectionObserver(
      (entries) => {
        const candidates = entries.filter((entry) => entry.isIntersecting)
        if (candidates.length)
          active(
            candidates.sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0]
              .target.dataset.sceneTrigger,
          )
      },
      { rootMargin: '-20% 0px -35% 0px', threshold: [0, 0.1, 0.3, 0.5] },
    )
    steps.forEach((step) => observer.observe(step))
  }
  if ('IntersectionObserver' in window) {
    const pause = () =>
      section.classList.toggle('cinema-paused', !inView || document.hidden)
    const visibility = new IntersectionObserver(
      (entries) => {
        inView = entries.some((entry) => entry.isIntersecting)
        pause()
      },
      { threshold: 0 },
    )
    visibility.observe(section)
    document.addEventListener('visibilitychange', pause)
    desktop.addEventListener('change', setup)
    reduce.addEventListener('change', setup)
    setup()
  }
}

function initRows() {
  if (reduce.matches || !('IntersectionObserver' in window)) return
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return
        entry.target.classList.add('row-entered')
        observer.unobserve(entry.target)
      })
    },
    { threshold: 0.08 },
  )
  document.querySelectorAll('[data-strategy]').forEach((row) => {
    observer.observe(row)
    row.classList.add('motion-row')
  })
}
function initCharacterHover() {
  const selectors =
    '.hero-copy h1, .section-heading h2, .feature-notes h3, .trust-notes h3, .strategy-group-heading h3, .strategy-list h4, .scene-steps h3, .scene-intro h3, .faq-section h2, .final-cta h2'
  const segmenter =
    typeof Intl.Segmenter === 'function'
      ? new Intl.Segmenter('zh-CN', { granularity: 'grapheme' })
      : null
  document.querySelectorAll(selectors).forEach((heading) => {
    heading.setAttribute('aria-label', heading.textContent.replace(/\s+/g, ' ').trim())
    const walker = document.createTreeWalker(heading, window.NodeFilter.SHOW_TEXT)
    const nodes = []
    while (walker.nextNode()) nodes.push(walker.currentNode)
    nodes.forEach((node) => {
      const fragment = document.createDocumentFragment()
      const segments = segmenter
        ? Array.from(segmenter.segment(node.textContent), (item) => item.segment)
        : Array.from(node.textContent)
      segments.forEach((character) => {
        if (/\s/.test(character)) {
          fragment.appendChild(document.createTextNode(character))
          return
        }
        const span = document.createElement('span')
        span.className = 'hover-char'
        span.dataset.character = character
        span.textContent = character
        span.setAttribute('aria-hidden', 'true')
        fragment.appendChild(span)
      })
      node.replaceWith(fragment)
    })
    heading.classList.add('character-hover-ready')
    const characters = Array.from(heading.querySelectorAll('.hover-char'))
    const finePointer = window.matchMedia('(hover: hover)')
    let activeCharacter = null
    const illuminate = (target) => {
      if (target === activeCharacter) return
      activeCharacter = target
      const center = characters.indexOf(target)
      const targetRect = target?.getBoundingClientRect()
      characters.forEach((character, index) => {
        const distance = Math.abs(index - center)
        const rect = character.getBoundingClientRect()
        const sameLine =
          targetRect && Math.abs(rect.top - targetRect.top) < targetRect.height / 2
        const strength =
          center >= 0 && sameLine && distance <= 2 ? [1, 0.62, 0.28][distance] : 0
        character.style.setProperty('--char-strength', String(strength))
        character.style.setProperty(
          '--char-delay',
          strength ? `${Math.max(0, index - center + 2) * 20}ms` : '0ms',
        )
        character.classList.toggle('char-lit', strength > 0)
      })
    }
    heading.addEventListener('pointerover', (event) => {
      if (!finePointer.matches) return
      illuminate(event.target.closest('.hover-char'))
    })
    heading.addEventListener('pointerleave', () => illuminate(null))
  })
}
initCharacterHover()
initHero()
initCinema()
initRows()
