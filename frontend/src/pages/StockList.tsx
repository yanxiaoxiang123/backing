import { useState, useEffect } from 'react'
import { Table, Button, message, Modal, Form, Input, Select } from 'antd'
import { SyncOutlined, LineChartOutlined, SearchOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { getStocks, submitSyncKline, submitSyncStocks, getApiErrorMessage } from '../services/api'
import { useJobPolling } from '../hooks/useJobPolling'
import type { Stock } from '../types'

function StockList() {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [syncing, setSyncing] = useState(false)
  const [syncModalVisible, setSyncModalVisible] = useState(false)
  const [searchText, setSearchText] = useState('')
  const [filteredStocks, setFilteredStocks] = useState<Stock[]>([])

  useEffect(() => {
    setPage(1)
  }, [searchText])

  useEffect(() => {
    loadStocks()
  }, [page, pageSize, searchText])

  const loadStocks = async () => {
    setLoading(true)
    try {
      const data = await getStocks(undefined, (page - 1) * pageSize, pageSize, searchText || undefined)
      setFilteredStocks(data.items)
      setTotal(data.total)
    } catch (error) {
      message.error(getApiErrorMessage(error))
    } finally {
      setLoading(false)
    }
  }

  // 统一任务轮询（5 分钟超时；卸载自动取消）
  const { waitForJob } = useJobPolling({ timeoutMs: 300000 })

  const handleSyncStocks = async () => {
    setSyncing(true)
    try {
      const submission = await submitSyncStocks()
      const result = await waitForJob<{ stocks_synced: number; message: string }>(submission.job_id)
      message.success(result.message || `同步完成: ${result.stocks_synced} 只股票`)
      loadStocks()
    } catch (error) {
      message.error(getApiErrorMessage(error))
    } finally {
      setSyncing(false)
    }
  }

  const handleSyncKline = async () => {
    setSyncModalVisible(true)
  }

  const handleSyncKlineConfirm = async (values: { stockCodes: string; strategy: string }) => {
    setSyncing(true)
    try {
      const codes = values.stockCodes ? values.stockCodes.split(',').map(s => s.trim()) : undefined
      const submission = await submitSyncKline(codes, values.strategy as 'incremental' | 'full')
      const result = await waitForJob<{ klines_synced: number; message: string }>(submission.job_id)
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

  const columns = [
    {
      title: '代码',
      dataIndex: 'code',
      key: 'code',
      width: 100,
      render: (code: string) => <span style={{ color: 'var(--color-ink)', fontWeight: 500 }}>{code}</span>
    },
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      width: 120
    },
    {
      title: '市场',
      dataIndex: 'market',
      key: 'market',
      width: 80,
      render: (market: string) => market === 'sh' ? '上海' : '深圳'
    },
    {
      title: '上市日期',
      dataIndex: 'list_date',
      key: 'list_date',
      width: 120,
      render: (date: string) => date || '-'
    },
    {
      title: '操作',
      key: 'action',
      width: 100,
      render: (_: unknown, record: Stock) => (
        <Button
          type="text"
          icon={<LineChartOutlined />}
          onClick={(e) => {
            e.stopPropagation()
            handleViewChart(record)
          }}
          style={{ color: 'var(--color-ink)' }}
        >
          K线
        </Button>
      )
    }
  ]

  return (
    <div className="fade-in">
      {/* 页面标题 */}
      <div className="page-header">
        <h1 className="page-title">股票管理</h1>
        <p className="page-subtitle">管理您的股票数据</p>
      </div>

      {/* 操作栏 */}
      <div style={{ background: 'var(--color-canvas-lifted)', borderRadius: 'var(--radius-card)', padding: 'var(--space-lg)', marginBottom: 'var(--space-md)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 'var(--space-md)' }}>
          <div style={{ display: 'flex', gap: 'var(--space-sm)' }}>
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
            prefix={<SearchOutlined style={{ color: 'var(--color-text-tertiary)' }} />}
            allowClear
            style={{ width: 240 }}
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
          />
        </div>
      </div>

      {/* 股票列表 */}
      <div style={{ background: 'var(--color-canvas-lifted)', borderRadius: 'var(--radius-card)', overflow: 'hidden' }}>
        <Table
          columns={columns}
          dataSource={filteredStocks}
          rowKey="id"
          loading={loading}
          onRow={(record) => ({
            onClick: () => handleViewChart(record),
            style: { cursor: 'pointer' }
          })}
          pagination={{
            current: page,
            pageSize: pageSize,
            total: searchText ? filteredStocks.length : total,
            onChange: (p, ps) => {
              setPage(p)
              setPageSize(ps)
            },
            showSizeChanger: true,
            showTotal: (t) => `共 ${t} 条`
          }}
        />
      </div>

      {/* 同步K线 Modal */}
      <Modal
        title="同步K线数据"
        open={syncModalVisible}
        onCancel={() => setSyncModalVisible(false)}
        footer={null}
        centered
      >
        <Form
          layout="vertical"
          onFinish={handleSyncKlineConfirm}
        >
          <Form.Item
            name="stockCodes"
            label="股票代码（可选）"
            extra="多个代码用逗号分隔，如: sh.600000,sz.000001。留空则同步所有股票。"
          >
            <Input placeholder="留空同步所有股票" />
          </Form.Item>
          <Form.Item name="strategy" label="同步策略">
            <Select>
              <Select.Option value="incremental">增量同步（有数据则从最新日期更新）</Select.Option>
              <Select.Option value="full">全量同步（重新拉取2020年至今所有数据）</Select.Option>
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
