import { useEffect, useState } from 'react'
import { Table, Button, message, Spin, Empty, Popconfirm, Card } from 'antd'
import { DeleteOutlined, PlusOutlined, StarFilled, ReloadOutlined } from '@ant-design/icons'
import { getWatchlist, addToWatchlist, removeFromWatchlist, getWatchlistCodes, syncKline, getDashboardSummary } from '../services/api'
import StockSearch from '../components/StockSearch'
import type { WatchlistItem, DashboardStock } from '../types'

function Watchlist() {
  const [loading, setLoading] = useState(true)
  const [updating, setUpdating] = useState(false)
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([])
  const [stockPriceMap, setStockPriceMap] = useState<Record<string, DashboardStock>>({})
  const [selectedStockCode, setSelectedStockCode] = useState<string | null>(null)
  const [selectedStockName, setSelectedStockName] = useState<string>('')

  useEffect(() => {
    loadWatchlistWithPrices()
  }, [])

  const loadWatchlistWithPrices = async () => {
    try {
      setLoading(true)
      const [watchlistData, dashboardData] = await Promise.all([
        getWatchlist(),
        getDashboardSummary()
      ])
      setWatchlist(watchlistData.items)

      // Build price map from dashboard watchlist data
      const priceMap: Record<string, DashboardStock> = {}
      for (const stock of dashboardData.watchlist) {
        priceMap[stock.code] = stock
      }
      setStockPriceMap(priceMap)
    } catch (error) {
      message.error('加载自选股失败')
    } finally {
      setLoading(false)
    }
  }

  const handleUpdate = async () => {
    try {
      setUpdating(true)
      const codes = await getWatchlistCodes()
      if (codes.length === 0) {
        message.warning('自选股为空，请先添加股票')
        setUpdating(false)
        return
      }
      await syncKline(codes, undefined, undefined)
      message.success('正在更新数据...')
      // Reload after a short delay to allow sync to complete
      setTimeout(() => {
        setUpdating(false)
        loadWatchlistWithPrices()
        message.success('自选股数据已更新')
      }, 2000)
    } catch (error) {
      message.error('更新失败')
      setUpdating(false)
    }
  }

  const handleAddStock = async () => {
    if (!selectedStockCode) {
      message.warning('请先选择一个股票')
      return
    }

    try {
      await addToWatchlist(selectedStockCode)
      message.success(`已添加 ${selectedStockName || selectedStockCode} 到自选股`)
      setSelectedStockCode(null)
      setSelectedStockName('')
      loadWatchlistWithPrices()
    } catch (error: any) {
      if (error.response?.status === 400) {
        message.warning(error.response.data.detail || '该股票已在自选股中')
      } else {
        message.error('添加失败')
      }
    }
  }

  const handleRemoveStock = async (stockCode: string) => {
    try {
      await removeFromWatchlist(stockCode)
      message.success('已从自选股移除')
      loadWatchlistWithPrices()
    } catch (error) {
      message.error('移除失败')
    }
  }

  const columns = [
    {
      title: '股票代码',
      dataIndex: 'stock_code',
      key: 'stock_code',
      width: 120,
      render: (code: string) => <span style={{ color: 'var(--color-accent)', fontWeight: 500 }}>{code}</span>
    },
    {
      title: '股票名称',
      dataIndex: 'stock_name',
      key: 'stock_name',
      width: 120
    },
    {
      title: '最新价',
      key: 'current_price',
      width: 100,
      render: (_: any, record: WatchlistItem) => {
        const priceData = stockPriceMap[record.stock_code]
        if (!priceData) return '-'
        return (
          <span style={{ fontWeight: 500 }}>{priceData.current_price.toFixed(2)}</span>
        )
      }
    },
    {
      title: '涨跌额',
      key: 'change',
      width: 100,
      render: (_: any, record: WatchlistItem) => {
        const priceData = stockPriceMap[record.stock_code]
        if (!priceData) return '-'
        const color = priceData.change > 0 ? 'var(--color-up, #f5222d)' : priceData.change < 0 ? 'var(--color-down, #52c41a)' : 'var(--color-text-secondary)'
        return (
          <span style={{ color }}>{priceData.change >= 0 ? '+' : ''}{priceData.change.toFixed(2)}</span>
        )
      }
    },
    {
      title: '涨跌幅',
      key: 'change_percent',
      width: 100,
      render: (_: any, record: WatchlistItem) => {
        const priceData = stockPriceMap[record.stock_code]
        if (!priceData) return '-'
        const color = priceData.change_percent > 0 ? 'var(--color-up, #f5222d)' : priceData.change_percent < 0 ? 'var(--color-down, #52c41a)' : 'var(--color-text-secondary)'
        return (
          <span style={{ color }}>{priceData.change_percent >= 0 ? '+' : ''}{priceData.change_percent.toFixed(2)}%</span>
        )
      }
    },
    {
      title: '添加时间',
      dataIndex: 'added_at',
      key: 'added_at',
      width: 120,
      render: (date: string) => new Date(date).toLocaleDateString('zh-CN')
    },
    {
      title: '操作',
      key: 'action',
      width: 100,
      render: (_: any, record: WatchlistItem) => (
        <Popconfirm
          title="确定要从自选股中移除吗？"
          onConfirm={() => handleRemoveStock(record.stock_code)}
          okText="确定"
          cancelText="取消"
        >
          <Button
            type="text"
            danger
            icon={<DeleteOutlined />}
          >
            移除
          </Button>
        </Popconfirm>
      )
    }
  ]

  return (
    <div className="fade-in">
      <div className="page-header">
        <h1 className="page-title">
          <StarFilled style={{ color: 'var(--color-warning)', marginRight: 8 }} />
          自选股管理
        </h1>
        <p className="page-subtitle">添加或移除您关注的股票</p>
      </div>

      <Card className="apple-card" style={{ marginBottom: 'var(--space-lg)' }}>
        <div style={{ display: 'flex', gap: 'var(--space-md)', alignItems: 'flex-start' }}>
          <div style={{ flex: 1 }}>
            <StockSearch
              value={selectedStockCode ?? undefined}
              onChange={(code, option) => {
                setSelectedStockCode(code)
                setSelectedStockName(option?.label || code)
              }}
            />
          </div>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={handleAddStock}
            disabled={!selectedStockCode}
          >
            添加
          </Button>
        </div>
        {selectedStockCode && (
          <div style={{ marginTop: 'var(--space-sm)', color: 'var(--color-text-secondary)', fontSize: 'var(--font-size-sm)' }}>
            已选择: <span style={{ color: 'var(--color-accent)', fontWeight: 500 }}>{selectedStockCode}</span> - {selectedStockName}
          </div>
        )}
      </Card>

      <div className="apple-card">
        <div className="apple-card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span className="apple-card-title">
            我的自选股 ({watchlist.length})
          </span>
          <Button
            icon={<ReloadOutlined />}
            onClick={handleUpdate}
            loading={updating}
          >
            更新数据
          </Button>
        </div>

        {loading ? (
          <div style={{ textAlign: 'center', padding: 'var(--space-xl)' }}>
            <Spin size="large" />
          </div>
        ) : watchlist.length === 0 ? (
          <Empty
            description="暂无自选股，请在上方搜索添加"
            style={{ padding: 'var(--space-xl)' }}
          />
        ) : (
          <Table
            columns={columns}
            dataSource={watchlist}
            rowKey="id"
            pagination={{ pageSize: 10 }}
            locale={{ emptyText: '暂无自选股' }}
          />
        )}
      </div>
    </div>
  )
}

export default Watchlist
