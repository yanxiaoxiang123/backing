import { useState } from 'react'
import {
  Card,
  Select,
  InputNumber,
  Button,
  Table,
  Tag,
  Space,
  message,
  Spin,
  Switch,
  Descriptions,
  Empty,
} from 'antd'
import { FilterOutlined, SearchOutlined, ReloadOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import type { ColumnsType } from 'antd/es/table'
import { runScreener } from '../services/api'
import type { ScreenerCondition, ScreenerResultItem, ScreenerResponse } from '../types'

const INDICATOR_OPTIONS = [
  { value: 'rsi', label: 'RSI 相对强弱' },
  { value: 'macd_golden_cross', label: 'MACD 金叉' },
  { value: 'macd_death_cross', label: 'MACD 死叉' },
  { value: 'volume_ratio', label: '成交量放量' },
  { value: 'bollinger_bandwidth', label: '布林带宽' },
  { value: 'ma_golden_cross', label: '均线金叉' },
  { value: 'ma_death_cross', label: '均线死叉' },
  { value: 'price_change', label: '涨跌幅' },
  { value: 'close_above_ma', label: '收盘站上均线' },
]

const OPERATOR_OPTIONS: Record<string, { value: string; label: string }[]> = {
  rsi: [
    { value: 'lt', label: '小于' },
    { value: 'gt', label: '大于' },
  ],
  volume_ratio: [
    { value: 'gt', label: '大于' },
    { value: 'lt', label: '小于' },
  ],
  bollinger_bandwidth: [
    { value: 'lt', label: '小于' },
    { value: 'gt', label: '大于' },
  ],
  price_change: [
    { value: 'gt', label: '大于' },
    { value: 'lt', label: '小于' },
  ],
  macd_golden_cross: [{ value: 'cross_above', label: '今日发生' }],
  macd_death_cross: [{ value: 'cross_below', label: '今日发生' }],
  ma_golden_cross: [{ value: 'cross_above', label: '今日发生' }],
  ma_death_cross: [{ value: 'cross_below', label: '今日发生' }],
  close_above_ma: [{ value: 'cross_above', label: '今日上穿' }],
}

const DEFAULT_VALUES: Record<string, number> = {
  rsi: 30,
  volume_ratio: 2.0,
  bollinger_bandwidth: 0.05,
  price_change: 3,
  macd_golden_cross: 1,
  macd_death_cross: 1,
  ma_golden_cross: 1,
  ma_death_cross: 1,
  close_above_ma: 1,
}

const CROSSOVER_INDICATORS = new Set([
  'macd_golden_cross',
  'macd_death_cross',
  'ma_golden_cross',
  'ma_death_cross',
  'close_above_ma',
])

const MARKET_OPTIONS = [
  { value: '', label: '全部市场' },
  { value: 'sh', label: '上海' },
  { value: 'sz', label: '深圳' },
  { value: 'bj', label: '北交所' },
]

function Screener() {
  const navigate = useNavigate()

  const [conditions, setConditions] = useState<ScreenerCondition[]>([
    { indicator: 'rsi', operator: 'lt', value: 30, params: {} },
  ])
  const [logic, setLogic] = useState<'AND' | 'OR'>('AND')
  const [market, setMarket] = useState<string>('')
  const [maxResults, setMaxResults] = useState<number>(100)

  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<ScreenerResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  const addCondition = () => {
    if (conditions.length >= 10) {
      message.warning('最多支持10个条件')
      return
    }
    setConditions([
      ...conditions,
      { indicator: 'rsi', operator: 'lt', value: 30, params: {} },
    ])
  }

  const removeCondition = (index: number) => {
    if (conditions.length <= 1) {
      message.warning('至少保留一个条件')
      return
    }
    setConditions(conditions.filter((_, i) => i !== index))
  }

  const updateCondition = (
    index: number,
    field: keyof ScreenerCondition,
    value: string | number | Record<string, number>,
  ) => {
    const next = [...conditions]
    const cond = { ...next[index] }

    if (field === 'indicator') {
      cond.indicator = value as string
      // reset operator for crossover indicators
      if (CROSSOVER_INDICATORS.has(value as string)) {
        cond.operator = 'cross_above'
        cond.value = 1
      } else {
        const ops = OPERATOR_OPTIONS[value as string]
        if (ops && ops.length > 0) {
          cond.operator = ops[0].value
        }
        cond.value = DEFAULT_VALUES[value as string] ?? 0
      }
    } else if (field === 'operator') {
      cond.operator = value as string
    } else if (field === 'value') {
      cond.value = value as number
    } else if (field === 'params') {
      cond.params = value as Record<string, number>
    }

    next[index] = cond
    setConditions(next)
  }

  const isCrossover = (indicator: string) => CROSSOVER_INDICATORS.has(indicator)

  const handleRun = async () => {
    setLoading(true)
    setError(null)
    setResult(null)

    try {
      const res = await runScreener({
        conditions,
        logic,
        market: market || undefined,
        max_results: maxResults,
      })
      setResult(res)
      if (res.total_matched === 0) {
        message.info('没有符合条件的股票')
      } else {
        message.success(`扫描 ${res.total_stocks_scanned} 只，匹配 ${res.total_matched} 只`)
      }
    } catch (e: any) {
      const msg = e?.response?.data?.detail ?? e?.message ?? '筛选请求失败'
      setError(msg)
      message.error(msg)
    } finally {
      setLoading(false)
    }
  }

  const handleShowPresets = () => {
    setConditions([
      { indicator: 'rsi', operator: 'lt', value: 30, params: {} },
      { indicator: 'volume_ratio', operator: 'gt', value: 1.5, params: {} },
    ])
    setLogic('AND')
  }

  // ---- table columns ----
  const columns: ColumnsType<ScreenerResultItem> = [
    {
      title: '代码',
      dataIndex: 'stock_code',
      key: 'stock_code',
      width: 110,
    },
    {
      title: '名称',
      dataIndex: 'stock_name',
      key: 'stock_name',
      width: 90,
    },
    {
      title: '最新价',
      dataIndex: 'close',
      key: 'close',
      width: 80,
      align: 'right',
      render: (v: number) => v?.toFixed(2),
    },
    {
      title: '涨跌',
      dataIndex: 'change_pct',
      key: 'change_pct',
      width: 70,
      align: 'right',
      render: (v: number | null) => {
        if (v == null) return '-'
        const color = v > 0 ? '#cf1322' : v < 0 ? '#3f8600' : '#666'
        return <span style={{ color }}>{v > 0 ? '+' : ''}{v.toFixed(2)}%</span>
      },
    },
    {
      title: '成交量(手)',
      dataIndex: 'volume',
      key: 'volume',
      width: 100,
      align: 'right',
      render: (v: number) => (v / 100).toFixed(0),
    },
    {
      title: '匹配指标',
      dataIndex: 'indicators',
      key: 'indicators',
      width: 160,
      render: (indicators: Record<string, number | null>, record: ScreenerResultItem) => (
        <Space size={[4, 4]} wrap>
          {record.matched_conditions.map((indicator) => {
            const val = indicators[indicator]
            const label = INDICATOR_OPTIONS.find((o) => o.value === indicator)?.label ?? indicator
            const displayVal = val != null ? (CROSSOVER_INDICATORS.has(indicator) ? '✓' : val.toFixed(2)) : '?'
            return (
              <Tag key={indicator} color="blue">
                {label}: {displayVal}
              </Tag>
            )
          })}
        </Space>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 80,
      fixed: 'right',
      render: (_, record) => (
        <Button
          type="link"
          size="small"
          onClick={() => navigate(`/stocks/${record.stock_code}`)}
        >
          查看
        </Button>
      ),
    },
  ]

  return (
    <div className="screener-page">
      {/* control card */}
      <Card
        title={
          <Space>
            <FilterOutlined />
            <span>股票筛选器</span>
          </Space>
        }
        style={{ marginBottom: 16 }}
      >
        {/* conditions */}
        <div style={{ marginBottom: 16 }}>
          {conditions.map((cond, idx) => (
            <div
              key={idx}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                marginBottom: 8,
                flexWrap: 'wrap',
              }}
            >
              <Select
                value={cond.indicator}
                onChange={(v) => updateCondition(idx, 'indicator', v)}
                options={INDICATOR_OPTIONS}
                style={{ width: 150 }}
              />
              <Select
                value={cond.operator}
                onChange={(v) => updateCondition(idx, 'operator', v)}
                options={OPERATOR_OPTIONS[cond.indicator] ?? []}
                style={{ width: 110 }}
                disabled={isCrossover(cond.indicator)}
              />
              {!isCrossover(cond.indicator) && (
                <InputNumber
                  value={cond.value}
                  onChange={(v) => updateCondition(idx, 'value', v ?? 0)}
                  style={{ width: 100 }}
                  step={cond.indicator === 'price_change' ? 0.5 : cond.indicator === 'volume_ratio' ? 0.1 : 1}
                />
              )}

              {/* extra params for indicator-specific tuning */}
              {cond.indicator === 'rsi' && (
                <Space size={4}>
                  <span style={{ fontSize: 12, color: '#888' }}>周期</span>
                  <InputNumber
                    size="small"
                    min={2}
                    max={100}
                    value={cond.params?.period ?? 14}
                    onChange={(v) =>
                      updateCondition(idx, 'params', { ...cond.params, period: v ?? 14 })
                    }
                    style={{ width: 64 }}
                  />
                </Space>
              )}
              {cond.indicator === 'volume_ratio' && (
                <Space size={4}>
                  <span style={{ fontSize: 12, color: '#888' }}>对比周期</span>
                  <InputNumber
                    size="small"
                    min={2}
                    max={120}
                    value={cond.params?.period ?? 20}
                    onChange={(v) =>
                      updateCondition(idx, 'params', { ...cond.params, period: v ?? 20 })
                    }
                    style={{ width: 64 }}
                  />
                </Space>
              )}
              {(cond.indicator === 'ma_golden_cross' || cond.indicator === 'ma_death_cross') && (
                <Space size={4}>
                  <span style={{ fontSize: 12, color: '#888' }}>短/长</span>
                  <InputNumber
                    size="small"
                    min={2}
                    max={50}
                    value={cond.params?.short ?? 5}
                    onChange={(v) =>
                      updateCondition(idx, 'params', { ...cond.params, short: v ?? 5 })
                    }
                    style={{ width: 60 }}
                  />
                  <InputNumber
                    size="small"
                    min={5}
                    max={200}
                    value={cond.params?.long ?? 20}
                    onChange={(v) =>
                      updateCondition(idx, 'params', { ...cond.params, long: v ?? 20 })
                    }
                    style={{ width: 60 }}
                  />
                </Space>
              )}

              <Button
                type="text"
                danger
                size="small"
                onClick={() => removeCondition(idx)}
                disabled={conditions.length <= 1}
              >
                删除
              </Button>
            </div>
          ))}
        </div>

        {/* controls row */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 16,
            flexWrap: 'wrap',
            marginBottom: 16,
          }}
        >
          <Button onClick={addCondition} size="small" type="dashed">
            + 添加条件
          </Button>
          <Space>
            <span style={{ fontSize: 13 }}>逻辑:</span>
            <Switch
              checkedChildren="AND"
              unCheckedChildren="OR"
              checked={logic === 'AND'}
              onChange={(v) => setLogic(v ? 'AND' : 'OR')}
            />
          </Space>
          <Space size={4}>
            <span style={{ fontSize: 13, color: '#888' }}>市场</span>
            <Select
              value={market}
              onChange={setMarket}
              options={MARKET_OPTIONS}
              style={{ width: 100 }}
              size="small"
            />
          </Space>
          <Space size={4}>
            <span style={{ fontSize: 13, color: '#888' }}>上限</span>
            <InputNumber
              size="small"
              min={10}
              max={500}
              value={maxResults}
              onChange={(v) => setMaxResults(v ?? 100)}
              style={{ width: 80 }}
            />
          </Space>
          <Button onClick={handleShowPresets} size="small">
            超卖+放量
          </Button>
        </div>

        {/* action buttons */}
        <Space>
          <Button
            type="primary"
            icon={<SearchOutlined />}
            onClick={handleRun}
            loading={loading}
          >
            开始筛选
          </Button>
          <Button
            icon={<ReloadOutlined />}
            onClick={() => {
              setResult(null)
              setError(null)
              setConditions([{ indicator: 'rsi', operator: 'lt', value: 30, params: {} }])
              setLogic('AND')
              setMarket('')
            }}
          >
            重置
          </Button>
        </Space>
      </Card>

      {/* loading */}
      {loading && (
        <Card>
          <div style={{ textAlign: 'center', padding: 40 }}>
            <Spin size="large" tip="正在扫描股票..." />
          </div>
        </Card>
      )}

      {/* error */}
      {error && !loading && (
        <Card>
          <Empty description={error} />
        </Card>
      )}

      {/* result summary */}
      {result && !loading && (
        <Card style={{ marginBottom: 16 }}>
          <Descriptions column={4} size="small">
            <Descriptions.Item label="扫描股票数">
              {result.total_stocks_scanned}
            </Descriptions.Item>
            <Descriptions.Item label="匹配数">
              <Tag color="green">{result.total_matched}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="逻辑">{result.logic}</Descriptions.Item>
            <Descriptions.Item label="耗时">
              {result.execution_time_s}s
            </Descriptions.Item>
            <Descriptions.Item label="筛选条件" span={4}>
              <Space size={[4, 4]} wrap>
                {result.conditions_used.map((label) => (
                  <Tag key={label}>{label}</Tag>
                ))}
              </Space>
            </Descriptions.Item>
          </Descriptions>
        </Card>
      )}

      {/* result table */}
      {result && result.results.length > 0 && !loading && (
        <Card title={`筛选结果 (${result.results.length})`}>
          <Table
            columns={columns}
            dataSource={result.results}
            rowKey="stock_code"
            size="small"
            pagination={{ pageSize: 50, showSizeChanger: true, showTotal: (t) => `共 ${t} 只` }}
            scroll={{ x: 700 }}
            onRow={(record) => ({
              onClick: () => navigate(`/stocks/${record.stock_code}`),
              style: { cursor: 'pointer' },
            })}
          />
        </Card>
      )}

      {result && result.results.length === 0 && !loading && (
        <Card>
          <Empty description="没有符合条件的股票，请调整筛选条件后重试。" />
        </Card>
      )}
    </div>
  )
}

export default Screener