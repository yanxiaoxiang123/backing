import { Prose } from '../Prose'
import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Alert, Button, Modal, Space } from 'antd'

import { getDataQuality, syncRawHistory } from '../../services/marketData'
import { getApiErrorMessage } from '../../services/api'
import { useJobPolling } from '../../hooks/useJobPolling'

export function DataQualityPanel({
  codes,
  compact = false,
}: {
  codes: string[]
  compact?: boolean
}) {
  const queryClient = useQueryClient()
  const quality = useQuery({
    queryKey: ['market-data-quality'],
    queryFn: getDataQuality,
    staleTime: 30000,
  })
  const [running, setRunning] = useState(false)
  const [notice, setNotice] = useState('')
  const [failure, setFailure] = useState('')
  const [detailsOpen, setDetailsOpen] = useState(false)
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
  const content = (
    <>
      <div className="data-quality-panel__heading">
        <div>
          <strong>历史数据覆盖</strong>
          <Prose as="p">按交易日历核对原始行情与停牌，补齐分红送转及复权因子。</Prose>
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
      {quality.isLoading ? (
        <Prose as="p" role="status">
          正在读取数据覆盖
        </Prose>
      ) : null}
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
      {notice ? (
        <Prose
          as="p"
          className="data-quality-panel__notice"
          role="status"
          title={notice}
        >
          {notice}
        </Prose>
      ) : null}
      {failure ? <Alert type="error" message={failure} /> : null}
    </>
  )
  if (compact)
    return (
      <>
        <section
          className="research-panel stock-quality-summary"
          aria-label="历史数据质量"
        >
          <div>
            <strong>历史数据覆盖</strong>
            <span title={failure || notice || undefined}>
              {failure
                ? '补数失败，可打开详情重试'
                : notice ||
                  (data
                    ? `旧 K 线 ${data.covered_stocks.toLocaleString()} / ${data.total_stocks.toLocaleString()} · 原始价格 ${data.raw_covered_stocks.toLocaleString()} 只`
                    : quality.isError
                      ? '数据质量读取失败'
                      : '正在读取数据覆盖')}
            </span>
          </div>
          <Button onClick={() => setDetailsOpen(true)}>详情与补数</Button>
        </section>
        <Modal
          title="历史数据覆盖"
          open={detailsOpen}
          footer={null}
          onCancel={() => setDetailsOpen(false)}
          centered
        >
          <div className="data-quality-panel stock-quality-details">{content}</div>
        </Modal>
      </>
    )
  return (
    <section className="research-panel data-quality-panel" aria-label="历史数据质量">
      {content}
    </section>
  )
}
