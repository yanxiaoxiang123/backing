import { Card, InputNumber, DatePicker, Button, Empty, Slider, Select } from 'antd'
import {
  LoadingOutlined,
  PlayCircleOutlined,
  ThunderboltOutlined,
  BarChartOutlined,
} from '@ant-design/icons'
import type { StrategyInfo } from '../../types'
import StockSearch from '../StockSearch'
import dayjs from 'dayjs'

const { RangePicker } = DatePicker

interface StrategyConfigProps {
  strategies: StrategyInfo[]
  selectedStrategy: string | null
  stockCode: string | null
  dateRange: [string, string]
  initialCapital: number
  parameters: Record<string, number | string>
  priceSource: 'raw' | 'legacy'
  corporateActionMode: 'price_only' | 'verified'
  dividendTaxRate: number
  loadingData: boolean
  onPriceSourceChange: (value: 'raw' | 'legacy') => void
  onCorporateActionModeChange: (value: 'price_only' | 'verified') => void
  onDividendTaxRateChange: (value: number) => void
  onSyncData: () => void
  loading: { signals: boolean; backtest: boolean; optimize: boolean; compare: boolean }
  onStockCodeChange: (code: string) => void
  onDateRangeChange: (range: [string, string]) => void
  onCapitalChange: (capital: number) => void
  onParameterChange: (params: Record<string, number | string>) => void
  onGenerateSignals: () => void
  onRunBacktest: () => void
  onOptimize: () => void
  onCompare: () => void
}

function renderParameterInputs(
  strategy: StrategyInfo,
  parameters: Record<string, number | string>,
  onChange: (params: Record<string, number | string>) => void,
) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
      {Object.entries(strategy.parameters).map(([key, config]) => (
        <div key={key}>
          <label
            style={{
              display: 'block',
              fontSize: 'var(--font-size-sm)',
              color: 'var(--color-text-secondary)',
              marginBottom: 'var(--space-xs)',
            }}
          >
            {key}
            {config.description && (
              <span style={{ marginLeft: 8, fontWeight: 400 }}>
                ({config.description})
              </span>
            )}
          </label>
          {config.type === 'slider' && (
            <div
              style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-md)' }}
            >
              <Slider
                min={config.min}
                max={config.max}
                step={config.step}
                value={Number(parameters[key] ?? config.default)}
                onChange={(value) => onChange({ ...parameters, [key]: Number(value) })}
                style={{ flex: 1 }}
              />
              <InputNumber
                min={config.min}
                max={config.max}
                step={config.step}
                value={Number(parameters[key] ?? config.default)}
                onChange={(value) =>
                  onChange({ ...parameters, [key]: Number(value ?? 0) })
                }
                style={{ width: 80 }}
              />
            </div>
          )}
          {config.type === 'input' && (
            <InputNumber
              min={config.min}
              max={config.max}
              step={config.step}
              value={Number(parameters[key] ?? config.default)}
              onChange={(value) =>
                onChange({ ...parameters, [key]: Number(value ?? 0) })
              }
              style={{ width: '100%' }}
            />
          )}
          {config.type === 'select' && config.options && (
            <Select
              value={parameters[key] ?? config.default}
              onChange={(value) => onChange({ ...parameters, [key]: value })}
              style={{ width: '100%' }}
              options={config.options.map((opt) => ({
                value: opt.value,
                label: opt.label,
              }))}
            />
          )}
        </div>
      ))}
    </div>
  )
}

export function StrategyConfig({
  strategies,
  selectedStrategy,
  stockCode,
  dateRange,
  initialCapital,
  parameters,
  priceSource,
  corporateActionMode,
  dividendTaxRate,
  loadingData,
  onPriceSourceChange,
  onCorporateActionModeChange,
  onDividendTaxRateChange,
  onSyncData,
  loading,
  onStockCodeChange,
  onDateRangeChange,
  onCapitalChange,
  onParameterChange,
  onGenerateSignals,
  onRunBacktest,
  onOptimize,
  onCompare,
}: StrategyConfigProps) {
  const selectedStrategyInfo = strategies.find((s) => s.name === selectedStrategy)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-lg)' }}>
      {/* Strategy Parameters */}
      <Card title="策略参数" style={{ opacity: selectedStrategy ? 1 : 0.6 }}>
        {selectedStrategyInfo ? (
          renderParameterInputs(selectedStrategyInfo, parameters, onParameterChange)
        ) : (
          <Empty description="请选择策略" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        )}
      </Card>

      {/* Backtest Configuration */}
      <Card title="回测配置">
        <div
          style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}
        >
          <div>
            <label
              style={{
                display: 'block',
                fontSize: 'var(--font-size-sm)',
                color: 'var(--color-text-secondary)',
                marginBottom: 'var(--space-xs)',
              }}
            >
              股票代码
            </label>
            <StockSearch value={stockCode ?? undefined} onChange={onStockCodeChange} />
          </div>

          <div>
            <label
              style={{
                display: 'block',
                fontSize: 'var(--font-size-sm)',
                color: 'var(--color-text-secondary)',
                marginBottom: 'var(--space-xs)',
              }}
            >
              回测区间
            </label>
            <RangePicker
              disabledDate={(current) => current.isAfter(dayjs(), 'day')}
              value={[dayjs(dateRange[0]), dayjs(dateRange[1])]}
              onChange={(dates) => {
                if (dates) {
                  onDateRangeChange([
                    dates[0]!.format('YYYY-MM-DD'),
                    dates[1]!.format('YYYY-MM-DD'),
                  ])
                }
              }}
              style={{ width: '100%' }}
            />
          </div>

          <div>
            <label
              style={{
                display: 'block',
                fontSize: 'var(--font-size-sm)',
                color: 'var(--color-text-secondary)',
                marginBottom: 'var(--space-xs)',
              }}
            >
              初始资金
            </label>
            <InputNumber
              value={initialCapital}
              onChange={(value) => onCapitalChange(value ?? 100000)}
              min={10000}
              step={10000}
              style={{ width: '100%' }}
              formatter={(value) => `${value}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}
              parser={(value) => Number(value!.replace(/\$\s?|(,*)/g, ''))}
            />
          </div>

          <div>
            <label htmlFor="research-price-source">历史行情口径</label>
            <Select
              id="research-price-source"
              value={priceSource}
              onChange={onPriceSourceChange}
              style={{ width: '100%' }}
              options={[
                { value: 'raw', label: '原始价格 · 按交易日历核验' },
                { value: 'legacy', label: '旧行情 · 复权口径未知' },
              ]}
            />
          </div>
          <div>
            <label htmlFor="research-corporate-actions">收益计算</label>
            <Select
              id="research-corporate-actions"
              value={priceSource === 'legacy' ? 'price_only' : corporateActionMode}
              disabled={priceSource === 'legacy'}
              onChange={onCorporateActionModeChange}
              style={{ width: '100%' }}
              options={[
                { value: 'verified', label: '含分红送转 · 核对登记及到账日期' },
                { value: 'price_only', label: '仅价格收益 · 不计分红送转' },
              ]}
            />
          </div>
          {priceSource === 'raw' && corporateActionMode === 'verified' ? (
            <div>
              <label htmlFor="research-dividend-tax">分红税率假设（%）</label>
              <InputNumber
                id="research-dividend-tax"
                value={dividendTaxRate * 100}
                min={0}
                max={100}
                onChange={(value) => onDividendTaxRateChange((value ?? 0) / 100)}
                style={{ width: '100%' }}
              />
              <small>固定研究假设；0 表示税前收益。</small>
            </div>
          ) : null}
          <Button disabled={!stockCode} loading={loadingData} onClick={onSyncData}>
            补齐研究数据
          </Button>

          <div
            style={{
              display: 'flex',
              gap: 'var(--space-sm)',
              marginTop: 'var(--space-md)',
            }}
          >
            <Button
              type="primary"
              icon={<LoadingOutlined spin={loading.signals} />}
              onClick={onGenerateSignals}
              loading={loading.signals}
              disabled={!selectedStrategy || !stockCode}
              style={{ flex: 1 }}
            >
              生成信号
            </Button>
            <Button
              type="primary"
              icon={<PlayCircleOutlined />}
              onClick={onRunBacktest}
              loading={loading.backtest}
              disabled={!selectedStrategy || !stockCode}
              style={{ flex: 1 }}
            >
              执行回测
            </Button>
            <Button
              icon={<ThunderboltOutlined />}
              onClick={onOptimize}
              loading={loading.optimize}
              disabled={!selectedStrategy || !stockCode}
            >
              参数优化
            </Button>
          </div>
          <div style={{ marginTop: 'var(--space-sm)' }}>
            <Button
              type="primary"
              danger
              icon={<BarChartOutlined />}
              onClick={onCompare}
              loading={loading.compare}
              disabled={!stockCode}
              block
            >
              一键对比所有策略
            </Button>
          </div>
        </div>
      </Card>
    </div>
  )
}
