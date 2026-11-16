import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { toast, setToastHandler } from './toast'

describe('toast utility', () => {
  beforeEach(() => {
    setToastHandler(null)
    document.body.innerHTML = ''
    vi.useFakeTimers()
  })

  afterEach(() => {
    setToastHandler(null)
    document.body.innerHTML = ''
    vi.useRealTimers()
  })

  it('renders a DOM toast when no custom handler is registered', () => {
    toast.error('网络连接失败')

    const container = document.getElementById('__app_lightweight_toast_container')
    expect(container).not.toBeNull()
    expect(container?.textContent).toContain('网络连接失败')

    vi.advanceTimersByTime(3500)
    expect(document.getElementById('__app_lightweight_toast_container')).toBeNull()
  })

  it('delegates to customHandler when registered', () => {
    const handler = vi.fn()
    setToastHandler(handler)

    toast.success('操作成功', 2000)
    expect(handler).toHaveBeenCalledWith('操作成功', 'success', 2000)
    expect(document.getElementById('__app_lightweight_toast_container')).toBeNull()
  })

  it('dispatches app:toast CustomEvent and avoids DOM toast when event is cancelled', () => {
    const listener = vi.fn((e: Event) => {
      e.preventDefault()
    })
    window.addEventListener('app:toast', listener)

    toast.warning('请注意风险', 1500)
    expect(listener).toHaveBeenCalled()
    expect(document.getElementById('__app_lightweight_toast_container')).toBeNull()

    window.removeEventListener('app:toast', listener)
  })
})
