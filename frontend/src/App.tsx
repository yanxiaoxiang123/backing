import {
  Routes,
  Route,
  Navigate,
  NavLink,
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
} from '@ant-design/icons'
import { Modal } from 'antd'

import ErrorBoundary from './components/ErrorBoundary'
import StockSearch from './components/StockSearch'
import { ResearchCopilot } from './components/research/ResearchCopilot'
const AgentWorkspace = lazy(() => import('./pages/AgentWorkspace'))
const Dashboard = lazy(() => import('./pages/Dashboard'))
const StockList = lazy(() => import('./pages/StockList'))
const StockChart = lazy(() => import('./pages/StockChart'))
const BacktestHistory = lazy(() => import('./pages/BacktestHistory'))
const Strategies = lazy(() => import('./pages/Strategies'))
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

const navItems = [
  { key: '/', label: '仪表盘' },
  { key: '/stocks', label: '股票管理' },
  { key: '/watchlist', label: '自选股' },
  { key: '/screener', label: '股票筛选' },
  { key: '/strategies', label: '策略研究' },
  { key: '/dl-prediction', label: 'DL预测' },
  { key: '/history', label: '回测历史' },
  { key: '/agent', label: '分析报告' },
  { key: '/workspace', label: 'Agent工作台' },
]

function App() {
  const navigate = useNavigate()
  const location = useLocation()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [searchOpen, setSearchOpen] = useState(false)
  const [authState, setAuthState] = useState<AuthState>(getAuthState())
  const toggleRef = useRef<HTMLButtonElement>(null)
  const overlayRef = useRef<HTMLDivElement>(null)

  // 会话探测：无有效 HttpOnly session cookie 时进入未认证状态（跳转登录页）
  useEffect(() => {
    const unsubscribe = onAuthChange(setAuthState)
    void bootstrapAuth()
    return unsubscribe
  }, [])

  // 移动端菜单：Escape 关闭、打开时聚焦关闭按钮、Tab 焦点圈定、关闭后焦点归还
  useEffect(() => {
    if (!mobileMenuOpen) return
    const overlay = overlayRef.current
    const toggle = toggleRef.current
    overlay?.querySelector<HTMLButtonElement>('.nav-mobile-close')?.focus()

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

  const navLinkClass = ({ isActive }: { isActive: boolean }) =>
    `nav-item${isActive ? ' active' : ''}`

  const stockCodeForTitle = location.pathname.match(/^\/stocks\/([^/]+)/)?.[1]
  useEffect(() => {
    const pageTitles: Record<string, string> = {
      '/': '仪表盘',
      '/stocks': '股票管理',
      '/watchlist': '自选股',
      '/screener': '股票筛选',
      '/strategies': '策略研究',
      '/dl-prediction': 'DL 预测',
      '/history': '回测历史',
      '/agent': '分析报告',
      '/workspace': 'Agent 工作台',
      '/login': '登录',
    }
    const pageTitle =
      pageTitles[location.pathname] ?? (stockCodeForTitle ? '个股研究' : '量化系统')
    const detail = stockCodeForTitle ? ` · ${stockCodeForTitle}` : ''
    document.title = `${pageTitle}${detail} · 量化系统`
  }, [location.pathname, stockCodeForTitle])

  // 未认证：只渲染登录页
  if (authState === 'unauthenticated') {
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

  return (
    <div className="app-layout">
      {/* Floating Pill Navigation */}
      <div className="nav-pill-container">
        <nav className="nav-pill" aria-label="主导航">
          <Link to="/" className="nav-logo">
            量化系统
          </Link>

          {/* Desktop Navigation */}
          <div className="nav-links">
            {navItems.map((item) => (
              <NavLink
                key={item.key}
                to={item.key}
                end={item.key === '/'}
                className={navLinkClass}
              >
                {item.label}
              </NavLink>
            ))}
          </div>

          {/* Search Button */}
          <button
            className="nav-search-btn"
            aria-label="搜索股票"
            onClick={() => setSearchOpen(true)}
          >
            <SearchOutlined />
          </button>

          <ResearchCopilot
            context={{
              route: location.pathname,
              entity_type: stockCodeForTitle ? 'stock' : 'page',
              entity_id: stockCodeForTitle,
            }}
          />

          {/* Logout */}
          <button
            className="nav-search-btn"
            aria-label="退出登录"
            title="退出登录"
            onClick={handleLogout}
          >
            <LogoutOutlined />
          </button>

          {/* Mobile Menu Toggle */}
          <button
            ref={toggleRef}
            className="nav-mobile-toggle"
            onClick={() => setMobileMenuOpen(true)}
            aria-label="打开菜单"
            aria-expanded={mobileMenuOpen}
            aria-controls="mobile-nav"
          >
            <MenuOutlined />
          </button>
        </nav>
      </div>

      {/* Mobile Overlay Menu */}
      <div
        ref={overlayRef}
        id="mobile-nav"
        className={`nav-mobile-overlay ${mobileMenuOpen ? 'open' : ''}`}
        role="dialog"
        aria-modal="true"
        aria-label="移动端导航菜单"
      >
        <button
          className="nav-mobile-close"
          onClick={closeMobileMenu}
          aria-label="关闭菜单"
        >
          <CloseOutlined />
        </button>
        {navItems.map((item) => (
          <NavLink
            key={item.key}
            to={item.key}
            end={item.key === '/'}
            className={navLinkClass}
            onClick={closeMobileMenu}
          >
            {item.label}
          </NavLink>
        ))}
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

      {/* Main Content */}
      <main className="app-content">
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
              <Route path="/strategies" element={page('Strategies', <Strategies />)} />
              <Route
                path="/dl-prediction"
                element={page('DLPrediction', <DLPrediction />)}
              />
              <Route path="/backtest" element={<Navigate to="/strategies" replace />} />
              <Route
                path="/history"
                element={page('BacktestHistory', <BacktestHistory />)}
              />
              <Route path="/agent" element={page('AgentAnalysis', <AgentAnalysis />)} />
              <Route
                path="/workspace"
                element={page(
                  'AgentWorkspace',
                  <Suspense fallback={<div className="auth-loading">加载工作台…</div>}>
                    <AgentWorkspace />
                  </Suspense>,
                )}
              />
              <Route path="/login" element={<Navigate to="/" replace />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Suspense>
        </ErrorBoundary>
      </main>
    </div>
  )
}

export default App
