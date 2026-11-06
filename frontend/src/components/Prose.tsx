import {
  Children,
  cloneElement,
  isValidElement,
  forwardRef,
  type HTMLAttributes,
  type ReactNode,
} from 'react'
import { splitProseTail } from '../utils/prose'

function protectTail(children: ReactNode): ReactNode {
  const nodes = Children.toArray(children)
  let last = nodes.length - 1
  while (last >= 0 && typeof nodes[last] === 'string' && !String(nodes[last]).trim())
    last--
  return nodes.map((node, index) => {
    if (index !== last) return node
    if (typeof node === 'string') {
      const [body, tail] = splitProseTail(node)
      return tail ? (
        <span key="prose-text" style={{ display: 'inline' }}>
          {body}
          <span className="prose-tail" style={{ display: 'inline' }}>
            {tail}
          </span>
        </span>
      ) : (
        node
      )
    }
    // Only descend into ordinary inline markup. Component props and links stay intact.
    if (
      isValidElement<{ children?: ReactNode }>(node) &&
      typeof node.type === 'string' &&
      ['span', 'strong', 'em', 'b', 'small'].includes(node.type)
    )
      return cloneElement(node, { children: protectTail(node.props.children) })
    return node
  })
}

export const Prose = forwardRef<
  HTMLHeadingElement,
  HTMLAttributes<HTMLElement> & {
    as?: 'p' | 'h1' | 'h2' | 'h3' | 'h4' | 'h5' | 'h6'
  }
>(function Prose({ as: Component = 'p', children, ...props }, ref) {
  return (
    <Component ref={ref} {...props}>
      {protectTail(children)}
    </Component>
  )
})
