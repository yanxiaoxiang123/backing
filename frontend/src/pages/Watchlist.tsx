import { useMemo, useState } from 'react'
import { Alert, Table, Button, message, Spin, Empty, Popconfirm, Card } from 'antd'
import {
  DeleteOutlined,
  PlusOutlined,
  StarFilled,
  ReloadOutlined,
} from '@ant-design/icons'
import {
  getWatchlist,
  addToWatchlist,
  removeFromWatchlist,
  getRealtimeQuotes,
} from '../services/api'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import StockSearch from '../components/StockSearch'
import type { WatchlistItem, DashboardStock } from '../types'

function Watchlist() {
  const [updating, setUpdating] = useState(false)
  const [selectedStockCode, setSelectedStockCode] = useState<string | null>(null)
  const [selectedStockName, setSelectedStockName] = useState<string>('')
  const queryClient = useQueryClient()
  const watchlistQuery = useQuery({ queryKey: ['watchlist'], queryFn: getWatchlist })
  const watchlist = useMemo(
    () => watchlistQuery.data?.items ?? [],
    [watchlistQuery.data],
  )
  const codes = useMemo(() => watchlist.map((item) => item.stock_code), [watchlist])
  const quotesQuery = useQuery({
    queryKey: ['watchlist', 'quotes', codes],
    queryFn: () => getRealtimeQuotes(codes),
    enabled: codes.length > 0,
  })
  const stockPriceMap = useMemo<Record<string, DashboardStock>>(() => {
    const map: Record<string, DashboardStock> = {}
    for (const quote of quotesQuery.data?.data ?? []) {
      map[quote.symbol] = {
        id: 0,
        code: quote.symbol,
        name: '',
        current_price: quote.close,
        high: quote.high,
        low: quote.low,
        volume: quote.volume,
        change: quote.change,
        change_percent: quote.change_percent,
      }
    }
    return map
  }, [quotesQuery.data])

  const handleUpdate = async () => {
    try {
      setUpdating(true)
      await queryClient.invalidateQueries({ queryKey: ['watchlist'] })
      message.success('自选股数据已更新')
    } catch {
      message.error('更新失败')
    } finally {
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
      await queryClient.invalidateQueries({ queryKey: ['watchlist'] })
    } catch (error: unknown) {
      const response = (
        error as { response?: { status?: number; data?: { detail?: string } } }
      ).response
      if (response?.status === 400) {
        message.warning(response.data?.detail || '该股票已在自选股中')
      } else {
        message.error('添加失败')
      }
    }
  }

  const handleRemoveStock = async (stockCode: string) => {
    try {
      await removeFromWatchlist(stockCode)
      message.success('已从自选股移除')
      await queryClient.invalidateQueries({ queryKey: ['watchlist'] })
    } catch {
      message.error('移除失败')
    }
  }

  const columns = [
    {
      title: '股票代码',
      dataIndex: 'stock_code',
      key: 'stock_code',
      width: 120,
      render: (code: string) => (
        <span style={{ color: 'var(--color-ink)', fontWeight: 500 }}>{code}</span>
      ),
    },
    {
      title: '股票名称',
      dataIndex: 'stock_name',
      key: 'stock_name',
      width: 120,
    },
    {
      title: '最新价',
      key: 'current_price',
      width: 100,
      render: (_: unknown, record: WatchlistItem) => {
        const priceData = stockPriceMap[record.stock_code]
        if (!priceData) return '-'
        return (
          <span style={{ fontWeight: 500 }}>{priceData.current_price.toFixed(2)}</span>
        )
      },
    },
    {
      title: '涨跌额',
      key: 'change',
      width: 100,
      render: (_: unknown, record: WatchlistItem) => {
        const priceData = stockPriceMap[record.stock_code]
        if (!priceData) return '-'
        const color =
          priceData.change > 0
            ? 'var(--color-up, #f5222d)'
            : priceData.change < 0
              ? 'var(--color-down, #52c41a)'
              : 'var(--color-text-secondary)'
        return (
          <span style={{ color }}>
            {priceData.change >= 0 ? '+' : ''}
            {priceData.change.toFixed(2)}
          </span>
        )
      },
    },
    {
      title: '涨跌幅',
      key: 'change_percent',
      width: 100,
      render: (_: unknown, record: WatchlistItem) => {
        const priceData = stockPriceMap[record.stock_code]
        if (!priceData) return '-'
        const color =
          priceData.change_percent > 0
            ? 'var(--color-up, #f5222d)'
            : priceData.change_percent < 0
              ? 'var(--color-down, #52c41a)'
              : 'var(--color-text-secondary)'
        return (
          <span style={{ color }}>
            {priceData.change_percent >= 0 ? '+' : ''}
            {priceData.change_percent.toFixed(2)}%
          </span>
        )
      },
    },
    {
      title: '添加时间',
      dataIndex: 'added_at',
      key: 'added_at',
      width: 120,
      render: (date: string) => new Date(date).toLocaleDateString('zh-CN'),
    },
    {
      title: '操作',
      key: 'action',
      width: 100,
      render: (_: unknown, record: WatchlistItem) => (
        <Popconfirm
          title="确定要从自选股中移除吗？"
          onConfirm={() => handleRemoveStock(record.stock_code)}
          okText="确定"
          cancelText="取消"
        >
          <Button type="text" danger icon={<DeleteOutlined />}>
            移除
          </Button>
        </Popconfirm>
      ),
    },
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
        <div
          style={{ display: 'flex', gap: 'var(--space-md)', alignItems: 'flex-start' }}
        >
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
          <div
            style={{
              marginTop: 'var(--space-sm)',
              color: 'var(--color-text-secondary)',
              fontSize: 'var(--font-size-sm)',
            }}
          >
            已选择:{' '}
            <span style={{ color: 'var(--color-ink)', fontWeight: 500 }}>
              {selectedStockCode}
            </span>{' '}
            - {selectedStockName}
          </div>
        )}
      </Card>

      <div className="apple-card">
        <div
          className="apple-card-header"
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <span className="apple-card-title">我的自选股 ({watchlist.length})</span>
          <Button icon={<ReloadOutlined />} onClick={handleUpdate} loading={updating}>
            更新数据
          </Button>
        </div>

        {watchlistQuery.isLoading ? (
          <div style={{ textAlign: 'center', padding: 'var(--space-xl)' }}>
            <Spin size="large" />
          </div>
        ) : watchlistQuery.isError ? (
          <Alert
            type="error"
            showIcon
            message="加载自选股失败"
            action={<Button onClick={() => void watchlistQuery.refetch()}>重试</Button>}
          />
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
