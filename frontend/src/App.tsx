import { Routes, Route, Navigate, NavLink, Link, useNavigate } from 'react-router-dom'
import { useEffect, useRef, useState } from 'react'
import { SearchOutlined, MenuOutlined, CloseOutlined } from '@ant-design/icons'
import { Modal } from 'antd'

import Dashboard from './pages/Dashboard'
import StockList from './pages/StockList'
import StockChart from './pages/StockChart'
import Backtest from './pages/Backtest'
import BacktestHistory from './pages/BacktestHistory'
import Strategies from './pages/Strategies'
import AgentAnalysis from './pages/AgentAnalysis'
import DLPrediction from './pages/DLPrediction'
import Watchlist from './pages/Watchlist'
import ErrorBoundary from './components/ErrorBoundary'
import StockSearch from './components/StockSearch'
import { initSession } from './services/api'
import Screener from './pages/Screener'

const navItems = [
  { key: '/', label: '仪表盘' },
  { key: '/stocks', label: '股票管理' },
  { key: '/watchlist', label: '自选股' },
  { key: '/screener', label: '股票筛选' },
  { key: '/strategies', label: '策略研究' },
  { key: '/dl-prediction', label: 'DL预测' },
  { key: '/backtest', label: '回测执行' },
  { key: '/history', label: '回测历史' },
  { key: '/agent', label: 'AI分析' }
]

function App() {
  const navigate = useNavigate()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [searchOpen, setSearchOpen] = useState(false)
  const toggleRef = useRef<HTMLButtonElement>(null)
  const overlayRef = useRef<HTMLDivElement>(null)

  // 初始化 session cookie（用 API key 换一次 cookie，避免 key 暴露在 bundle 中）
  useEffect(() => { initSession() }, [])

  const closeMobileMenu = () => setMobileMenuOpen(false)

  // 移动端菜单：Escape 关闭、打开时聚焦关闭按钮、Tab 焦点圈定、关闭后焦点归还
  useEffect(() => {
    if (!mobileMenuOpen) return
    const overlay = overlayRef.current
    overlay?.querySelector<HTMLButtonElement>('.nav-mobile-close')?.focus()

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setMobileMenuOpen(false)
        return
      }
      if (e.key !== 'Tab' || !overlay) return
      const focusables = Array.from(
        overlay.querySelectorAll<HTMLElement>('a[href], button:not([disabled])')
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
      toggleRef.current?.focus()
    }
  }, [mobileMenuOpen])

  const handleStockSelect = (code: string) => {
    setSearchOpen(false)
    navigate(`/stocks/${code}`)
  }

  const navLinkClass = ({ isActive }: { isActive: boolean }) =>
    `nav-item${isActive ? ' active' : ''}`

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
            {navItems.map(item => (
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
        {navItems.map(item => (
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
        destroyOnClose
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
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/stocks" element={<StockList />} />
            <Route path="/stocks/:code" element={<StockChart />} />
            <Route path="/watchlist" element={<Watchlist />} />
            <Route path="/screener" element={<Screener />} />
            <Route path="/strategies" element={<Strategies />} />
            <Route path="/dl-prediction" element={<DLPrediction />} />
            <Route path="/backtest" element={<Backtest />} />
            <Route path="/history" element={<BacktestHistory />} />
            <Route path="/agent" element={<AgentAnalysis />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </ErrorBoundary>
      </main>
    </div>
  )
}

export default App
