/**
 * 轻量级全局 Toast 提示工具，用于解耦底层网络拦截器与重量级 UI 库（如 AntD message）。
 * 避免在核心数据服务层（api.ts）中强引用 UI 依赖导致主 bundle / vendor 体积膨胀。
 */

export type ToastType = 'info' | 'success' | 'warning' | 'error'

export type ToastHandler = (content: string, type: ToastType, duration?: number) => void

let customHandler: ToastHandler | null = null

/**
 * 注册自定义 Toast 处理器（如由前端顶层组件委托给 UI 库）
 */
export function setToastHandler(handler: ToastHandler | null): void {
  customHandler = handler
}

/**
 * 原生 DOM 轻量兜底 Toast
 */
function renderDomToast(content: string, type: ToastType, duration = 3000): void {
  if (typeof document === 'undefined') return

  const containerId = '__app_lightweight_toast_container'
  let container = document.getElementById(containerId)
  if (!container) {
    container = document.createElement('div')
    container.id = containerId
    container.setAttribute('aria-live', 'polite')
    container.style.cssText = [
      'position: fixed',
      'top: 24px',
      'left: 50%',
      'transform: translateX(-50%)',
      'z-index: 10000',
      'display: flex',
      'flex-direction: column',
      'align-items: center',
      'gap: 10px',
      'pointer-events: none',
    ].join(';')
    document.body.appendChild(container)
  }

  const toastItem = document.createElement('div')
  toastItem.style.cssText = [
    'padding: 9px 16px',
    'border-radius: 8px',
    'font-size: 14px',
    'line-height: 1.5',
    'box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15)',
    'pointer-events: auto',
    'transition: opacity 0.25s ease, transform 0.25s ease',
    'opacity: 0',
    'transform: translateY(-8px)',
    'max-width: 480px',
    'word-break: break-word',
    'color: #ffffff',
  ].join(';')

  switch (type) {
    case 'error':
      toastItem.style.backgroundColor = '#cf1322'
      break
    case 'success':
      toastItem.style.backgroundColor = '#389e0d'
      break
    case 'warning':
      toastItem.style.backgroundColor = '#d46b08'
      break
    default:
      toastItem.style.backgroundColor = '#1677ff'
      break
  }

  toastItem.textContent = content
  container.appendChild(toastItem)

  // 触发渐入动画
  requestAnimationFrame(() => {
    toastItem.style.opacity = '1'
    toastItem.style.transform = 'translateY(0)'
  })

  // 延时淡出并移除
  setTimeout(() => {
    toastItem.style.opacity = '0'
    toastItem.style.transform = 'translateY(-8px)'
    setTimeout(() => {
      toastItem.remove()
      if (container && container.childNodes.length === 0) {
        container.remove()
      }
    }, 260)
  }, duration)
}

function dispatchToast(content: string, type: ToastType, duration?: number): void {
  let handled = false

  if (typeof window !== 'undefined' && typeof window.dispatchEvent === 'function') {
    const event = new CustomEvent('app:toast', {
      detail: { content, type, duration },
      cancelable: true,
    })
    const notCancelled = window.dispatchEvent(event)
    if (!notCancelled) {
      handled = true
    }
  }

  if (customHandler) {
    customHandler(content, type, duration)
    handled = true
  }

  if (!handled) {
    renderDomToast(content, type, duration)
  }
}

export const toast = {
  info(content: string, duration?: number): void {
    dispatchToast(content, 'info', duration)
  },
  success(content: string, duration?: number): void {
    dispatchToast(content, 'success', duration)
  },
  warning(content: string, duration?: number): void {
    dispatchToast(content, 'warning', duration)
  },
  error(content: string, duration?: number): void {
    dispatchToast(content, 'error', duration)
  },
}
