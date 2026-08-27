import { useCallback, useEffect, useMemo, useState } from 'react'
import { Button, Form, Input, message, Modal, Select, Table } from 'antd'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ExperimentOutlined,
  LineChartOutlined,
  RobotOutlined,
  SearchOutlined,
  SyncOutlined,
} from '@ant-design/icons'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { submitSyncKline, submitSyncStocks, getApiErrorMessage } from '../services/api'
import { getStocks } from '../services/stocks'
import { useJobPolling } from '../hooks/useJobPolling'
import type { Stock } from '../types'
import { stockKeys } from '../services/queryKeys'
import {
  AsyncBoundary,
  PageHeader,
  RowActionMenu,
} from '../components/research/ResearchPrimitives'
import { normalizeStockCode } from '../utils/stockIdentity'

function StockList() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const queryClient = useQueryClient()
  const [page, setPage] = useState(() => Number(searchParams.get('page')) || 1)
  const [pageSize, setPageSize] = useState(
    () => Number(searchParams.get('page_size')) || 20,
  )
  const [syncing, setSyncing] = useState(false)
  const [syncModalVisible, setSyncModalVisible] = useState(false)
  const [searchText, setSearchText] = useState(searchParams.get('q') ?? '')
  const [market, setMarket] = useState(searchParams.get('market') ?? '')
  const [sort, setSort] = useState<'id' | 'code' | 'name'>(
    (searchParams.get('sort') as 'id' | 'code' | 'name') || 'id',
  )
  const stocksQuery = useQuery({
    queryKey: stockKeys.list({
      market: market || undefined,
      cursor: (page - 1) * pageSize,
      limit: pageSize,
      search: searchText || undefined,
    }),
    queryFn: () =>
      getStocks(
        market || undefined,
        (page - 1) * pageSize,
        pageSize,
        searchText || undefined,
      ),
    placeholderData: (previous) => previous,
  })
  const filteredStocks = useMemo<Stock[]>(
    () => stocksQuery.data?.items ?? [],
    [stocksQuery.data],
  )
  const total = stocksQuery.data?.total ?? 0

  // Keep local controls in sync with browser back/forward navigation.
  useEffect(() => {
    const nextPage = Number(searchParams.get('page')) || 1
    const nextPageSize = Number(searchParams.get('page_size')) || 20
    const nextSearch = searchParams.get('q') ?? ''
    const nextMarket = searchParams.get('market') ?? ''
    const nextSort = searchParams.get('sort') as 'id' | 'code' | 'name' | null
    setPage((value) => (value === nextPage ? value : nextPage))
    setPageSize((value) => (value === nextPageSize ? value : nextPageSize))
    setSearchText((value) => (value === nextSearch ? value : nextSearch))
    setMarket((value) => (value === nextMarket ? value : nextMarket))
    if (nextSort === 'id' || nextSort === 'code' || nextSort === 'name') {
      setSort((value) => (value === nextSort ? value : nextSort))
    } else {
      setSort((value) => (value === 'id' ? value : 'id'))
    }
  }, [searchParams])

  const syncUrl = useCallback(
    (next: {
      page?: number
      pageSize?: number
      search?: string
      market?: string
      sort?: 'id' | 'code' | 'name'
    }) => {
      const nextParams = new URLSearchParams(searchParams)
      const nextPage = next.page ?? page
      const nextPageSize = next.pageSize ?? pageSize
      const nextSearch = next.search ?? searchText
      const nextMarket = next.market ?? market
      const nextSort = next.sort ?? sort
      if (nextPage > 1) nextParams.set('page', String(nextPage))
      else nextParams.delete('page')
      if (nextPageSize !== 20) nextParams.set('page_size', String(nextPageSize))
      else nextParams.delete('page_size')
      if (nextSearch) nextParams.set('q', nextSearch)
      else nextParams.delete('q')
      if (nextMarket) nextParams.set('market', nextMarket)
      else nextParams.delete('market')
      if (nextSort !== 'id') nextParams.set('sort', nextSort)
      else nextParams.delete('sort')
      setSearchParams(nextParams, { replace: true })
    },
    [market, page, pageSize, searchParams, searchText, setSearchParams, sort],
  )

  const visibleStocks = useMemo(() => {
    if (sort === 'id') return filteredStocks
    return [...filteredStocks].sort((left, right) =>
      sort === 'name'
        ? left.name.localeCompare(right.name, 'zh-CN')
        : left.code.localeCompare(right.code),
    )
  }, [filteredStocks, sort])

  useEffect(() => {
    const savedScroll = sessionStorage.getItem('stocks.scrollY')
    if (savedScroll) {
      sessionStorage.removeItem('stocks.scrollY')
      requestAnimationFrame(() => window.scrollTo({ top: Number(savedScroll) }))
    }
  }, [])

  // 统一任务轮询（5 分钟超时；卸载自动取消）
  const { waitForJob } = useJobPolling({ timeoutMs: 300000 })

  const handleSyncStocks = async () => {
    setSyncing(true)
    try {
      const submission = await submitSyncStocks()
      const result = await waitForJob<{ stocks_synced: number; message: string }>(
        submission.job_id,
      )
      message.success(result.message || `同步完成: ${result.stocks_synced} 只股票`)
      await queryClient.invalidateQueries({ queryKey: stockKeys.all })
    } catch (error) {
      message.error(getApiErrorMessage(error))
    } finally {
      setSyncing(false)
    }
  }

  const handleSyncKline = async () => {
    setSyncModalVisible(true)
  }

  const handleSyncKlineConfirm = async (values: {
    stockCodes: string
    strategy: string
  }) => {
    const codes = values.stockCodes
      ? values.stockCodes.split(',').map((value) => normalizeStockCode(value))
      : undefined
    if (codes?.some((code) => !code)) {
      message.error('存在无法识别的股票代码，请使用 sh.600000 或 600000 格式')
      return
    }
    const normalizedCodes = codes?.filter((code): code is string => code !== null)
    setSyncing(true)
    try {
      const submission = await submitSyncKline(
        normalizedCodes?.length ? normalizedCodes : undefined,
        values.strategy as 'incremental' | 'full',
      )
      const result = await waitForJob<{ klines_synced: number; message: string }>(
        submission.job_id,
      )
      message.success(result.message || `同步成功: ${result.klines_synced} 条K线数据`)
    } catch (error) {
      message.error(getApiErrorMessage(error))
    } finally {
      setSyncing(false)
      setSyncModalVisible(false)
    }
  }

  const handleViewChart = (record: Stock) => {
    sessionStorage.setItem('stocks.scrollY', String(window.scrollY))
    navigate(`/stocks/${record.code}`)
  }

  const columns = [
    {
      title: '代码',
      dataIndex: 'code',
      key: 'code',
      width: 100,
      render: (code: string) => <span className="instrument-code">{code}</span>,
    },
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      width: 120,
    },
    {
      title: '市场',
      dataIndex: 'market',
      key: 'market',
      width: 80,
      render: (market: string) =>
        market === 'sh' ? '上海' : market === 'bj' ? '北京' : '深圳',
    },
    {
      title: '上市日期',
      dataIndex: 'list_date',
      key: 'list_date',
      width: 120,
      render: (date: string) => date || '-',
    },
    {
      title: '操作',
      key: 'action',
      width: 100,
      render: (_: unknown, record: Stock) => {
        const items = [
          {
            key: 'chart',
            icon: <LineChartOutlined />,
            label: '查看 K 线',
            onClick: () => handleViewChart(record),
          },
          {
            key: 'agent',
            icon: <RobotOutlined />,
            label: 'Agent 研究',
            onClick: () =>
              navigate(`/workspace?stock=${encodeURIComponent(record.code)}`),
          },
          {
            key: 'strategy',
            icon: <ExperimentOutlined />,
            label: '策略验证',
            onClick: () =>
              navigate(`/strategies?stock=${encodeURIComponent(record.code)}`),
          },
        ]
        return <RowActionMenu items={items} label={`打开 ${record.name} 操作菜单`} />
      },
    },
  ]

  return (
    <div className="fade-in">
      <PageHeader
        eyebrow="INSTRUMENTS"
        title="股票管理"
        subtitle="搜索、同步并进入标的研究"
      />

      {/* 操作栏 */}
      <div className="stock-list-controls research-panel">
        <div className="stock-list-controls__row">
          <div className="stock-list-controls__actions">
            <Button
              type="primary"
              icon={<SyncOutlined spin={syncing} />}
              onClick={handleSyncStocks}
              loading={syncing}
            >
              同步股票列表
            </Button>
            <Button
              icon={<SyncOutlined spin={syncing} />}
              onClick={handleSyncKline}
              loading={syncing}
            >
              同步K线数据
            </Button>
          </div>
          <Input
            placeholder="搜索代码或名称..."
            prefix={<SearchOutlined />}
            allowClear
            className="stock-list-search"
            value={searchText}
            onChange={(e) => {
              const value = e.target.value
              setSearchText(value)
              setPage(1)
              syncUrl({ page: 1, search: value })
            }}
          />
          <Select
            allowClear
            aria-label="市场"
            placeholder="全部市场"
            value={market || undefined}
            className="stock-list-market"
            onChange={(value) => {
              setMarket(value ?? '')
              setPage(1)
              syncUrl({ page: 1, market: value ?? '' })
            }}
            options={[
              { value: 'sh', label: '上海' },
              { value: 'sz', label: '深圳' },
              { value: 'bj', label: '北京' },
            ]}
          />
          <Select
            aria-label="股票排序"
            value={sort}
            className="stock-list-sort"
            onChange={(value: 'id' | 'code' | 'name') => {
              setSort(value)
              setPage(1)
              syncUrl({ page: 1, sort: value })
            }}
            options={[
              { value: 'id', label: '默认顺序' },
              { value: 'code', label: '代码排序' },
              { value: 'name', label: '名称排序' },
            ]}
          />
        </div>
      </div>

      {/* 股票列表 */}
      <div className="research-panel stock-list-table-panel">
        <AsyncBoundary
          loading={stocksQuery.isLoading}
          error={stocksQuery.error}
          onRetry={() => void stocksQuery.refetch()}
        >
          <Table
            columns={columns}
            dataSource={visibleStocks}
            rowKey="id"
            loading={stocksQuery.isFetching}
            onRow={(record) => ({
              onClick: () => handleViewChart(record),
              tabIndex: 0,
              role: 'link',
              'aria-label': `查看 ${record.name} ${record.code} K线`,
              onKeyDown: (event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault()
                  handleViewChart(record)
                }
              },
            })}
            pagination={{
              current: page,
              pageSize,
              total,
              onChange: (p, ps) => {
                setPage(p)
                setPageSize(ps)
                syncUrl({ page: p, pageSize: ps })
              },
              showSizeChanger: true,
              showTotal: (t) => `共 ${t} 条`,
            }}
          />
        </AsyncBoundary>
      </div>

      {/* 同步K线 Modal */}
      <Modal
        title="同步K线数据"
        open={syncModalVisible}
        onCancel={() => setSyncModalVisible(false)}
        footer={null}
        centered
      >
        <Form layout="vertical" onFinish={handleSyncKlineConfirm}>
          <Form.Item
            name="stockCodes"
            label="股票代码（可选）"
            extra="多个代码用逗号分隔，如: sh.600000,sz.000001。留空则同步所有股票。"
          >
            <Input placeholder="留空同步所有股票" />
          </Form.Item>
          <Form.Item name="strategy" label="同步策略">
            <Select>
              <Select.Option value="incremental">
                增量同步（有数据则从最新日期更新）
              </Select.Option>
              <Select.Option value="full">
                全量同步（重新拉取2020年至今所有数据）
              </Select.Option>
            </Select>
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={syncing} block>
              开始同步
            </Button>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

export default StockList
