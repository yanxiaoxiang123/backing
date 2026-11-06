import { useMemo, useRef, useState } from 'react'
import {
  Alert,
  Button,
  Descriptions,
  Drawer,
  Empty,
  Grid,
  Input,
  Pagination,
  Select,
  Skeleton,
  Table,
} from 'antd'
import { useQuery } from '@tanstack/react-query'
import { EyeOutlined, LeftOutlined, RightOutlined } from '@ant-design/icons'
import { Link } from 'react-router-dom'
import { Prose } from '../components/Prose'
import { LazyECharts } from '../components/charts/LazyECharts'
import { ChartResetButton } from '../components/charts/ChartResetButton'
import { FinancialValue } from '../components/research/FinancialValue'
import { QueryStatus } from '../components/research/QueryStatus'
import { ParameterSnapshot } from '../components/research/ParameterSnapshot'
import { MetricCard, PageHeader } from '../components/research/ResearchPrimitives'
import { getBacktestResults, getBacktestResult, getStock } from '../services/api'
import type { BacktestListItem } from '../types'
import { backtestKeys, stockKeys } from '../services/queryKeys'
import { STRATEGY_METADATA } from '../constants/strategy'
import { useHistoryLocation } from '../hooks/useHistoryLocation'
import { useScrollMemory } from '../hooks/useScrollMemory'
import {
  formatDate,
  formatDateTime,
  formatNumber,
  formatPercent,
  isFiniteNumber,
  tradeAction,
} from '../utils/dataFormat'

const strategyLabel = (name?: string) =>
  name ? STRATEGY_METADATA[name]?.name || name : '历史策略'

function BacktestHistory() {
  const location = useHistoryLocation()
  const { page, pageSize, stock, strategy, sort, selectedId, update } = location
  const screens = Grid.useBreakpoint()
  const [resetKey, setResetKey] = useState(0)
  const opener = useRef<HTMLElement | null>(null)
  const resultsQuery = useQuery({
    queryKey: backtestKeys.list({
      cursor: (page - 1) * pageSize,
      limit: pageSize,
      stock: stock || undefined,
      strategy: strategy || undefined,
      sort,
    }),
    queryFn: () =>
      getBacktestResults(
        stock || undefined,
        (page - 1) * pageSize,
        pageSize,
        strategy || undefined,
        sort,
      ),
    placeholderData: (previous) => previous,
    staleTime: 30_000,
  })
  const detailQuery = useQuery({
    queryKey: backtestKeys.detail(selectedId ?? 0),
    queryFn: () => getBacktestResult(selectedId as number),
    enabled: selectedId !== null,
    staleTime: 5 * 60_000,
  })
  const currentResult = detailQuery.data
  const stockQuery = useQuery({
    queryKey: stockKeys.detail(currentResult?.stock_code ?? ''),
    queryFn: () => getStock(currentResult!.stock_code),
    enabled: selectedId !== null && Boolean(currentResult?.stock_code),
    staleTime: 5 * 60_000,
  })
  useScrollMemory(
    location.scrollKey,
    Boolean(resultsQuery.data) && !resultsQuery.isPlaceholderData,
  )
  const results = useMemo(
    () => resultsQuery.data?.items ?? [],
    [resultsQuery.data?.items],
  )
  const total = resultsQuery.data?.total ?? 0
  const summary = useMemo(() => {
    const returns = results.map((item) => item.total_return).filter(isFiniteNumber)
    return {
      runs: results.length,
      average: returns.length
        ? returns.reduce((sum, value) => sum + value, 0) / returns.length
        : null,
      positive: returns.filter((value) => value > 0).length,
      measured: returns.length,
    }
  }, [results])
  const selectedIndex = results.findIndex((item) => item.id === selectedId)
  const openDetail = (id: number) => {
    opener.current =
      document.activeElement instanceof HTMLElement ? document.activeElement : null
    update({ result: id })
  }
  const changePage = (next: number, size: number) =>
    update({ page: size === pageSize ? next : 1, page_size: size })

  const chartOption = useMemo(() => {
    if (!currentResult) return {}
    const saved = currentResult.portfolio_values
    const dates: string[] = []
    const capital: number[] = []
    if (saved?.length) {
      saved.forEach((item) => {
        dates.push(item.date)
        capital.push(item.total_value)
      })
    } else {
      let cash = currentResult.initial_capital
      currentResult.trades.forEach((trade) => {
        dates.push(trade.trade_date || trade.date || '')
        cash += trade.action === 'buy' ? -trade.amount : trade.amount
        capital.push(cash)
      })
      if (capital.length) {
        dates.push(currentResult.end_date)
        capital.push(currentResult.final_capital)
      }
    }
    return {
      tooltip: {
        trigger: 'axis',
        valueFormatter: (value: unknown) => `${formatNumber(value)} 元`,
      },
      grid: { left: 68, right: 20, bottom: 64, top: 34 },
      xAxis: {
        type: 'category',
        data: dates,
        boundaryGap: false,
        axisLabel: { hideOverlap: true, color: '#6b6b6b' },
        axisLine: { lineStyle: { color: '#e8e8e8' } },
      },
      yAxis: {
        type: 'value',
        scale: true,
        name: '资金 / 元',
        axisLabel: {
          color: '#6b6b6b',
          formatter: (value: number) => formatNumber(value, 0),
        },
        splitLine: { lineStyle: { color: '#eeeeee' } },
      },
      dataZoom: [
        { type: 'inside', start: 0, end: 100 },
        { type: 'slider', bottom: 4, height: 20, start: 0, end: 100 },
      ],
      series: [
        {
          name: saved?.length ? '组合价值' : '交易现金流估算',
          data: capital,
          type: 'line',
          step: saved?.length ? false : 'end',
          smooth: false,
          showSymbol: false,
          lineStyle: { color: '#1677ff', width: 2 },
          itemStyle: { color: '#1677ff' },
        },
      ],
    }
  }, [currentResult])

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 65 },
    { title: '策略', dataIndex: 'strategy_name', width: 130, render: strategyLabel },
    {
      title: '股票代码',
      dataIndex: 'stock_code',
      width: 112,
      render: (code: string) => <Link to={`/stocks/${code}`}>{code}</Link>,
    },
    { title: '开始日期', dataIndex: 'start_date', width: 110, render: formatDate },
    { title: '结束日期', dataIndex: 'end_date', width: 110, render: formatDate },
    {
      title: '收益率',
      dataIndex: 'total_return',
      width: 105,
      align: 'right' as const,
      render: (value: unknown) => <FinancialValue value={value} />,
    },
    {
      title: '交易次数',
      dataIndex: 'total_trades',
      width: 90,
      align: 'right' as const,
      render: (value: unknown) => formatNumber(value, 0),
    },
    {
      title: '回测时间（北京时间）',
      dataIndex: 'created_at',
      width: 174,
      render: formatDateTime,
    },
    {
      title: '操作',
      key: 'action',
      width: 85,
      fixed: 'right' as const,
      render: (_: unknown, record: BacktestListItem) => (
        <Button
          type="text"
          icon={<EyeOutlined />}
          onClick={() => openDetail(record.id)}
        >
          查看
        </Button>
      ),
    },
  ]
  const tradeColumns = [
    {
      title: '日期',
      dataIndex: 'trade_date',
      width: 116,
      render: (_: unknown, record: { trade_date?: string; date?: string }) =>
        formatDate(record.trade_date || record.date),
    },
    {
      title: '操作',
      dataIndex: 'action',
      width: 76,
      render: (action: string) => {
        const value = tradeAction(action)
        return <span className={value.className}>{value.label}</span>
      },
    },
    {
      title: '价格 / 元',
      dataIndex: 'price',
      align: 'right' as const,
      render: (value: unknown) => formatNumber(value),
    },
    {
      title: '数量 / 股',
      dataIndex: 'quantity',
      align: 'right' as const,
      render: (value: unknown) => formatNumber(value, 0),
    },
    {
      title: '金额 / 元',
      dataIndex: 'amount',
      align: 'right' as const,
      render: (value: unknown) => formatNumber(value),
    },
  ]

  return (
    <div className="fade-in history-workspace">
      <PageHeader
        eyebrow="BACKTEST HISTORY"
        title="回测历史"
        subtitle="筛选已保存的运行，比较收益并追溯参数与交易。"
        actions={
          <QueryStatus
            fetching={resultsQuery.isFetching && Boolean(resultsQuery.data)}
            onRefresh={() => void resultsQuery.refetch()}
          />
        }
      />
      <div className="backtest-history-summary" aria-label="回测摘要">
        <MetricCard
          label="当前页运行"
          value={formatNumber(summary.runs, 0)}
          detail={`筛选后共 ${formatNumber(total, 0)} 次运行`}
        />
        <MetricCard
          label="本页平均收益率"
          value={<FinancialValue value={summary.average} />}
          detail={
            summary.measured
              ? `${summary.measured} 条有效收益 · 非全量统计`
              : '暂无有效收益'
          }
        />
        <MetricCard
          label="本页盈利运行"
          value={formatNumber(summary.positive, 0)}
          detail={
            summary.measured
              ? `有效记录中占 ${formatPercent((summary.positive / summary.measured) * 100, 0)}`
              : '暂无记录'
          }
        />
      </div>
      <section className="research-panel backtest-history-panel" aria-label="实验记录">
        <div className="research-panel-heading">
          <Prose as="h2">实验记录</Prose>
          <span>共 {formatNumber(total, 0)} 次运行</span>
        </div>
        <div className="backtest-history-toolbar" aria-label="回测历史筛选">
          <Input
            allowClear
            placeholder="筛选股票代码"
            aria-label="筛选股票代码"
            value={location.stockInput}
            onChange={(event) => location.setStockInput(event.target.value)}
          />
          <Input
            allowClear
            placeholder="筛选策略"
            aria-label="筛选策略"
            value={location.strategyInput}
            onChange={(event) => location.setStrategyInput(event.target.value)}
          />
          <Select
            aria-label="回测排序"
            value={sort}
            onChange={(value) => update({ sort: value, page: 1 })}
            options={[
              { value: 'newest', label: '最新运行' },
              { value: 'return', label: '收益率优先' },
            ]}
          />
        </div>
        {resultsQuery.isError && (
          <Alert
            type="error"
            showIcon
            message={
              resultsQuery.data ? '更新失败，以下保留上次记录' : '加载历史记录失败'
            }
            action={<Button onClick={() => void resultsQuery.refetch()}>重试</Button>}
          />
        )}
        {resultsQuery.isLoading ? (
          <div
            className="history-loading"
            role="status"
            aria-label="正在加载历史记录"
            aria-busy="true"
          >
            <Skeleton active paragraph={{ rows: 6 }} />
          </div>
        ) : screens.md ? (
          <Table
            columns={columns}
            dataSource={results}
            rowKey="id"
            scroll={{ x: 1080 }}
            pagination={false}
            rowClassName={(record) =>
              record.id === selectedId ? 'history-row-selected' : ''
            }
          />
        ) : results.length ? (
          <ul className="history-mobile-list" aria-label="回测记录">
            {results.map((record) => (
              <li key={record.id}>
                <div className="history-mobile-top">
                  <Link to={`/stocks/${record.stock_code}`}>{record.stock_code}</Link>
                  <FinancialValue value={record.total_return} />
                </div>
                <div className="history-mobile-meta">
                  <span>
                    {strategyLabel(record.strategy_name)} · #{record.id}
                  </span>
                  <Button
                    type="text"
                    size="small"
                    icon={<EyeOutlined />}
                    onClick={() => openDetail(record.id)}
                  >
                    查看
                  </Button>
                </div>
                <div className="history-mobile-dates">
                  {formatDate(record.start_date)} — {formatDate(record.end_date)}
                </div>
                <div className="history-mobile-dates">
                  {formatDateTime(record.created_at)} · 北京时间
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="没有符合筛选的回测记录"
          />
        )}
        {total > 0 && (
          <Pagination
            className="history-pagination"
            current={page}
            pageSize={pageSize}
            total={total}
            onChange={changePage}
            showSizeChanger={Boolean(screens.md)}
            pageSizeOptions={[10, 20, 50, 100]}
            simple={!screens.md}
            showTotal={(count) => `共 ${formatNumber(count, 0)} 条`}
          />
        )}
      </section>
      <Drawer
        title={`回测详情${selectedId ? ` · #${selectedId}` : ''}${stockQuery.data?.name ? ` · ${stockQuery.data.name}` : ''}`}
        open={selectedId !== null}
        onClose={() => update({ result: null }, true)}
        width={screens.md ? 880 : '100%'}
        rootClassName="history-detail-drawer"
        afterOpenChange={(open) => {
          if (!open && opener.current?.isConnected) opener.current.focus()
        }}
      >
        <div className="history-detail-navigation">
          <span>
            {selectedIndex >= 0
              ? `本页第 ${selectedIndex + 1} / ${results.length} 条`
              : '通过链接查看的记录'}
          </span>
          <div>
            <Button
              size="small"
              icon={<LeftOutlined />}
              disabled={selectedIndex <= 0 || resultsQuery.isPlaceholderData}
              onClick={() => update({ result: results[selectedIndex - 1].id }, true)}
            >
              上一条
            </Button>
            <Button
              size="small"
              disabled={
                selectedIndex < 0 ||
                selectedIndex >= results.length - 1 ||
                resultsQuery.isPlaceholderData
              }
              onClick={() => update({ result: results[selectedIndex + 1].id }, true)}
            >
              下一条 <RightOutlined />
            </Button>
          </div>
        </div>
        {detailQuery.isLoading && (
          <div role="status" aria-label="正在加载回测详情" aria-busy="true">
            <Skeleton active paragraph={{ rows: 8 }} />
          </div>
        )}
        {detailQuery.isError && (
          <Alert
            type="error"
            showIcon
            message="加载详情失败，记录可能已被删除"
            action={<Button onClick={() => void detailQuery.refetch()}>重试</Button>}
          />
        )}
        {currentResult && (
          <div className="history-detail-content">
            <div className="backtest-detail-metrics">
              <MetricCard
                label="总收益率"
                value={<FinancialValue value={currentResult.total_return} />}
              />
              <MetricCard
                label="年化收益率"
                value={<FinancialValue value={currentResult.annual_return} />}
              />
              <MetricCard
                label="夏普比率"
                value={formatNumber(currentResult.sharpe_ratio)}
              />
              <MetricCard
                label="最大回撤"
                value={formatPercent(currentResult.max_drawdown)}
              />
            </div>
            <Descriptions size="small" bordered column={screens.sm ? 2 : 1}>
              <Descriptions.Item label="股票">
                <Link to={`/stocks/${currentResult.stock_code}`}>
                  {currentResult.stock_code}
                </Link>
              </Descriptions.Item>
              <Descriptions.Item label="策略">
                {strategyLabel(currentResult.strategy_name)}
              </Descriptions.Item>
              <Descriptions.Item label="回测区间" span={2}>
                <span className="data-nowrap">
                  {formatDate(currentResult.start_date)}
                </span>
                {' — '}
                <span className="data-nowrap">
                  {formatDate(currentResult.end_date)}
                </span>
              </Descriptions.Item>
              <Descriptions.Item label="初始资金 / 元">
                <span className="data-nowrap">
                  {formatNumber(currentResult.initial_capital)}
                </span>
              </Descriptions.Item>
              <Descriptions.Item label="最终资金 / 元">
                <span className="data-nowrap">
                  {formatNumber(currentResult.final_capital)}
                </span>
              </Descriptions.Item>
              <Descriptions.Item label="生成时间" span={2}>
                <span className="data-nowrap">
                  {formatDateTime(currentResult.created_at)}
                </span>{' '}
                <small className="research-data-context">北京时间</small>
              </Descriptions.Item>
            </Descriptions>
            <section>
              <Prose as="h3">参数快照</Prose>
              <ParameterSnapshot parameters={currentResult.parameters} />
            </section>
            <section className="history-equity-panel">
              <div className="history-section-heading">
                <Prose as="h3">
                  {currentResult.portfolio_values?.length
                    ? '资金曲线'
                    : '交易现金流（旧记录估算）'}
                </Prose>
                <ChartResetButton onReset={() => setResetKey((value) => value + 1)} />
              </div>
              <p className="research-data-context">
                {formatDate(
                  currentResult.portfolio_values?.[0]?.date || currentResult.start_date,
                )}{' '}
                —{' '}
                {formatDate(
                  currentResult.portfolio_values?.[
                    currentResult.portfolio_values.length - 1
                  ]?.date || currentResult.end_date,
                )}{' '}
                · 单位：人民币元
              </p>
              {currentResult.portfolio_values?.length || currentResult.trades.length ? (
                <LazyECharts
                  option={chartOption}
                  resetKey={resetKey}
                  style={{ height: 300 }}
                  summary="本次回测已保存资金或旧记录交易现金流，可缩放和重置视图"
                />
              ) : (
                <Empty
                  image={Empty.PRESENTED_IMAGE_SIMPLE}
                  description="这条记录没有保存曲线或交易数据"
                />
              )}
              {!currentResult.portfolio_values?.length && (
                <Prose as="p" className="research-data-context">
                  旧记录仅保留交易现金流估算，不能代表逐日组合净值。
                </Prose>
              )}
            </section>
            <section>
              <Prose as="h3">
                交易记录 <small>{formatNumber(currentResult.total_trades, 0)} 次</small>
              </Prose>
              <Table
                columns={tradeColumns}
                dataSource={currentResult.trades}
                rowKey="id"
                scroll={{ x: 570 }}
                pagination={{ pageSize: 10 }}
                size="small"
              />
            </section>
            <Prose as="p" className="research-data-context">
              历史表现仅供研究，不代表未来收益；请结合数据口径、费用与风险评估。
            </Prose>
          </div>
        )}
      </Drawer>
    </div>
  )
}

export default BacktestHistory
