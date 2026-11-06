import {
  Routes,
  Route,
  Navigate,
  Link,
  useLocation,
  useNavigate,
} from 'react-router-dom'
import { lazy, Suspense, useEffect, useRef, useState, type ReactNode } from 'react'
import {
  SearchOutlined,
  MenuOutlined,
  CloseOutlined,
  LogoutOutlined,
  DashboardOutlined,
  StockOutlined,
  StarOutlined,
  FilterOutlined,
  ExperimentOutlined,
  LineChartOutlined,
  HistoryOutlined,
  FileTextOutlined,
  RobotOutlined,
  SettingOutlined,
} from '@ant-design/icons'
import { ConfigProvider, Modal, message } from 'antd'

import ErrorBoundary from './components/ErrorBoundary'
import StockSearch from './components/StockSearch'
import AiSettingsModal from './components/settings/AiSettingsModal'
import { ShellNavigation } from './components/ShellNavigation'
import { ResearchCopilot } from './components/research/ResearchCopilot'
import { useSystemStatus } from './hooks/useSystemStatus'
const AgentWorkspace = lazy(() => import('./pages/AgentWorkspace'))
const Dashboard = lazy(() => import('./pages/Dashboard'))
const StockList = lazy(() => import('./pages/StockList'))
const StockChart = lazy(() => import('./pages/StockChart'))
const BacktestHistory = lazy(() => import('./pages/BacktestHistory'))
const Strategies = lazy(() => import('./pages/Strategies'))
const PortfolioResearch = lazy(() => import('./pages/PortfolioResearch'))
const AgentAnalysis = lazy(() => import('./pages/AgentAnalysis'))
const DLPrediction = lazy(() => import('./pages/DLPrediction'))
const Watchlist = lazy(() => import('./pages/Watchlist'))
const Login = lazy(() => import('./pages/Login'))
const Screener = lazy(() => import('./pages/Screener'))
import {
  bootstrapAuth,
  getAuthState,
  logout,
  onAuthChange,
  type AuthState,
} from './services/api'
import { safeNextPath } from './utils/nextPath'
import { researchTheme } from './styles/researchTheme'

interface NavItem {
  key: string
  label: string
  icon: ReactNode
}

const navGroups: Array<{ label: string; items: NavItem[] }> = [
  {
    label: '研究',
    items: [
      { key: '/', label: '仪表盘', icon: <DashboardOutlined /> },
      { key: '/stocks', label: '股票管理', icon: <StockOutlined /> },
      { key: '/watchlist', label: '自选股', icon: <StarOutlined /> },
      { key: '/screener', label: '股票筛选', icon: <FilterOutlined /> },
    ],
  },
  {
    label: '策略',
    items: [
      { key: '/strategies', label: '策略研究', icon: <ExperimentOutlined /> },
      { key: '/portfolio', label: '组合研究', icon: <ExperimentOutlined /> },
      { key: '/dl-prediction', label: 'DL 预测', icon: <LineChartOutlined /> },
      { key: '/history', label: '回测历史', icon: <HistoryOutlined /> },
    ],
  },
  {
    label: 'AI',
    items: [
      { key: '/agent', label: '分析报告', icon: <FileTextOutlined /> },
      { key: '/workspace', label: 'Agent 工作台', icon: <RobotOutlined /> },
    ],
  },
]

const pageTitles: Record<string, string> = {
  '/': '仪表盘',
  '/stocks': '股票管理',
  '/watchlist': '自选股',
  '/screener': '股票筛选',
  '/strategies': '策略研究',
  '/portfolio': '组合研究',
  '/dl-prediction': 'DL 预测',
  '/history': '回测历史',
  '/agent': '分析报告',
  '/workspace': 'Agent 工作台',
  '/login': '登录',
}

function getPageTitle(pathname: string, stockCode?: string): string {
  return pageTitles[pathname] ?? (stockCode ? '个股研究' : '量化系统')
}

function BrandMark() {
  return (
    <svg
      className="shell-mark"
      viewBox="0 0 24 24"
      aria-hidden="true"
      focusable="false"
    >
      <rect
        x="3"
        y="11"
        width="3.5"
        height="9"
        rx="1"
        fill="currentColor"
        opacity=".4"
      />
      <rect x="10.25" y="6" width="3.5" height="14" rx="1" fill="currentColor" />
      <rect
        x="17.5"
        y="9"
        width="3.5"
        height="11"
        rx="1"
        fill="currentColor"
        opacity=".7"
      />
      <path
        d="M3 8.5 10.5 5 18 7.5 21 4"
        stroke="currentColor"
        strokeWidth="1.5"
        fill="none"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function RedirectTo({ to }: { to: string }) {
  useEffect(() => {
    window.location.replace(to)
  }, [to])

  return (
    <div className="route-loading" role="status" aria-live="polite">
      正在加载…
    </div>
  )
}

function LoginRedirect() {
  const location = useLocation()
  const params = new URLSearchParams(location.search)
  const next =
    safeNextPath(params.get('next')) ||
    safeNextPath((location.state as { from?: string } | null)?.from ?? null) ||
    '/'
  return <Navigate to={next} replace />
}

function App() {
  const navigate = useNavigate()
  const location = useLocation()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [searchOpen, setSearchOpen] = useState(false)
  const [copilotOpen, setCopilotOpen] = useState(false)
  const [aiSettingsOpen, setAiSettingsOpen] = useState(false)
  const [authState, setAuthState] = useState<AuthState>(getAuthState())
  const toggleRef = useRef<HTMLButtonElement>(null)
  const overlayRef = useRef<HTMLDivElement>(null)
  const system = useSystemStatus({ enabled: authState === 'authenticated' })

  // 监听全局 app:toast 自定义事件，统一转由 UI 层（AntD message）呈现
  useEffect(() => {
    const handleToast = (e: Event) => {
      const customEvent = e as CustomEvent<{
        content: string
        type: 'info' | 'success' | 'warning' | 'error'
        duration?: number
      }>
      if (!customEvent.detail) return
      customEvent.preventDefault()
      const { content, type, duration } = customEvent.detail
      const dur = duration !== undefined ? duration / 1000 : undefined
      message[type](content, dur)
    }

    window.addEventListener('app:toast', handleToast)
    const unsubscribe = onAuthChange(setAuthState)
    void bootstrapAuth()
    return () => {
      window.removeEventListener('app:toast', handleToast)
      unsubscribe()
    }
  }, [])

  // 移动端菜单：Escape 关闭、打开时聚焦关闭按钮、Tab 焦点圈定、关闭后焦点归还
  useEffect(() => {
    if (!mobileMenuOpen) return
    const overlay = overlayRef.current
    const toggle = toggleRef.current
    overlay?.querySelector<HTMLButtonElement>('.shell-mobile-close')?.focus()

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setMobileMenuOpen(false)
        return
      }
      if (e.key !== 'Tab' || !overlay) return
      const focusables = Array.from(
        overlay.querySelectorAll<HTMLElement>('a[href], button:not([disabled])'),
      )
      if (focusables.length === 0) return
      const first = focusables[0]
      const last = focusables[focusables.length - 1]
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault()
        last.focus()
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault()
        first.focus()
      }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      toggle?.focus()
    }
  }, [mobileMenuOpen])

  const handleStockSelect = (code: string) => {
    setSearchOpen(false)
    navigate(`/stocks/${code}`)
  }

  const stockCodeForTitle = location.pathname.match(/^\/stocks\/([^/]+)/)?.[1]

  useEffect(() => {
    const pageTitle = getPageTitle(location.pathname, stockCodeForTitle)
    const detail = stockCodeForTitle ? ` · ${stockCodeForTitle}` : ''
    document.title = `${pageTitle}${detail} · 量化系统`
  }, [location.pathname, stockCodeForTitle])

  if (location.pathname === '/welcome') {
    return <RedirectTo to={`/welcome/${location.search}`} />
  }

  // 未认证：只渲染登录页
  if (authState === 'unauthenticated') {
    const isLogin = location.pathname === '/login'
    const isWelcome = location.pathname === '/welcome/'

    if (!isLogin && !isWelcome) {
      const next = `${location.pathname}${location.search}`
      return <RedirectTo to={`/welcome/?next=${encodeURIComponent(next)}`} />
    }

    return (
      <Suspense fallback={<div className="route-loading">加载登录页…</div>}>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </Suspense>
    )
  }

  // 探测中：避免闪现登录页
  if (authState === 'unknown') {
    return <div className="auth-loading">加载中…</div>
  }

  const handleLogout = async () => {
    await logout()
    navigate('/login', { replace: true })
  }

  const closeMobileMenu = () => setMobileMenuOpen(false)

  const page = (name: string, element: ReactNode) => (
    <ErrorBoundary name={name}>{element}</ErrorBoundary>
  )

  const tasksValue = system.isLoading || system.metricsError ? '—' : system.completed
  const failedCount =
    !system.isLoading && !system.metricsError && system.failed ? system.failed : 0
  const alertsValue = system.isLoading || system.alertsError ? '—' : system.unreadAlerts

  const brand = (
    <Link to="/" className="shell-brand" onClick={closeMobileMenu}>
      <BrandMark />
      <span className="shell-brand-text">
        <span className="shell-brand-name">量化系统</span>
        <span className="shell-brand-scope">A股研究 · 个人</span>
      </span>
    </Link>
  )

  const nav = <ShellNavigation groups={navGroups} onNavigate={closeMobileMenu} />

  const statusBlock = (
    <div className="shell-status">
      <Link to="/workspace" className="shell-status-row" onClick={closeMobileMenu}>
        <span
          className={`shell-status-dot ${
            failedCount ? 'is-bad' : system.completed ? 'is-good' : ''
          }`}
        />
        <span>
          本次运行 <strong>{tasksValue}</strong> 完成
          {failedCount ? (
            <>
              {' '}
              · <strong className="is-bad">{failedCount}</strong> 失败
            </>
          ) : null}
        </span>
      </Link>
      <Link to="/workspace" className="shell-status-row" onClick={closeMobileMenu}>
        <span className={`shell-status-dot ${system.unreadAlerts ? 'is-warn' : ''}`} />
        <span>
          告警 <strong>{alertsValue}</strong> 未读
        </span>
      </Link>
    </div>
  )

  const aiSettingsButton = (
    <button
      type="button"
      className="shell-nav-item"
      onClick={() => {
        closeMobileMenu()
        setAiSettingsOpen(true)
      }}
    >
      <SettingOutlined />
      <span>AI 服务配置</span>
    </button>
  )

  const userBlock = (
    <div className="shell-user">
      <span>个人工作台</span>
      <button
        type="button"
        onClick={() => void handleLogout()}
        aria-label="退出登录"
        title="退出登录"
      >
        <LogoutOutlined />
      </button>
    </div>
  )

  const isResearchPage =
    navGroups
      .slice(0, 2)
      .some((group) => group.items.some((item) => item.key === location.pathname)) ||
    location.pathname.startsWith('/stocks/') ||
    location.pathname === '/backtest'

  return (
    <ConfigProvider
      theme={isResearchPage ? researchTheme : undefined}
      select={{
        classNames: { popup: { root: isResearchPage ? 'research-theme-overlay' : '' } },
      }}
      modal={{
        classNames: { content: isResearchPage ? 'research-theme-overlay' : '' },
      }}
    >
      <div
        className={`shell${isResearchPage ? ' shell--research' : ''}${location.pathname === '/' ? ' shell--dashboard' : ''}${location.pathname === '/stocks' ? ' shell--stocks' : ''}${location.pathname === '/dl-prediction' ? ' shell--dl' : ''}`}
      >
        <aside className="shell-sidebar" aria-label="侧栏">
          {brand}
          <button
            type="button"
            className="shell-search"
            onClick={() => setSearchOpen(true)}
          >
            <SearchOutlined />
            <span>搜索股票</span>
          </button>
          {nav}
          <div className="shell-sidebar-bottom">
            {statusBlock}
            <button
              type="button"
              className="shell-nav-item shell-copilot-btn"
              onClick={() => setCopilotOpen(true)}
            >
              <RobotOutlined />
              <span>AI 副驾驶</span>
            </button>
            {aiSettingsButton}
            {userBlock}
          </div>
        </aside>

        <div className="shell-main">
          <div className="shell-mobilebar">
            <button
              ref={toggleRef}
              type="button"
              className="shell-icon-btn"
              onClick={() => setMobileMenuOpen(true)}
              aria-label="打开菜单"
              aria-expanded={mobileMenuOpen}
              aria-controls="mobile-nav"
            >
              <MenuOutlined />
            </button>
            <span className="shell-mobile-title">
              {getPageTitle(location.pathname, stockCodeForTitle)}
            </span>
            <button
              type="button"
              className="shell-icon-btn"
              onClick={() => setSearchOpen(true)}
              aria-label="搜索股票"
            >
              <SearchOutlined />
            </button>
          </div>

          <main
            className={`shell-canvas${location.pathname === '/workspace' ? ' shell-canvas--workspace' : ''}`}
          >
            <ErrorBoundary name="App">
              <Suspense
                fallback={
                  <div className="route-loading" role="status" aria-live="polite">
                    加载页面…
                  </div>
                }
              >
                <Routes>
                  <Route path="/" element={page('Dashboard', <Dashboard />)} />
                  <Route path="/stocks" element={page('StockList', <StockList />)} />
                  <Route
                    path="/stocks/:code"
                    element={page('StockChart', <StockChart />)}
                  />
                  <Route path="/watchlist" element={page('Watchlist', <Watchlist />)} />
                  <Route path="/screener" element={page('Screener', <Screener />)} />
                  <Route
                    path="/strategies"
                    element={page('Strategies', <Strategies />)}
                  />
                  <Route
                    path="/dl-prediction"
                    element={page('DLPrediction', <DLPrediction />)}
                  />
                  <Route
                    path="/portfolio"
                    element={page('PortfolioResearch', <PortfolioResearch />)}
                  />
                  <Route
                    path="/backtest"
                    element={<Navigate to="/strategies" replace />}
                  />
                  <Route
                    path="/history"
                    element={page('BacktestHistory', <BacktestHistory />)}
                  />
                  <Route
                    path="/agent"
                    element={page('AgentAnalysis', <AgentAnalysis />)}
                  />
                  <Route
                    path="/workspace"
                    element={page(
                      'AgentWorkspace',
                      <Suspense
                        fallback={<div className="auth-loading">加载工作台…</div>}
                      >
                        <AgentWorkspace />
                      </Suspense>,
                    )}
                  />
                  <Route path="/login" element={<LoginRedirect />} />
                  <Route path="*" element={<Navigate to="/" replace />} />
                </Routes>
              </Suspense>
            </ErrorBoundary>
          </main>
        </div>
      </div>

      {/* Mobile sheet */}
      <div
        ref={overlayRef}
        id="mobile-nav"
        className={`shell-sheet ${mobileMenuOpen ? 'open' : ''}`}
        role="dialog"
        aria-modal="true"
        aria-label="导航菜单"
      >
        <div className="shell-sheet-head">
          {brand}
          <button
            type="button"
            className="shell-icon-btn shell-mobile-close"
            onClick={closeMobileMenu}
            aria-label="关闭菜单"
          >
            <CloseOutlined />
          </button>
        </div>
        <button
          type="button"
          className="shell-search"
          onClick={() => {
            setSearchOpen(true)
            closeMobileMenu()
          }}
        >
          <SearchOutlined />
          <span>搜索股票</span>
        </button>
        {nav}
        <div className="shell-sidebar-bottom">
          {statusBlock}
          <button
            type="button"
            className="shell-nav-item shell-copilot-btn"
            onClick={() => {
              setCopilotOpen(true)
              closeMobileMenu()
            }}
          >
            <RobotOutlined />
            <span>AI 副驾驶</span>
          </button>
          {aiSettingsButton}
          <div className="shell-user">
            <span>个人工作台</span>
            <button
              type="button"
              onClick={() => {
                closeMobileMenu()
                void handleLogout()
              }}
              aria-label="退出登录"
              title="退出登录"
            >
              <LogoutOutlined />
            </button>
          </div>
        </div>
      </div>

      {/* Global Stock Search */}
      <Modal
        open={searchOpen}
        onCancel={() => setSearchOpen(false)}
        title="搜索股票"
        footer={null}
        width={480}
        destroyOnHidden
      >
        <StockSearch
          autoFocus
          placeholder="输入股票代码或名称"
          onChange={(code) => handleStockSelect(code)}
        />
      </Modal>

      <AiSettingsModal open={aiSettingsOpen} onClose={() => setAiSettingsOpen(false)} />

      <ResearchCopilot
        hideTrigger
        open={copilotOpen}
        onOpenChange={setCopilotOpen}
        context={{
          route: location.pathname,
          entity_type: stockCodeForTitle ? 'stock' : 'page',
          entity_id: stockCodeForTitle,
        }}
      />
    </ConfigProvider>
  )
}

export default App
