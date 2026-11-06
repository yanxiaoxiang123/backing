import { Prose } from '../components/Prose'
import { useEffect, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Alert,
  Button,
  Collapse,
  DatePicker,
  Form,
  Input,
  InputNumber,
  Select,
  Space,
  Table,
  message,
} from 'antd'
import dayjs, { type Dayjs } from 'dayjs'
import StockSearch from '../components/StockSearch'
import {
  PageHeader,
  PriceChange,
  ResearchPanel,
} from '../components/research/ResearchPrimitives'
import { getApiErrorMessage } from '../services/api'
import {
  exportPortfolioExperiment,
  getPortfolioExperiment,
  listPortfolioExperiments,
  replayPortfolioExperiment,
  runPortfolioResearch,
} from '../services/portfolioResearch'
import type {
  PortfolioExperiment,
  PortfolioResearchRequest,
  PortfolioResearchResult,
} from '../types/portfolioResearch'
import { normalizeStockCode } from '../utils/stockIdentity'
import { useResearchHistory } from '../hooks/useResearchHistory'
import '../styles/portfolioResearch.css'

interface ResearchForm {
  name: string
  holdings: Array<{ code?: string; weight: number }>
  period: [Dayjs, Dayjs]
  initial_capital: number
  rebalance: PortfolioResearchRequest['rebalance']
  benchmark?: string
  corporate_action_mode: PortfolioResearchRequest['corporate_action_mode']
  dividend_tax: number
  commission: number
  minimum_commission: number
  sell_tax: number
  transfer: number
  slippage: number
  participation: number
}

function EquityChart({ result }: { result: PortfolioResearchResult }) {
  const container = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(600)
  useEffect(() => {
    const observer = new ResizeObserver(([entry]) =>
      setWidth(Math.max(240, entry.contentRect.width)),
    )
    if (container.current) observer.observe(container.current)
    return () => observer.disconnect()
  }, [])
  const series = [
    result.portfolio_values,
    ...(result.benchmark ? [result.benchmark.portfolio_values] : []),
  ]
  const values = series.flatMap((rows) =>
    rows.map((row) => row.total_value / result.initial_capital),
  )
  const low = Math.min(1, ...values)
  const high = Math.max(1, ...values)
  const span = high - low || 0.02
  const min = low - span * 0.1
  const max = high + span * 0.1
  const y = (value: number) => 180 - ((value - min) / (max - min)) * 160
  const x = (index: number, count: number) =>
    56 + (index / Math.max(count - 1, 1)) * (width - 72)
  return (
    <div ref={container} className="portfolio-equity">
      <div className="portfolio-chart-key">
        <span>组合净值</span>
        {result.benchmark && <span>买入持有基准 · {result.benchmark.stock_code}</span>}
      </div>
      <svg
        viewBox={`0 0 ${width} 220`}
        role="img"
        aria-label="组合与基准净值，初始资金归一为一"
      >
        {[0, 1, 2, 3].map((index) => {
          const value = min + ((max - min) * index) / 3
          return (
            <g key={index}>
              <line
                x1="56"
                x2={width - 16}
                y1={y(value)}
                y2={y(value)}
                className="portfolio-grid-line"
              />
              <text x="44" y={y(value) + 4} textAnchor="end">
                {value.toFixed(3)}
              </text>
            </g>
          )
        })}
        {series.map((rows, index) => (
          <polyline
            key={index}
            points={rows
              .map(
                (row, i) =>
                  `${x(i, rows.length)},${y(row.total_value / result.initial_capital)}`,
              )
              .join(' ')}
            className={index ? 'portfolio-benchmark-line' : 'portfolio-equity-line'}
          />
        ))}
        <text x="56" y="208">
          {result.portfolio_values[0].date}
        </text>
        <text x={width - 16} y="208" textAnchor="end">
          {result.portfolio_values[result.portfolio_values.length - 1]?.date}
        </text>
      </svg>
    </div>
  )
}

const reasons: Record<string, string> = {
  non_executable_session: '停牌或行情不可成交',
  previous_session_capacity: '前一交易日成交量容量不足',
  shared_cash: '共享资金不足',
  fees_exceed_cash_and_proceeds: '成交收入与余额不足以支付费用',
}

export default function PortfolioResearch() {
  const [form] = Form.useForm<ResearchForm>()
  const [experiment, setExperiment] = useState<PortfolioExperiment | null>(null)
  const [running, setRunning] = useState(false)
  const [action, setAction] = useState('')
  const [error, setError] = useState('')
  const [page, setPage] = useState(1)
  const resultHeading = useRef<HTMLHeadingElement>(null)
  const queryClient = useQueryClient()
  const history = useQuery({
    queryKey: ['portfolio-experiments', page],
    queryFn: () => listPortfolioExperiments(page),
  })
  useEffect(() => {
    const latest = history.data?.items[0]
    if (experiment || !latest || running || action) return
    let active = true
    getPortfolioExperiment(latest.experiment_id)
      .then((item) => {
        if (active) setExperiment((current) => current ?? item)
      })
      .catch(() => {
        if (active) setError('最近保存的实验加载失败，可在下方列表重试')
      })
    return () => {
      active = false
    }
  }, [experiment, history.data, running, action])

  function openResult(item: PortfolioExperiment) {
    setExperiment(item)
    if (window.innerWidth <= 1100) {
      resultHeading.current?.focus({ preventScroll: true })
      resultHeading.current?.scrollIntoView?.({ block: 'start' })
    }
  }
  const holdings = Form.useWatch('holdings', form) as
    ResearchForm['holdings'] | undefined
  const period = Form.useWatch('period', form) as ResearchForm['period'] | undefined
  const selectedBenchmark = Form.useWatch('benchmark', form) as string | undefined
  const researchHistory = useResearchHistory(
    [...(holdings ?? []).map((row) => row?.code ?? ''), selectedBenchmark ?? ''],
    period?.[0]?.format('YYYY-MM-DD') ?? '',
    period?.[1]?.format('YYYY-MM-DD') ?? '',
  )
  useEffect(() => {
    setError('')
  }, [researchHistory.selectionKey])
  const weight = (holdings ?? []).reduce((sum, row) => sum + (row?.weight ?? 0), 0)

  async function submit(values: ResearchForm) {
    const weights: Record<string, number> = {}
    for (const holding of values.holdings) {
      const code = normalizeStockCode(holding.code)
      if (!code || weights[code] !== undefined) {
        setError('请选择股票，且每只股票只添加一次')
        return
      }
      weights[code] = holding.weight / 100
    }
    if (weight <= 0 || weight > 100) {
      setError('目标权重合计须大于 0 且不超过 100%')
      return
    }
    const benchmark = values.benchmark?.trim()
      ? normalizeStockCode(values.benchmark)
      : undefined
    if (values.benchmark?.trim() && !benchmark) {
      setError('基准代码无效，请使用 sh.600000 等证券代码')
      return
    }
    setRunning(true)
    setError('')
    try {
      await researchHistory.ensure(
        [...Object.keys(weights), ...(benchmark ? [benchmark] : [])],
        values.period[0].format('YYYY-MM-DD'),
        values.period[1].format('YYYY-MM-DD'),
      )
      const item = await runPortfolioResearch({
        name: values.name,
        weights,
        start_date: values.period[0].format('YYYY-MM-DD'),
        end_date: values.period[1].format('YYYY-MM-DD'),
        initial_capital: values.initial_capital,
        rebalance: values.rebalance,
        benchmark: benchmark || undefined,
        corporate_action_mode: values.corporate_action_mode,
        dividend_tax_rate: values.dividend_tax / 100,
        costs: {
          commission_rate: values.commission / 10000,
          minimum_commission: values.minimum_commission,
          sell_tax_rate: values.sell_tax / 10000,
          transfer_rate: values.transfer / 10000,
          slippage_rate: values.slippage / 10000,
          max_participation: values.participation / 100,
          lot_size: 100,
        },
      })
      openResult(item)
      setPage(1)
      await queryClient.invalidateQueries({ queryKey: ['portfolio-experiments'] })
    } catch (cause) {
      setError(getApiErrorMessage(cause))
    } finally {
      setRunning(false)
    }
  }

  async function perform(label: string, task: () => Promise<void>) {
    setAction(label)
    try {
      await task()
    } catch (cause) {
      message.error(getApiErrorMessage(cause))
    } finally {
      setAction('')
    }
  }

  const result = experiment?.result
  const last = result?.portfolio_values[result.portfolio_values.length - 1]
  return (
    <div className="portfolio-research">
      <PageHeader
        eyebrow="PORTFOLIO LAB"
        title="组合研究"
        subtitle="在同一笔资金下检验目标配置，核对成本、现金与每笔成交。"
      />
      <div className="portfolio-research-grid">
        <ResearchPanel className="portfolio-config" title="目标配置">
          <Form
            form={form}
            layout="vertical"
            onFinish={submit}
            disabled={running || !!action}
            initialValues={{
              name: '组合研究',
              holdings: [{ weight: 50 }, { weight: 50 }],
              period: [dayjs().subtract(1, 'year'), dayjs().subtract(1, 'day')],
              initial_capital: 100000,
              rebalance: 'monthly',
              corporate_action_mode: 'verified',
              dividend_tax: 0,
              commission: 2.5,
              minimum_commission: 5,
              sell_tax: 5,
              transfer: 0.1,
              slippage: 1,
              participation: 10,
            }}
          >
            <Form.Item
              name="name"
              label="实验名称"
              rules={[{ required: true, max: 120 }]}
            >
              <Input maxLength={120} />
            </Form.Item>
            <Form.List name="holdings">
              {(fields, { add, remove }) => (
                <>
                  {fields.map((field, index) => (
                    <div key={field.key} className="portfolio-weight-row">
                      <Form.Item
                        name={[field.name, 'code']}
                        label={`股票 ${index + 1}`}
                        rules={[{ required: true, message: '请选择股票' }]}
                      >
                        <StockSearch />
                      </Form.Item>
                      <Form.Item
                        name={[field.name, 'weight']}
                        label="权重 %"
                        rules={[{ required: true }]}
                      >
                        <InputNumber min={0} max={100} precision={2} />
                      </Form.Item>
                      <Button
                        type="text"
                        aria-label={`移除股票 ${index + 1}`}
                        disabled={fields.length === 1}
                        onClick={() => remove(field.name)}
                      >
                        移除
                      </Button>
                    </div>
                  ))}
                  <div className="portfolio-allocation-total">
                    <Button
                      size="small"
                      disabled={fields.length >= 20}
                      onClick={() => add({ weight: 0 })}
                    >
                      添加股票
                    </Button>
                    <span>
                      股票 {weight.toFixed(2)}% · 现金 {(100 - weight).toFixed(2)}%
                    </span>
                  </div>
                </>
              )}
            </Form.List>
            <Form.Item name="period" label="研究区间" rules={[{ required: true }]}>
              <DatePicker.RangePicker allowClear={false} />
            </Form.Item>
            <div className="portfolio-history-status" role="status" aria-live="polite">
              <span>
                {researchHistory.status === 'idle'
                  ? '选中股票后自动获取所选区间的行情和分红送转'
                  : researchHistory.status === 'ready'
                    ? '所选研究区间的数据已准备完成'
                    : researchHistory.status === 'failed'
                      ? '数据获取失败，可在这里重试'
                      : `正在获取所选区间的行情和分红送转… ${researchHistory.progress}%`}
              </span>
              {researchHistory.status !== 'idle' && (
                <Button
                  size="small"
                  type="text"
                  disabled={researchHistory.status === 'loading' || running}
                  onClick={() => {
                    setError('')
                    void researchHistory.retry()
                  }}
                >
                  {researchHistory.status === 'failed' ? '重试获取' : '重新获取'}
                </Button>
              )}
            </div>
            <div className="portfolio-fields-pair">
              <Form.Item
                name="initial_capital"
                label="初始资金 / 元"
                rules={[{ required: true }]}
              >
                <InputNumber min={1} max={1e12} />
              </Form.Item>
              <Form.Item name="rebalance" label="再平衡频率">
                <Select
                  options={[
                    { value: 'none', label: '仅建仓' },
                    { value: 'daily', label: '每日' },
                    { value: 'weekly', label: '每周' },
                    { value: 'monthly', label: '每月' },
                  ]}
                />
              </Form.Item>
            </div>
            <Form.Item name="benchmark" label="买入持有基准（可选）">
              <Input placeholder="证券代码，如 sh.600000" />
            </Form.Item>
            <Form.Item name="corporate_action_mode" label="分红送转处理">
              <Select
                options={[
                  { value: 'verified', label: '计入已验证的分红送转' },
                  { value: 'price_only', label: '仅价格收益，不计分红送转' },
                ]}
              />
            </Form.Item>
            <Collapse
              ghost
              items={[
                {
                  key: 'costs',
                  forceRender: true,
                  label: '交易成本与容量假设',
                  children: (
                    <div className="portfolio-fields-pair">
                      {(
                        [
                          ['commission', '佣金 / bp', 100],
                          ['minimum_commission', '最低佣金 / 元', 10000],
                          ['sell_tax', '卖出印花税 / bp', 100],
                          ['transfer', '过户费 / bp', 100],
                          ['slippage', '单边滑点 / bp', 9999],
                          ['participation', '前日成交量上限 %', 100],
                          ['dividend_tax', '分红税率 %', 100],
                        ] as const
                      ).map(([name, label, max]) => (
                        <Form.Item
                          key={name}
                          name={name}
                          label={label}
                          rules={[{ required: true }]}
                        >
                          <InputNumber
                            min={name === 'participation' ? 0.01 : 0}
                            max={max}
                          />
                        </Form.Item>
                      ))}
                    </div>
                  ),
                },
              ]}
            />
            <Prose as="p" className="portfolio-note">
              当期首个交易日收盘后确定数量，下一交易日开盘执行。未成交部分当日失效，买入每手
              100 股。
            </Prose>
            {(error || researchHistory.error) && (
              <Alert type="error" message={error || researchHistory.error} showIcon />
            )}
            <Button type="primary" htmlType="submit" loading={running} block>
              运行组合回测
            </Button>
          </Form>
        </ResearchPanel>
        <ResearchPanel className="portfolio-results">
          <div className="portfolio-section-heading">
            <Prose as="h2" ref={resultHeading} tabIndex={-1}>
              {experiment?.name ?? '回测结果'}
            </Prose>
            {experiment && (
              <Space wrap>
                <Button
                  size="small"
                  disabled={!!action || running}
                  loading={action === 'replay'}
                  onClick={() =>
                    perform('replay', async () => {
                      const replay = await replayPortfolioExperiment(
                        experiment.experiment_id,
                      )
                      if (replay.reproduced) message.success('快照重放一致')
                      else message.error('重放结果不一致，请检查实验快照')
                    })
                  }
                >
                  重放核验
                </Button>
                <Button
                  size="small"
                  disabled={!!action || running}
                  loading={action === 'export'}
                  onClick={() =>
                    perform('export', () =>
                      exportPortfolioExperiment(experiment.experiment_id),
                    )
                  }
                >
                  导出实验
                </Button>
              </Space>
            )}
          </div>
          {result && experiment ? (
            <>
              <Prose as="p" className="portfolio-note">
                {experiment.request.start_date} 至 {experiment.request.end_date} ·
                初始资金 {result.initial_capital.toLocaleString('zh-CN')} 元
              </Prose>
              <Prose as="p" className="portfolio-note">
                保存的目标配置：
                {Object.entries(experiment.request.weights)
                  .map(([code, weight]) => `${code} ${(weight * 100).toFixed(2)}%`)
                  .join(' · ')}
              </Prose>
              {experiment.request.corporate_action_mode === 'price_only' && (
                <Alert
                  type="warning"
                  message="此实验仅计算价格收益，未计入分红和送转。"
                />
              )}
              <dl className="portfolio-metrics">
                <div>
                  <dt>组合累计收益</dt>
                  <dd>
                    <PriceChange value={result.metrics.total_return} />
                  </dd>
                </div>
                <div>
                  <dt>最大回撤</dt>
                  <dd>{result.metrics.max_drawdown.toFixed(2)}%</dd>
                </div>
                <div>
                  <dt>相对买入持有超额</dt>
                  <dd>
                    {result.comparison ? (
                      <PriceChange
                        value={result.comparison.excess_return}
                        suffix=" 个百分点"
                      />
                    ) : (
                      '—'
                    )}
                  </dd>
                </div>
                <div>
                  <dt>手续费 / 元</dt>
                  <dd>
                    {result.metrics.total_fees.toLocaleString('zh-CN', {
                      minimumFractionDigits: 2,
                    })}
                  </dd>
                </div>
              </dl>
              <EquityChart result={result} />
              <Prose as="p" className="portfolio-note">
                期末权益 {result.final_capital.toLocaleString('zh-CN')} 元 · 可用现金{' '}
                {last?.cash.toLocaleString('zh-CN')} 元 · 应收分红{' '}
                {last?.receivable.toLocaleString('zh-CN')} 元
              </Prose>
              <Collapse
                ghost
                items={[
                  {
                    key: 'positions',
                    label: '期末持仓',
                    children: (
                      <Table
                        size="small"
                        rowKey="code"
                        pagination={false}
                        dataSource={Object.entries(last?.positions ?? {}).map(
                          ([code, position]) => ({ code, ...position }),
                        )}
                        columns={[
                          { title: '股票', dataIndex: 'code' },
                          { title: '持仓股数', dataIndex: 'quantity', align: 'right' },
                          {
                            title: '待上市股数',
                            dataIndex: 'pending_shares',
                            align: 'right',
                          },
                        ]}
                      />
                    ),
                  },
                  {
                    key: 'trades',
                    label: `成交明细 · ${result.trades.length} 笔`,
                    children: (
                      <Table
                        size="small"
                        rowKey={(_, index) => String(index)}
                        pagination={{ pageSize: 10, size: 'small' }}
                        dataSource={result.trades}
                        scroll={{ x: 580 }}
                        columns={[
                          { title: '日期', dataIndex: 'date' },
                          { title: '股票', dataIndex: 'stock_code' },
                          {
                            title: '方向',
                            dataIndex: 'action',
                            render: (value) => (value === 'buy' ? '买入' : '卖出'),
                          },
                          { title: '股数', dataIndex: 'quantity', align: 'right' },
                          { title: '成交价', dataIndex: 'price', align: 'right' },
                          { title: '费用 / 元', dataIndex: 'fees', align: 'right' },
                        ]}
                      />
                    ),
                  },
                  {
                    key: 'unfilled',
                    label: `未成交记录 · ${result.unfilled_orders.length} 项`,
                    children: (
                      <Table
                        size="small"
                        rowKey={(_, index) => String(index)}
                        pagination={{ pageSize: 10, size: 'small' }}
                        dataSource={result.unfilled_orders}
                        scroll={{ x: 540 }}
                        columns={[
                          { title: '日期', dataIndex: 'date' },
                          { title: '股票', dataIndex: 'stock_code' },
                          { title: '股数', dataIndex: 'quantity', align: 'right' },
                          {
                            title: '原因',
                            dataIndex: 'reason',
                            render: (value) => reasons[value] ?? value,
                          },
                        ]}
                      />
                    ),
                  },
                  {
                    key: 'daily',
                    label: '每日权益账本',
                    children: (
                      <Table
                        size="small"
                        rowKey="date"
                        pagination={{ pageSize: 10, size: 'small' }}
                        dataSource={result.portfolio_values}
                        scroll={{ x: 460 }}
                        columns={[
                          { title: '日期', dataIndex: 'date' },
                          {
                            title: '权益 / 元',
                            dataIndex: 'total_value',
                            align: 'right',
                          },
                          { title: '现金 / 元', dataIndex: 'cash', align: 'right' },
                          {
                            title: '应收 / 元',
                            dataIndex: 'receivable',
                            align: 'right',
                          },
                        ]}
                      />
                    ),
                  },
                  {
                    key: 'assumptions',
                    label: '数据与执行边界',
                    children: (
                      <>
                        <Prose as="p">
                          固定股票集合由你指定，不代表历史时点的选股结果。成本税率采用固定研究假设；日线一字板保守拒绝成交。
                        </Prose>
                        <Prose as="p">
                          基准使用相同初始资金、成本与分红处理，下一交易日开盘买入持有，不等同于指数发布收益。
                        </Prose>
                        <Prose as="p">
                          行情缺失且没有停牌证据时拒绝运行；当前保存的数据为事后观察版本。除权日不调整前日已经确定的委托数量。
                        </Prose>
                        <Prose as="p" className="portfolio-checksum">
                          快照校验码 {experiment.snapshot_sha256}
                        </Prose>
                      </>
                    ),
                  },
                ]}
              />
            </>
          ) : (
            <div className="portfolio-empty" role="status">
              {running
                ? '正在核对原始行情、交易日历和分红证据…'
                : '选择股票与目标权重后运行回测，净值、现金和成交明细将在这里展示。'}
            </div>
          )}
        </ResearchPanel>
      </div>
      <ResearchPanel
        className="portfolio-history"
        title="已保存实验"
        extra={
          <Button size="small" onClick={() => void history.refetch()}>
            刷新
          </Button>
        }
      >
        {history.isError && (
          <Alert type="error" message="实验列表加载失败，请刷新重试" />
        )}
        <Table
          size="small"
          loading={history.isLoading}
          rowKey="experiment_id"
          dataSource={history.data?.items ?? []}
          locale={{ emptyText: '尚未保存组合实验' }}
          scroll={{ x: 540 }}
          pagination={{
            current: page,
            pageSize: 20,
            total: history.data?.total ?? 0,
            onChange: setPage,
            showSizeChanger: false,
            hideOnSinglePage: true,
          }}
          columns={[
            {
              title: '实验',
              dataIndex: 'name',
              render: (name, row) => (
                <Button
                  type="link"
                  disabled={!!action || running}
                  onClick={() =>
                    perform(row.experiment_id, async () =>
                      openResult(await getPortfolioExperiment(row.experiment_id)),
                    )
                  }
                >
                  {name}
                </Button>
              ),
            },
            {
              title: '研究区间',
              render: (_, row) =>
                `${row.request.start_date} 至 ${row.request.end_date}`,
            },
            {
              title: '累计收益',
              align: 'right',
              render: (_, row) => <PriceChange value={row.metrics.total_return} />,
            },
            {
              title: '最大回撤',
              align: 'right',
              render: (_, row) => `${row.metrics.max_drawdown.toFixed(2)}%`,
            },
          ]}
        />
      </ResearchPanel>
    </div>
  )
}
