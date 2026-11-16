import { LoadingOutlined, ReloadOutlined } from '@ant-design/icons'
import { Button } from 'antd'

/** Refreshing never replaces or fades the data already being read. */
export function QueryStatus({
  fetching,
  onRefresh,
  label = '更新中',
}: {
  fetching: boolean
  onRefresh?: () => void
  label?: string
}) {
  return (
    <div className="query-status" aria-live="polite">
      {fetching ? (
        <span role="status">
          <LoadingOutlined spin role="presentation" aria-hidden="true" /> {label}
        </span>
      ) : onRefresh ? (
        <Button
          type="text"
          size="small"
          icon={<ReloadOutlined role="presentation" aria-hidden="true" />}
          onClick={onRefresh}
          aria-label="刷新记录"
        >
          刷新
        </Button>
      ) : null}
    </div>
  )
}
