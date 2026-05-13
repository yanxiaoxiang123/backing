import { Routes, Route, Navigate, useNavigate } from 'react-router-dom'
import { useLocation } from 'react-router-dom'

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

  return (
    <div className="app-layout">
      {/* Apple-style Header */}
      <header className="app-header">
        <div className="header-content">
          <div className="app-logo">量化系统</div>
          <nav className="app-nav">
            {navItems.map(item => (
              <div
                key={item.key}
                className={`nav-item ${location.pathname === item.key || (item.key !== '/' && location.pathname.startsWith(item.key)) ? 'active' : ''}`}
                onClick={() => navigate(item.key)}
              >
                {item.label}
              </div>
            ))}
          </nav>
        </div>
      </header>

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
