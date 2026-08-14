import '@testing-library/jest-dom/vitest'
import { afterEach, vi } from 'vitest'
import { cleanup } from '@testing-library/react'

// globals: false 时 RTL 不会自动 cleanup，这里显式注册，避免 DOM 跨用例累积
afterEach(() => {
  cleanup()
})

// antd 组件依赖 matchMedia（jsdom 未实现）
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn()
  })
})

// jsdom 未实现 scrollTo
window.scrollTo = vi.fn() as unknown as typeof window.scrollTo
