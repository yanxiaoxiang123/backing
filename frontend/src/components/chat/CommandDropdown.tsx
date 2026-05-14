// frontend/src/components/chat/CommandDropdown.tsx
import { useState, useEffect, useRef } from 'react'
import type { CommandItem } from '../../types'

interface Props {
  commands: CommandItem[]
  visible: boolean
  filter: string
  onSelect: (command: string) => void
  onClose: () => void
}

export function CommandDropdown({ commands, visible, filter, onSelect, onClose }: Props) {
  const [selectedIndex, setSelectedIndex] = useState(0)
  const ref = useRef<HTMLDivElement>(null)

  const filteredCommands = commands.filter(c =>
    c.command.toLowerCase().includes(filter.toLowerCase())
  )

  useEffect(() => {
    setSelectedIndex(0)
  }, [filter])

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!visible) return

      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setSelectedIndex(i => Math.min(i + 1, filteredCommands.length - 1))
      } else if (e.key === 'ArrowUp') {
        e.preventDefault()
        setSelectedIndex(i => Math.max(i - 1, 0))
      } else if (e.key === 'Enter') {
        e.preventDefault()
        if (filteredCommands[selectedIndex]) {
          onSelect(filteredCommands[selectedIndex].command)
        }
      } else if (e.key === 'Escape') {
        onClose()
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [visible, selectedIndex, filteredCommands, onSelect, onClose])

  if (!visible || filteredCommands.length === 0) return null

  return (
    <div
      ref={ref}
      style={{
        position: 'absolute',
        bottom: '100%',
        left: 0,
        right: 0,
        background: 'var(--color-canvas-lifted)',
        border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-btn)',
        boxShadow: 'var(--shadow-md)',
        maxHeight: '200px',
        overflow: 'auto',
        zIndex: 100
      }}
    >
      {filteredCommands.map((cmd, index) => (
        <div
          key={cmd.command}
          onClick={() => onSelect(cmd.command)}
          style={{
            padding: 'var(--space-sm) var(--space-md)',
            cursor: 'pointer',
            background: index === selectedIndex ? 'var(--color-bg-secondary)' : 'transparent',
            borderBottom: index < filteredCommands.length - 1 ? '1px solid var(--color-border)' : 'none'
          }}
        >
          <div style={{ fontWeight: 500 }}>{cmd.command}</div>
          <div style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-secondary)' }}>
            {cmd.description} — {cmd.example}
          </div>
        </div>
      ))}
    </div>
  )
}