import { splitProseTail } from '../../utils/prose'
import { memo, useEffect, useRef, useState } from 'react'
import ReactMarkdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { Element, ElementContent, Root, Text } from 'hast'

const REVEAL_MS = 140
const STAGGER_MS = 20
const components: Components = {
  table: ({ children }) => (
    <div className="chat-table-scroll">
      <table>{children}</table>
    </div>
  ),
}

type Segmenter = { segment: (text: string) => Iterable<{ segment: string }> }
const SegmenterClass = (
  Intl as typeof Intl & {
    Segmenter?: new (locale: string, options: { granularity: 'grapheme' }) => Segmenter
  }
).Segmenter
const segmenter = SegmenterClass
  ? new SegmenterClass('zh', { granularity: 'grapheme' })
  : null

function graphemes(text: string): string[] {
  return segmenter
    ? Array.from(segmenter.segment(text), (part) => part.segment)
    : Array.from(text)
}

interface ReplyEffects {
  starts: Map<number, number>
  now: number
}

function span(className: string, children: ElementContent[]): Element {
  return {
    type: 'element',
    tagName: 'span',
    properties: { className: [className] },
    children,
  }
}

function decorateText(
  node: Text,
  effects: ReplyEffects,
  keepTail: boolean,
): ElementContent[] {
  const offset = node.position?.start.offset ?? -1
  const render = (text: string, start: number): ElementContent[] => {
    const result: ElementContent[] = []
    let plain = ''
    let cursor = start
    const flush = () => {
      if (plain) result.push({ type: 'text', value: plain })
      plain = ''
    }
    for (const glyph of graphemes(text)) {
      const at = effects.starts.get(offset + cursor)
      if (
        offset >= 0 &&
        at !== undefined &&
        effects.now < at + REVEAL_MS &&
        /\S/u.test(glyph)
      ) {
        flush()
        const letter = span('chat-reveal-glyph', [{ type: 'text', value: glyph }])
        letter.properties.style = `animation-delay:${at - effects.now}ms`
        result.push(letter)
      } else {
        plain += glyph
      }
      cursor += glyph.length
    }
    flush()
    return result
  }
  const renderWords = (text: string, start: number): ElementContent[] => {
    const result: ElementContent[] = []
    let cursor = 0
    // Animated Latin letters keep the same word boundaries as static text.
    for (const match of text.matchAll(/[A-Za-z0-9]+(?:[.,_-][A-Za-z0-9]+)*/g)) {
      const index = match.index!
      result.push(...render(text.slice(cursor, index), start + cursor))
      const word = render(match[0], start + index)
      result.push(
        ...(word.length > 1 && match[0].length <= 32
          ? [span('chat-nowrap-word', word)]
          : word),
      )
      cursor = index + match[0].length
    }
    result.push(...render(text.slice(cursor), start + cursor))
    return result
  }
  const tail = keepTail && node.value.length > 6 ? splitProseTail(node.value)[1] : ''
  if (!tail) return renderWords(node.value, 0)
  const split = node.value.length - tail.length
  return [
    ...renderWords(node.value.slice(0, split), 0),
    span('chat-nowrap-tail', renderWords(tail, split)),
  ]
}

function replyEffectsPlugin(effects: ReplyEffects) {
  return (tree: Root) => {
    const walk = (parent: Element, tail = false) => {
      if (
        parent.type === 'element' &&
        ['pre', 'code', 'script', 'style', 'svg', 'math'].includes(parent.tagName)
      )
        return
      const prose =
        parent.type === 'element' && /^(p|li|h[1-6]|td|th)$/.test(parent.tagName)
      const last = parent.children.length - 1
      parent.children = parent.children.flatMap((child, index) => {
        const keepTail = index === last && (prose || tail)
        if (child.type === 'text') return decorateText(child, effects, keepTail)
        if (child.type === 'element') walk(child, keepTail)
        return [child]
      })
    }
    for (const child of tree.children) {
      if (child.type === 'element') walk(child)
    }
  }
}

/** Only new streamed text is animated. History and already focused text stay still. */
export const StreamingMarkdown = memo(function StreamingMarkdown({
  content,
  streaming,
}: {
  content: string
  streaming: boolean
}) {
  const [, settle] = useState(0)
  const timeline = useRef({
    content,
    streaming,
    nextAt: 0,
    starts: new Map<number, number>(),
  })
  const state = timeline.current
  const now = performance.now()
  if (state.content !== content) {
    if ((streaming || state.streaming) && content.startsWith(state.content)) {
      const added = graphemes(content.slice(state.content.length))
      // Typical chunks use 20ms spacing. Large/fast chunks compress the wave
      // so visual feedback never accumulates seconds behind the actual reply.
      const step = Math.min(STAGGER_MS, 240 / Math.max(1, added.length))
      let at = Math.max(now, Math.min(state.nextAt, now + 96))
      let offset = state.content.length
      for (const glyph of added) {
        state.starts.set(offset, at)
        offset += glyph.length
        at += step
      }
      state.nextAt = at
    } else {
      state.starts.clear()
      state.nextAt = 0
    }
    state.content = content
  }
  state.streaming = streaming
  for (const [offset, at] of state.starts) {
    if (now >= at + REVEAL_MS) state.starts.delete(offset)
  }

  useEffect(() => {
    const at = timeline.current.nextAt
    if (!timeline.current.starts.size) return
    const timer = window.setTimeout(
      () => settle((revision) => revision + 1),
      Math.max(0, at + REVEAL_MS - performance.now()) + 20,
    )
    return () => window.clearTimeout(timer)
  }, [content])

  return (
    <ReactMarkdown
      components={components}
      remarkPlugins={[remarkGfm]}
      rehypePlugins={[[replyEffectsPlugin, { starts: state.starts, now }]]}
    >
      {content}
    </ReactMarkdown>
  )
})
