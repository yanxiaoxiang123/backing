import { Component, type ErrorInfo, type ReactNode } from 'react'
import { logger } from '../utils/logger'

interface Props {
  children: ReactNode
  /** Optional fallback UI. If omitted, a default error view is rendered. */
  fallback?: ReactNode
  /** Component name for logging. */
  name?: string
}

interface State {
  hasError: boolean
  error: Error | null
}

/**
 * Global error boundary.
 *
 * Catches rendering errors in its subtree and shows a fallback UI instead
 * of a white screen.  Also logs the error stack to the console.
 */
class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    const tag = this.props.name || 'ErrorBoundary'
    logger.error(`[${tag}] ${error.message}`, {
      stack: error.stack,
      componentStack: info.componentStack,
    })
  }

  private handleRetry = (): void => {
    this.setState({ hasError: false, error: null })
  }

  render(): ReactNode {
    if (this.state.hasError) {
      if (this.props.fallback !== undefined) {
        return this.props.fallback
      }

      return (
        <div className="error-boundary">
          <div className="error-boundary-content">
            <div className="error-boundary-icon">⚠</div>
            <h2>页面渲染异常</h2>
            <p className="error-boundary-message">
              {this.state.error?.message || '发生了意外错误'}
            </p>
            <div className="error-boundary-actions">
              <button className="error-boundary-btn" onClick={this.handleRetry}>
                重试
              </button>
              <button
                className="error-boundary-btn error-boundary-btn-secondary"
                onClick={() => window.location.reload()}
              >
                刷新页面
              </button>
            </div>
            {import.meta.env.DEV && this.state.error?.stack && (
              <pre className="error-boundary-stack">{this.state.error.stack}</pre>
            )}
          </div>
        </div>
      )
    }

    return this.props.children
  }
}

export default ErrorBoundary
