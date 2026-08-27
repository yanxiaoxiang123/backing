import { Table } from 'antd'
import type { MenuProps, TableColumnsType, TablePaginationConfig } from 'antd'
import { DeleteOutlined, LineChartOutlined, RobotOutlined } from '@ant-design/icons'
import { PriceChange, RowActionMenu } from './ResearchPrimitives'

export interface InstrumentRow {
  id: string | number
  code: string
  name: string
  currentPrice?: number | null
  change?: number | null
  changePercent?: number | null
  addedAt?: string | null
}

interface InstrumentTableProps {
  rows: InstrumentRow[]
  loading?: boolean
  onOpen?: (row: InstrumentRow) => void
  onResearch?: (row: InstrumentRow) => void
  onRemove?: (row: InstrumentRow) => void
  pagination?: false | TablePaginationConfig
}

export function InstrumentTable({
  rows,
  loading,
  onOpen,
  onResearch,
  onRemove,
  pagination = { pageSize: 10 },
}: InstrumentTableProps) {
  const columns: TableColumnsType<InstrumentRow> = [
    {
      title: '标的',
      key: 'instrument',
      render: (_, row) => (
        <div className="instrument-cell">
          <strong>{row.name || '未命名标的'}</strong>
          <span>{row.code}</span>
        </div>
      ),
    },
    {
      title: '最新价',
      dataIndex: 'currentPrice',
      key: 'currentPrice',
      align: 'right',
      render: (value: number | null | undefined) =>
        value == null ? <span className="price-flat">—</span> : value.toFixed(2),
    },
    {
      title: '涨跌额',
      dataIndex: 'change',
      key: 'change',
      align: 'right',
      render: (value: number | null | undefined) => (
        <PriceChange value={value} suffix="" />
      ),
    },
    {
      title: '涨跌幅',
      dataIndex: 'changePercent',
      key: 'changePercent',
      align: 'right',
      render: (value: number | null | undefined) => <PriceChange value={value} />,
    },
    {
      title: '加入时间',
      dataIndex: 'addedAt',
      key: 'addedAt',
      render: (value: string | null | undefined) =>
        value ? new Date(value).toLocaleDateString('zh-CN') : '—',
    },
    ...(onOpen || onResearch || onRemove
      ? [
          {
            title: '操作',
            key: 'actions',
            align: 'right' as const,
            render: (_: unknown, row: InstrumentRow) => {
              const items: MenuProps['items'] = [
                onOpen
                  ? {
                      key: 'open',
                      icon: <LineChartOutlined />,
                      label: '查看个股',
                      onClick: () => onOpen(row),
                    }
                  : null,
                onResearch
                  ? {
                      key: 'research',
                      icon: <RobotOutlined />,
                      label: 'Agent 研究',
                      onClick: () => onResearch(row),
                    }
                  : null,
                onRemove
                  ? {
                      key: 'remove',
                      danger: true,
                      icon: <DeleteOutlined />,
                      label: '移除自选',
                      onClick: () => onRemove(row),
                    }
                  : null,
              ].filter(Boolean) as MenuProps['items']
              return (
                <RowActionMenu
                  items={items}
                  label={`打开 ${row.name || row.code} 操作菜单`}
                />
              )
            },
          },
        ]
      : []),
  ]

  return (
    <Table<InstrumentRow>
      className="instrument-table"
      columns={columns}
      dataSource={rows}
      rowKey="id"
      loading={loading}
      pagination={pagination}
      locale={{ emptyText: '暂无标的' }}
      onRow={(row) => ({
        className: 'research-clickable-row',
        tabIndex: 0,
        role: onOpen ? 'link' : undefined,
        'aria-label': onOpen ? `查看 ${row.name || row.code}` : undefined,
        onClick: () => onOpen?.(row),
        onKeyDown: (event) => {
          if (onOpen && (event.key === 'Enter' || event.key === ' ')) {
            event.preventDefault()
            onOpen(row)
          }
        },
      })}
    />
  )
}
