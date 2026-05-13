import { Routes, Route, Navigate, useNavigate, useLocation } from 'react-router-dom'
import { useState } from 'react'
import { SearchOutlined, MenuOutlined, CloseOutlined } from '@ant-design/icons'

import Dashboard from './pages/Dashboard'
import StockList from './pages/StockList'
import StockChart from './pages/StockChart'
import Backtest from './pages/Backtest'
import BacktestHistory from './pages/BacktestHistory'
import Strategies from './pages/Strategies'
import AgentAnalysis from './pages/AgentAnalysis'
import DLPrediction from './pages/DLPrediction'
import Watchlist from './pages/Watchlist'
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
  const location = useLocation()
  const navigate = useNavigate()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  const isActive = (path: string) => {
    if (path === '/') {
      return location.pathname === '/'
    }
    return location.pathname.startsWith(path)
  }

  return (
    <div className="app-layout">
      {/* Floating Pill Navigation */}
      <div className="nav-pill-container">
        <nav className="nav-pill">
          <div className="nav-logo" onClick={() => navigate('/')}>
            量化系统
          </div>

          {/* Desktop Navigation */}
          <div className="nav-links">
            {navItems.map(item => (
              <div
                key={item.key}
                className={`nav-item ${isActive(item.key) ? 'active' : ''}`}
                onClick={() => navigate(item.key)}
              >
                {item.label}
              </div>
            ))}
          </div>

          {/* Search Button */}
          <button className="nav-search-btn" aria-label="搜索">
            <SearchOutlined />
          </button>

          {/* Mobile Menu Toggle */}
          <button
            className="nav-mobile-toggle"
            onClick={() => setMobileMenuOpen(true)}
            aria-label="打开菜单"
          >
            <MenuOutlined />
          </button>
        </nav>
      </div>

      {/* Mobile Overlay Menu */}
      <div className={`nav-mobile-overlay ${mobileMenuOpen ? 'open' : ''}`}>
        <button
          className="nav-mobile-close"
          onClick={() => setMobileMenuOpen(false)}
          aria-label="关闭菜单"
        >
          <CloseOutlined />
        </button>
        {navItems.map(item => (
          <div
            key={item.key}
            className={`nav-item ${isActive(item.key) ? 'active' : ''}`}
            onClick={() => {
              navigate(item.key)
              setMobileMenuOpen(false)
            }}
          >
            {item.label}
          </div>
        ))}
      </div>

      {/* Main Content */}
      <main className="app-content">
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
      </main>
    </div>
  )
}

export default App