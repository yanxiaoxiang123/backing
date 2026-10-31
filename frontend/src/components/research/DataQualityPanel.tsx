import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Alert, Button, Space } from 'antd'

import { getDataQuality, syncRawHistory } from '../../services/marketData'
import { getApiErrorMessage } from '../../services/api'
import { useJobPolling } from '../../hooks/useJobPolling'

export function DataQualityPanel({ codes }: { codes: string[] }) {
  const queryClient = useQueryClient()
  const quality = useQuery({
    queryKey: ['market-data-quality'],
    queryFn: getDataQuality,
    staleTime: 30000,
  })
  const [running, setRunning] = useState(false)
  const [notice, setNotice] = useState('')
  const [failure, setFailure] = useState('')
  const { waitForJob } = useJobPolling({ timeoutMs: 3600000 })
  const sync = async () => {
    setRunning(true)
    setFailure('')
    setNotice('正在提交原始价格补数任务')
    try {
      const jobId = await syncRawHistory(codes)
      setNotice(`任务 ${jobId} 正在补数，进度保存在后台任务中`)
      await waitForJob(jobId)
      setNotice('补数完成，已核对交易日历覆盖')
    } catch (error) {
      setFailure(getApiErrorMessage(error))
      setNotice('')
    } finally {
      setRunning(false)
      void queryClient.invalidateQueries({ queryKey: ['market-data-quality'] })
    }
  }
  const data = quality.data
  return (
    <section className="research-panel data-quality-panel" aria-label="历史数据质量">
      <div className="data-quality-panel__heading">
        <div>
          <strong>历史数据覆盖</strong>
          <p>按交易日历核对原始行情与停牌，补齐分红送转及复权因子。</p>
        </div>
        <Space wrap>
          <Button onClick={() => void quality.refetch()} loading={quality.isFetching}>
            刷新数据质量
          </Button>
          <Button
            disabled={!codes.length}
            loading={running}
            onClick={() => void sync()}
          >
            补齐本页原始价格
          </Button>
        </Space>
      </div>
      {quality.isLoading ? <p role="status">正在读取数据覆盖</p> : null}
      {quality.isError ? (
        <Alert type="error" message="数据质量读取失败，请刷新重试" />
      ) : null}
      {data ? (
        <dl className="data-quality-panel__facts">
          <div>
            <dt>旧 K 线覆盖</dt>
            <dd>
              {data.covered_stocks.toLocaleString()} /{' '}
              {data.total_stocks.toLocaleString()} 只
            </dd>
          </div>
          <div>
            <dt>原始价格覆盖</dt>
            <dd>{data.raw_covered_stocks.toLocaleString()} 只</dd>
          </div>
          <div>
            <dt>版本化行情记录</dt>
            <dd>{data.versioned_bars.toLocaleString()} 根</dd>
          </div>
          <div>
            <dt>异常旧 K 线</dt>
            <dd>{data.invalid_bars.toLocaleString()} 根</dd>
          </div>
        </dl>
      ) : null}
      {notice ? <p role="status">{notice}</p> : null}
      {failure ? <Alert type="error" message={failure} /> : null}
    </section>
  )
}
