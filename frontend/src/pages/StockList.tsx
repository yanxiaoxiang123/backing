import { useState, useEffect } from 'react'
import axios from 'axios'
import { Table, Button, message, Modal, Form, Input } from 'antd'
import { SyncOutlined, LineChartOutlined, SearchOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { getJobStatus, getStocks, submitSyncKline, submitSyncStocks } from '../services/api'
import type { Stock } from '../types'
import { logger } from '../utils/logger'

function StockList() {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [stocks, setStocks] = useState<Stock[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [syncing, setSyncing] = useState(false)
  const [syncModalVisible, setSyncModalVisible] = useState(false)
  const [searchText, setSearchText] = useState('')
  const [filteredStocks, setFilteredStocks] = useState<Stock[]>([])

  useEffect(() => {
    loadStocks()
  }, [page, pageSize])

  useEffect(() => {
    if (searchText) {
      const filtered = stocks.filter(
        s => s.code.toLowerCase().includes(searchText.toLowerCase()) ||
             s.name.toLowerCase().includes(searchText.toLowerCase())
      )
      setFilteredStocks(filtered)
    } else {
      setFilteredStocks(stocks)
    }
  }, [searchText, stocks])

  const loadStocks = async () => {
    setLoading(true)
    try {
      const data = await getStocks(undefined, (page - 1) * pageSize, pageSize)
      setStocks(data.items)
      setTotal(data.total)
    } catch (error) {
      message.error('加载股票列表失败')
    } finally {
      setLoading(false)
    }
  }

  const waitForJob = async <T,>(jobId: string, timeoutMs = 300000): Promise<T> => {
    const startTime = Date.now()
    let lastStatus = ''
    while (true) {
      if (Date.now() - startTime > timeoutMs) {
        throw new Error('任务超时，请稍后重试')
      }
      try {
        const job = await getJobStatus<T>(jobId)
        // 调试日志
        if (job.status !== lastStatus) {
          logger.info('Job status:', job.status, job.message)
          lastStatus = job.status
        }
        if (job.status === 'completed') {
          return job.result as T
        }
        if (job.status === 'failed') {
          throw new Error(job.error || job.message || '任务执行失败')
        }
        // 如果状态既不是 completed 也不是 failed，继续等待
        // 但防止无限循环，检查状态是否有效
        if (!['pending', 'running'].includes(job.status)) {
          logger.error('Unknown job status:', job.status)
          throw new Error(`未知任务状态: ${job.status}`)
        }
      } catch (error) {
        // 如果是 404 或网络错误，直接抛出
        if (axios.isAxiosError(error) && error.response?.status === 404) {
          throw new Error('任务不存在，可能服务已重启')
        }
        throw error
      }
      await new Promise(resolve => setTimeout(resolve, 1500))
    }
  }

  const handleSyncStocks = async () => {
    setSyncing(true)
    try {
      const submission = await submitSyncStocks()
      const result = await waitForJob<{ stocks_synced: number; message: string }>(submission.job_id)
      message.success(result.message || `同步完成: ${result.stocks_synced} 只股票`)
      loadStocks()
    } catch (error) {
      message.error((error as Error).message || '同步失败')
    } finally {
      setSyncing(false)
    }
  }

  const handleSyncKline = async () => {
    setSyncModalVisible(true)
  }

  const handleSyncKlineConfirm = async (values: { stockCodes: string; startDate: string; endDate: string }) => {
    setSyncing(true)
    try {
      const codes = values.stockCodes ? values.stockCodes.split(',').map(s => s.trim()) : undefined
      const submission = await submitSyncKline(codes, values.startDate, values.endDate)
      const result = await waitForJob<{ klines_synced: number; message: string }>(submission.job_id)
      message.success(result.message || `同步成功: ${result.klines_synced} 条K线数据`)
    } catch (error) {
      message.error((error as Error).message || '同步失败')
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
      render: (code: string) => <span style={{ color: 'var(--color-accent)', fontWeight: 500 }}>{code}</span>
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
          style={{ color: 'var(--color-accent)' }}
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
      <div className="apple-card" style={{ marginBottom: 'var(--space-md)' }}>
        <div className="flex flex-between" style={{ flexWrap: 'wrap', gap: 'var(--space-md)' }}>
          <div className="flex gap-sm">
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
      <div className="apple-card">
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
          initialValues={{
            startDate: '2020-01-01',
            endDate: new Date().toISOString().split('T')[0]
          }}
        >
          <Form.Item
            name="stockCodes"
            label="股票代码（可选）"
            extra="多个代码用逗号分隔，如: sh.600000,sz.000001"
          >
            <Input placeholder="留空同步所有股票" />
          </Form.Item>
          <Form.Item name="startDate" label="开始日期" rules={[{ required: true }]}>
            <Input type="date" />
          </Form.Item>
          <Form.Item name="endDate" label="结束日期" rules={[{ required: true }]}>
            <Input type="date" />
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
