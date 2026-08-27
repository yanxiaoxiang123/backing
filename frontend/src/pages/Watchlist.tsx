import { useMemo, useState } from 'react'
import { Alert, Button, message, Spin, Empty, Card, Modal } from 'antd'
import { PlusOutlined, StarFilled, ReloadOutlined } from '@ant-design/icons'
import {
  getWatchlist,
  addToWatchlist,
  removeFromWatchlist,
} from '../services/watchlist'
import { getRealtimeQuotes } from '../services/market'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import StockSearch from '../components/StockSearch'
import type { DashboardStock } from '../types'
import { getStockCodeAliases, normalizeStockCode } from '../utils/stockIdentity'
import { watchlistKeys } from '../services/queryKeys'
import {
  InstrumentTable,
  type InstrumentRow,
} from '../components/research/InstrumentTable'
import { useNavigate } from 'react-router-dom'
import { PageHeader } from '../components/research/ResearchPrimitives'

function Watchlist() {
  const navigate = useNavigate()
  const [updating, setUpdating] = useState(false)
  const [selectedStockCode, setSelectedStockCode] = useState<string | null>(null)
  const [selectedStockName, setSelectedStockName] = useState<string>('')
  const queryClient = useQueryClient()
  const watchlistQuery = useQuery({
    queryKey: watchlistKeys.list(),
    queryFn: getWatchlist,
    staleTime: 30_000,
  })
  const watchlist = useMemo(
    () => watchlistQuery.data?.items ?? [],
    [watchlistQuery.data],
  )
  const codes = useMemo(
    () =>
      watchlist.map((item) => normalizeStockCode(item.stock_code) ?? item.stock_code),
    [watchlist],
  )
  const quotesQuery = useQuery({
    queryKey: watchlistKeys.quotes(codes),
    queryFn: () => getRealtimeQuotes(codes),
    enabled: codes.length > 0,
    staleTime: 15_000,
    refetchInterval: 30_000,
  })
  const stockPriceMap = useMemo<Record<string, DashboardStock>>(() => {
    const map: Record<string, DashboardStock> = {}
    for (const quote of quotesQuery.data?.data ?? []) {
      const stock = {
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
      for (const alias of getStockCodeAliases(quote.symbol)) map[alias] = stock
    }
    return map
  }, [quotesQuery.data])

  const handleUpdate = async () => {
    try {
      setUpdating(true)
      await queryClient.invalidateQueries({ queryKey: watchlistKeys.all })
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
      await queryClient.invalidateQueries({ queryKey: watchlistKeys.all })
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
      await queryClient.invalidateQueries({ queryKey: watchlistKeys.all })
    } catch {
      message.error('移除失败')
    }
  }

  const confirmRemoveStock = (row: InstrumentRow) => {
    Modal.confirm({
      title: '移除自选股？',
      content: `确定要移除 ${row.name || row.code} 吗？`,
      okText: '移除',
      cancelText: '取消',
      okButtonProps: { danger: true },
      onOk: () => handleRemoveStock(row.code),
    })
  }

  const instrumentRows = useMemo<InstrumentRow[]>(
    () =>
      watchlist.map((item) => {
        const quote = stockPriceMap[item.stock_code]
        return {
          id: item.id,
          code: item.stock_code,
          name: item.stock_name || item.stock_code,
          currentPrice: quote?.current_price,
          change: quote?.change,
          changePercent: quote?.change_percent,
          addedAt: item.added_at,
        }
      }),
    [stockPriceMap, watchlist],
  )

  return (
    <div className="fade-in">
      <PageHeader
        eyebrow="WATCHLIST"
        title={
          <>
            <StarFilled style={{ color: 'var(--color-warning)', marginRight: 8 }} />
            自选股
          </>
        }
        subtitle="集中观察关注标的的最新行情和研究入口"
        actions={
          <Button icon={<ReloadOutlined />} onClick={handleUpdate} loading={updating}>
            更新数据
          </Button>
        }
      />

      <Card className="apple-card" style={{ marginBottom: 'var(--space-lg)' }}>
        <div
          style={{ display: 'flex', gap: 'var(--space-md)', alignItems: 'flex-start' }}
        >
          <div style={{ flex: 1 }}>
            <StockSearch
              value={selectedStockCode ?? undefined}
              onChange={(code, option) => {
                setSelectedStockCode(code)
                setSelectedStockName(option?.name || code)
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
          <span className="data-freshness">行情每 30 秒自动刷新</span>
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
          <>
            {quotesQuery.isError ? (
              <Alert
                type="warning"
                showIcon
                message="行情暂不可用"
                description="自选列表仍可查看；行情服务恢复后可重试。"
                action={
                  <Button onClick={() => void quotesQuery.refetch()}>重试</Button>
                }
                className="watchlist-quotes-alert"
              />
            ) : null}
            <InstrumentTable
              rows={instrumentRows}
              loading={quotesQuery.isFetching}
              onOpen={(row) => navigate(`/stocks/${row.code}`)}
              onResearch={(row) =>
                navigate(`/workspace?stock=${encodeURIComponent(row.code)}`)
              }
              onRemove={confirmRemoveStock}
            />
          </>
        )}
      </div>
    </div>
  )
}

export default Watchlist
