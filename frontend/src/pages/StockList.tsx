import { Prose } from '../components/Prose'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Button,
  Form,
  Grid,
  Input,
  message,
  Modal,
  Pagination,
  Select,
  Table,
} from 'antd'
import type { InputRef, TableColumnsType } from 'antd'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ExperimentOutlined,
  LineChartOutlined,
  RobotOutlined,
  SearchOutlined,
  SyncOutlined,
  ArrowRightOutlined,
  SortAscendingOutlined,
  SortDescendingOutlined,
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
import { DataQualityPanel } from '../components/research/DataQualityPanel'
import { useTableCapacity } from '../hooks/useTableCapacity'

function requestedSize(value: string | null) {
  const number = Number(value)
  return Number.isInteger(number) && number > 0 ? Math.min(number, 100) : null
}

function marketLabel(market: string) {
  return (
    ({ sh: '上海', sz: '深圳', bj: '北京' } as Record<string, string>)[market] ||
    market ||
    '—'
  )
}

function StockList() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const queryClient = useQueryClient()
  const screens = Grid.useBreakpoint()
  const compact = screens.md === false
  const tableAreaRef = useRef<HTMLDivElement>(null)
  const searchRef = useRef<InputRef>(null)
  const capacity = useTableCapacity(tableAreaRef)
  const [page, setPage] = useState(() => Number(searchParams.get('page')) || 1)
  const [preferredSize, setPreferredSize] = useState(() =>
    requestedSize(searchParams.get('page_size')),
  )
  const pageSize = Math.min(preferredSize ?? capacity, capacity)
  const [selectedKeys, setSelectedKeys] = useState<React.Key[]>([])
  const [descending, setDescending] = useState(searchParams.get('direction') === 'desc')
  const [syncForm] = Form.useForm()
  const [syncing, setSyncing] = useState(false)
  const [syncModalVisible, setSyncModalVisible] = useState(false)
  const [searchText, setSearchText] = useState(searchParams.get('q') ?? '')
  const [debouncedSearch, setDebouncedSearch] = useState(searchText)

  const [market, setMarket] = useState(searchParams.get('market') ?? '')
  const [sort, setSort] = useState<'id' | 'code' | 'name'>(
    (searchParams.get('sort') as 'id' | 'code' | 'name') || 'id',
  )

  const syncUrl = useCallback(
    (next: {
      page?: number
      pageSize?: number | null
      search?: string
      market?: string
      sort?: 'id' | 'code' | 'name'
      descending?: boolean
    }) => {
      const nextParams = new URLSearchParams(searchParams)
      const nextPage = next.page ?? page
      const nextPageSize = next.pageSize === undefined ? preferredSize : next.pageSize
      const nextSearch = next.search ?? searchText
      const nextMarket = next.market ?? market
      const nextSort = next.sort ?? sort
      if (nextPage > 1) nextParams.set('page', String(nextPage))
      else nextParams.delete('page')
      if (nextPageSize != null) nextParams.set('page_size', String(nextPageSize))
      else nextParams.delete('page_size')
      if (nextSearch) nextParams.set('q', nextSearch)
      else nextParams.delete('q')
      if (nextMarket) nextParams.set('market', nextMarket)
      else nextParams.delete('market')
      if (nextSort !== 'id') nextParams.set('sort', nextSort)
      else nextParams.delete('sort')
      if (next.descending ?? descending) nextParams.set('direction', 'desc')
      else nextParams.delete('direction')
      setSearchParams(nextParams, { replace: true })
    },
    [
      market,
      page,
      preferredSize,
      searchParams,
      searchText,
      setSearchParams,
      sort,
      descending,
    ],
  )

  const lastSyncedSearchRef = useRef(searchText)
  const syncUrlRef = useRef(syncUrl)
  syncUrlRef.current = syncUrl

  useEffect(() => {
    const focusSearch = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        searchRef.current?.focus()
      }
    }
    window.addEventListener('keydown', focusSearch)
    return () => window.removeEventListener('keydown', focusSearch)
  }, [])

  const previousCapacity = useRef(capacity)
  const previousSize = useRef(pageSize)
  useEffect(() => {
    if (previousCapacity.current !== capacity) {
      const nextPage = Math.floor(((page - 1) * previousSize.current) / pageSize) + 1
      setPage(nextPage)
      syncUrlRef.current({ page: nextPage })
    }
    previousCapacity.current = capacity
    previousSize.current = pageSize
  }, [capacity, page, pageSize])

  useEffect(() => {
    if (searchText === lastSyncedSearchRef.current) {
      return
    }
    const timer = setTimeout(() => {
      lastSyncedSearchRef.current = searchText
      setDebouncedSearch(searchText)
      setPage(1)
      syncUrlRef.current({ page: 1, search: searchText })
    }, 300)
    return () => clearTimeout(timer)
  }, [searchText])

  const stocksQuery = useQuery({
    queryKey: stockKeys.list({
      market: market || undefined,
      cursor: (page - 1) * pageSize,
      limit: pageSize,
      search: debouncedSearch || undefined,
    }),
    queryFn: () =>
      getStocks(
        market || undefined,
        (page - 1) * pageSize,
        pageSize,
        debouncedSearch || undefined,
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
    const nextPageSize = requestedSize(searchParams.get('page_size'))
    const nextSearch = searchParams.get('q') ?? ''
    const nextMarket = searchParams.get('market') ?? ''
    const nextSort = searchParams.get('sort') as 'id' | 'code' | 'name' | null
    setPage((value) => (value === nextPage ? value : nextPage))
    setPreferredSize((value) => (value === nextPageSize ? value : nextPageSize))
    setDescending(searchParams.get('direction') === 'desc')
    setSearchText((value) => {
      if (value !== nextSearch) {
        lastSyncedSearchRef.current = nextSearch
        setDebouncedSearch(nextSearch)
        return nextSearch
      }
      return value
    })
    setMarket((value) => (value === nextMarket ? value : nextMarket))
    if (nextSort === 'id' || nextSort === 'code' || nextSort === 'name') {
      setSort((value) => (value === nextSort ? value : nextSort))
    } else {
      setSort((value) => (value === 'id' ? value : 'id'))
    }
  }, [searchParams])

  const visibleStocks = useMemo(() => {
    if (sort === 'id')
      return descending ? [...filteredStocks].reverse() : filteredStocks
    const sorted = [...filteredStocks].sort((left, right) =>
      sort === 'name'
        ? left.name.localeCompare(right.name, 'zh-CN')
        : left.code.localeCompare(right.code),
    )
    return descending ? sorted.reverse() : sorted
  }, [filteredStocks, sort, descending])

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
    syncForm.setFieldsValue({
      stockCodes: selectedKeys.join(','),
      strategy: 'incremental',
    })
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
    navigate(`/stocks/${record.code}`)
  }

  const columns: TableColumnsType<Stock> = [
    {
      title: '股票代码',
      dataIndex: 'code',
      key: 'code',
      render: (code: string, record) => (
        <div className="stock-code-cell">
          <strong>{code}</strong>
          <span className="stock-mobile-name">{record.name}</span>
          <span className="stock-mobile-details">
            {marketLabel(record.market)} · {record.list_date || '上市日期未知'}
          </span>
        </div>
      ),
    },
    {
      title: '股票名称',
      dataIndex: 'name',
      key: 'name',
      responsive: ['md'],
    },
    {
      title: '市场',
      dataIndex: 'market',
      key: 'market',
      responsive: ['md'],
      render: (market: string) => (
        <span className="stock-market-label">{marketLabel(market)}</span>
      ),
    },
    {
      title: '上市日期',
      dataIndex: 'list_date',
      key: 'list_date',
      responsive: ['md'],
      render: (date: string) => date || '-',
    },
    {
      title: '操作',
      key: 'action',
      width: compact ? 128 : 230,
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
        return (
          <div
            className="stock-row-actions"
            onClick={(event) => event.stopPropagation()}
            onKeyDown={(event) => event.stopPropagation()}
          >
            <Button type="text" onClick={() => handleViewChart(record)}>
              进入研究 <ArrowRightOutlined aria-hidden="true" />
            </Button>
            <RowActionMenu items={items} label={`打开 ${record.name} 操作菜单`} />
          </div>
        )
      },
    },
  ]

  return (
    <div className="stock-list-page">
      <PageHeader
        eyebrow="INSTRUMENTS"
        title="股票管理"
        subtitle="搜索、同步并进入标的研究"
        actions={
          <div className="stock-list-controls__actions">
            <span className="stock-data-label">数据管理</span>
            <Button
              type="primary"
              icon={<SyncOutlined aria-hidden="true" spin={syncing} />}
              onClick={handleSyncStocks}
              loading={syncing}
            >
              同步股票列表
            </Button>
            <Button
              icon={<SyncOutlined aria-hidden="true" spin={syncing} />}
              onClick={handleSyncKline}
              loading={syncing}
            >
              {selectedKeys.length
                ? `同步所选 K 线 (${selectedKeys.length})`
                : '同步K线数据'}
            </Button>
          </div>
        }
      />

      <DataQualityPanel
        compact={compact}
        codes={filteredStocks.slice(0, pageSize).map((stock) => stock.code)}
      />
      <section
        className="research-panel stock-list-table-panel"
        aria-labelledby="stock-list-title"
      >
        <div className="stock-list-heading">
          <Prose as="h2" id="stock-list-title">
            股票列表{' '}
            <span className="stock-list-count">{total.toLocaleString()} 只</span>
          </Prose>
          <Button
            type="text"
            className="stock-sort-direction"
            icon={
              descending ? (
                <SortDescendingOutlined aria-hidden="true" />
              ) : (
                <SortAscendingOutlined aria-hidden="true" />
              )
            }
            onClick={() => {
              const nextDescending = sort === 'code' ? !descending : false
              setSort('code')
              setDescending(nextDescending)
              syncUrl({ sort: 'code', descending: nextDescending })
            }}
            title="对本页股票按代码排序"
          >
            {sort === 'id'
              ? '代码排序'
              : `${sort === 'name' ? '名称' : '代码'}${descending ? '降序' : '升序'}`}
          </Button>
        </div>
        <div className="stock-list-filters">
          <Input
            ref={searchRef}
            aria-label="搜索股票代码或名称"
            placeholder="搜索代码或名称..."
            prefix={<SearchOutlined />}
            suffix={<span className="stock-search-shortcut">⌘ K</span>}
            allowClear
            className="stock-list-search"
            value={searchText}
            onChange={(e) => {
              setSearchText(e.target.value)
              setPage(1)
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
          <span className="stock-visible-count">
            {selectedKeys.length
              ? `已选择 ${selectedKeys.length} 只`
              : `当前显示 ${Math.min(visibleStocks.length, pageSize)} 只`}
          </span>
        </div>
        <div ref={tableAreaRef} className="stock-list-table-area">
          <span aria-hidden="true" className="stock-row-measure" />
          <span aria-hidden="true" className="stock-head-measure" />
          <AsyncBoundary
            loading={stocksQuery.isLoading}
            loadingRows={Math.min(pageSize, 2)}
            error={stocksQuery.error}
            onRetry={() => void stocksQuery.refetch()}
          >
            <Table<Stock>
              className="stock-list-table"
              columns={columns}
              dataSource={visibleStocks.slice(0, pageSize)}
              rowKey="code"
              tableLayout="fixed"
              rowSelection={{
                columnWidth: compact ? 32 : 80,
                selectedRowKeys: selectedKeys,
                onChange: setSelectedKeys,
                preserveSelectedRowKeys: true,
                getCheckboxProps: (record) => ({
                  name: `stock-${record.code}`,
                  'aria-label': `选择 ${record.name}`,
                }),
                renderCell: (_checked, _record, _index, origin) => (
                  <span
                    onClick={(event) => event.stopPropagation()}
                    onKeyDown={(event) => event.stopPropagation()}
                  >
                    {origin}
                  </span>
                ),
              }}
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
              pagination={false}
              locale={{ emptyText: '没有匹配的股票，请调整搜索或市场条件' }}
            />
          </AsyncBoundary>
        </div>
        <div className="stock-list-pagination">
          <span className="stock-total">共 {total.toLocaleString()} 只股票</span>
          <Select
            aria-label="每页条数"
            className="stock-page-size"
            optionLabelProp="title"
            value={
              preferredSize != null && preferredSize <= capacity ? preferredSize : 0
            }
            onChange={(value: number) => {
              setPreferredSize(value || null)
              setPage(1)
              syncUrl({ page: 1, pageSize: value || null })
            }}
            options={[
              {
                value: 0,
                label: `${capacity} 条 / 页 · 自适应`,
                title: `${capacity} 条 / 页`,
              },
              ...[5, 10, 15, 20, 30, 50]
                .filter((size) => size <= capacity)
                .map((size) => ({
                  value: size,
                  label: `${size} 条 / 页`,
                  title: `${size} 条 / 页`,
                })),
            ]}
          />
          <Pagination
            current={page}
            pageSize={pageSize}
            total={total}
            showSizeChanger={false}
            showLessItems
            simple={compact}
            onChange={(next) => {
              setPage(next)
              syncUrl({ page: next })
            }}
          />
        </div>
      </section>
      <footer className="stock-list-footer">
        支持按代码、名称检索，点击进入研究查看行情与分析。
      </footer>

      {/* 同步K线 Modal */}
      <Modal
        title="同步K线数据"
        open={syncModalVisible}
        onCancel={() => setSyncModalVisible(false)}
        footer={null}
        centered
      >
        <Form form={syncForm} layout="vertical" onFinish={handleSyncKlineConfirm}>
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
