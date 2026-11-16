import { useCallback, useLayoutEffect, useRef, type ReactNode } from 'react'
import { NavLink, useLocation } from 'react-router-dom'

interface NavGroup {
  label: string
  items: Array<{ key: string; label: string; icon: ReactNode }>
}

interface ShellNavigationProps {
  groups: NavGroup[]
  onNavigate: () => void
}

export function ShellNavigation({ groups, onNavigate }: ShellNavigationProps) {
  const { pathname } = useLocation()
  const navRef = useRef<HTMLElement>(null)
  const highlightRef = useRef<HTMLSpanElement>(null)
  const hoveredRef = useRef<HTMLAnchorElement | null>(null)
  const focusedRef = useRef<HTMLAnchorElement | null>(null)
  const animationRef = useRef<Animation | null>(null)

  const moveHighlight = useCallback((target: HTMLAnchorElement | null) => {
    const nav = navRef.current
    const highlight = highlightRef.current
    const content = target?.querySelector<HTMLElement>('.shell-nav-content')
    if (!nav || !highlight || !target || !content) return

    const bounds = nav.getBoundingClientRect()
    const row = target.getBoundingClientRect()
    if (!bounds.width || !row.height) return
    const padding = getComputedStyle(target)
    const width = nav.closest('.shell--research')
      ? row.width
      : Math.min(
          row.width,
          content.getBoundingClientRect().width +
            parseFloat(padding.paddingLeft) +
            parseFloat(padding.paddingRight),
        )
    const x = row.left - bounds.left + nav.scrollLeft
    const y = row.top - bounds.top + nav.scrollTop
    const transform = `translate3d(${x}px, ${y}px, 0)`
    const ready = nav.dataset.highlightReady === 'true'
    // Read the displayed box before cancelling: fast pointer moves continue
    // from the current frame instead of jumping back to the previous target.
    const previous = highlight.getBoundingClientRect()
    if (
      ready &&
      Math.abs(previous.left - row.left) < 0.1 &&
      Math.abs(previous.top - row.top) < 0.1 &&
      Math.abs(previous.width - width) < 0.1 &&
      Math.abs(previous.height - row.height) < 0.1
    )
      return
    animationRef.current?.cancel()
    highlight.style.width = `${width}px`
    highlight.style.height = `${row.height}px`
    highlight.style.transform = transform
    nav.dataset.highlightReady = 'true'

    if (
      ready &&
      previous.width &&
      !window.matchMedia('(prefers-reduced-motion: reduce)').matches
    ) {
      // FLIP scales only the separate background. The links, glyphs and hit
      // areas stay in normal flow at a constant size, weight and position.
      animationRef.current = highlight.animate(
        [
          {
            transform: `translate3d(${previous.left - bounds.left + nav.scrollLeft}px, ${previous.top - bounds.top + nav.scrollTop}px, 0) scale(${previous.width / width}, ${previous.height / row.height})`,
          },
          { transform },
        ],
        { duration: 140, easing: 'cubic-bezier(0.22, 1, 0.36, 1)' },
      )
    }
  }, [])

  const restoreHighlight = useCallback(() => {
    moveHighlight(
      hoveredRef.current ??
        focusedRef.current ??
        navRef.current?.querySelector<HTMLAnchorElement>('[aria-current="page"]') ??
        null,
    )
  }, [moveHighlight])

  useLayoutEffect(() => {
    hoveredRef.current = null
    focusedRef.current = null
    restoreHighlight()
  }, [pathname, restoreHighlight])

  useLayoutEffect(() => {
    const nav = navRef.current
    if (!nav) return
    let frame = 0
    let disposed = false
    const schedule = () => {
      cancelAnimationFrame(frame)
      frame = requestAnimationFrame(restoreHighlight)
    }
    const observer = new ResizeObserver(schedule)
    const motion = window.matchMedia('(prefers-reduced-motion: reduce)')
    const settle = () => {
      if (motion.matches) animationRef.current?.cancel()
    }
    observer.observe(nav)
    nav.querySelectorAll('.shell-nav-content').forEach((item) => observer.observe(item))
    window.addEventListener('resize', schedule)
    motion.addEventListener('change', settle)
    void document.fonts.ready.then(() => {
      if (!disposed) schedule()
    })
    return () => {
      disposed = true
      cancelAnimationFrame(frame)
      observer.disconnect()
      window.removeEventListener('resize', schedule)
      motion.removeEventListener('change', settle)
      animationRef.current?.cancel()
    }
  }, [restoreHighlight])

  return (
    <nav
      ref={navRef}
      className="shell-nav"
      aria-label="主导航"
      onPointerOver={(event) => {
        if (event.pointerType === 'touch') return
        const target = (event.target as HTMLElement).closest<HTMLAnchorElement>(
          '.shell-nav-item',
        )
        if (target && target !== hoveredRef.current) {
          hoveredRef.current = target
          moveHighlight(target)
        }
      }}
      onPointerLeave={() => {
        hoveredRef.current = null
        restoreHighlight()
      }}
      onFocusCapture={(event) => {
        focusedRef.current = event.target.closest<HTMLAnchorElement>('.shell-nav-item')
        hoveredRef.current = null
        restoreHighlight()
      }}
      onBlurCapture={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) {
          focusedRef.current = null
          restoreHighlight()
        }
      }}
    >
      <span ref={highlightRef} className="shell-nav-highlight" aria-hidden="true" />
      {groups.map((group) => (
        <div className="shell-nav-group" key={group.label}>
          <div className="shell-nav-label">{group.label}</div>
          {group.items.map((item) => (
            <NavLink
              key={item.key}
              to={item.key}
              end={item.key === '/'}
              className={({ isActive }) => `shell-nav-item${isActive ? ' active' : ''}`}
              onClick={onNavigate}
            >
              <span className="shell-nav-content">
                <span className="shell-nav-icon" aria-hidden="true">
                  {item.icon}
                </span>
                <span>{item.label}</span>
              </span>
            </NavLink>
          ))}
        </div>
      ))}
    </nav>
  )
}
