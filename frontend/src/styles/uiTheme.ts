/** Read the CSS loaded in <head>; AntD portals use the same source as page CSS. */
const root = getComputedStyle(document.documentElement)
const token = (name: string, fallback: string) =>
  root.getPropertyValue(`--ui-${name}`).trim() || fallback

export const ui = {
  sidebar: token('sidebar', '#f0f0f0'),
  main: token('main', '#f6f6f6'),
  panel: token('panel', '#fcfcfc'),
  ink: token('ink', '#242424'),
  muted: token('muted', '#6b6b6b'),
  line: token('line', '#e8e8e8'),
  action: token('action', '#222222'),
  brand: token('brand', '#1b6e66'),
  fast: token('fast', '120ms'),
  normal: token('normal', '160ms'),
  overlay: token('overlay', '180ms'),
  ease: token('ease', 'cubic-bezier(0.22, 1, 0.36, 1)'),
}
