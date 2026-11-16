import { Prose } from '../Prose'
import { Table, Tag } from 'antd'
import type { DLBacktest, DLForecast } from '../../services/dl'
import { FinancialValue } from '../research/FinancialValue'
import { formatNumber, tradeAction } from '../../utils/dataFormat'

export function DLForecastDetails({ result }: { result: DLForecast }) {
  return (
    <details className="dl-details">
      <summary>逐日预测与 K 线明细</summary>
      <div className="dl-details-body">
        {(result.forecast_target === 'close' || result.model === 'timesfm-2.5') && (
          <Prose as="p">
            TimesFM 收盘价点预测，未生成开盘、最高、最低、成交量或成交额。
          </Prose>
        )}
        <Prose as="h3">未来 {result.prediction_dates.length} 个交易日预测</Prose>
        <Table
          dataSource={result.prediction_dates.map((date, index) => {
            const previous = index
              ? result.predicted_prices[index - 1]
              : result.current_price
            return {
              date,
              price: result.predicted_prices[index],
              change: previous
                ? ((result.predicted_prices[index] - previous) / previous) * 100
                : null,
            }
          })}
          rowKey="date"
          size="small"
          pagination={false}
          columns={[
            { title: '日期', dataIndex: 'date' },
            {
              title: '预测价格',
              dataIndex: 'price',
              align: 'right',
              render: (value?: number) => formatNumber(value),
            },
            {
              title: '涨跌幅',
              dataIndex: 'change',
              align: 'right',
              render: (value: number | null) => <FinancialValue value={value} />,
            },
          ]}
        />
        {result.predicted_klines && (
          <>
            <Prose as="h3">预测 K 线明细</Prose>
            <Prose as="p">
              三条采样路径的均值，非统计置信区间；不满足 OHLC 约束的输出保留并标记。
            </Prose>
            <Table
              dataSource={result.predicted_klines}
              rowKey="date"
              size="small"
              scroll={{ x: 680 }}
              pagination={false}
              columns={[
                { title: '日期', dataIndex: 'date', width: 110 },
                ...(['open', 'high', 'low', 'close'] as const).map((field, index) => ({
                  title: ['开盘', '最高', '最低', '收盘'][index],
                  dataIndex: field,
                  align: 'right' as const,
                  render: (value: number) => formatNumber(value),
                })),
                {
                  title: '成交量/股',
                  dataIndex: 'volume',
                  align: 'right',
                  render: (value: number) => formatNumber(value, 0),
                },
                {
                  title: '成交额/元',
                  dataIndex: 'amount',
                  align: 'right',
                  render: (value?: number) => formatNumber(value, 0),
                },
                {
                  title: '校验',
                  dataIndex: 'ohlc_valid',
                  render: (value?: boolean) =>
                    value === undefined ? '—' : value ? '有效' : 'OHLC 无效',
                },
              ]}
            />
          </>
        )}
      </div>
    </details>
  )
}

export function DLBacktestDetails({ result }: { result: DLBacktest }) {
  return (
    <details className="dl-details">
      <summary>交易记录（{result.total_trades}）</summary>
      <div className="dl-details-body">
        <Table
          dataSource={result.trades}
          rowKey={(record) => `${record.date}-${record.action}-${record.price}`}
          size="small"
          pagination={{ pageSize: 10 }}
          scroll={{ x: 620, y: 300 }}
          columns={[
            { title: '日期', dataIndex: 'date' },
            {
              title: '操作',
              dataIndex: 'action',
              render: (action: string) => (
                <Tag className={tradeAction(action).className}>
                  {tradeAction(action).label}
                </Tag>
              ),
            },
            {
              title: '价格',
              dataIndex: 'price',
              align: 'right',
              render: (value: number) => formatNumber(value),
            },
            { title: '数量', dataIndex: 'quantity', align: 'right' },
            {
              title: '金额',
              align: 'right',
              render: (_, record) =>
                formatNumber(
                  record.action === 'BUY'
                    ? (record.cost ?? record.price * record.quantity)
                    : (record.revenue ?? record.price * record.quantity),
                ),
            },
            {
              title: '收益率',
              align: 'right',
              render: (_, record) =>
                record.action === 'BUY' || record.return === undefined ? (
                  '—'
                ) : (
                  <FinancialValue value={record.return} />
                ),
            },
          ]}
        />
      </div>
    </details>
  )
}
