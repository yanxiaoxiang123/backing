import { Prose } from '../Prose'
import { formatNumber, isFiniteNumber, numberTone } from '../../utils/dataFormat'
import type { ReactNode } from 'react'
import { Alert, Button, Empty, Progress, Skeleton, Tag } from 'antd'
import { MoreOutlined, ReloadOutlined } from '@ant-design/icons'
import type { MenuProps } from 'antd'
import { Dropdown } from 'antd'

export function PageHeader({
  eyebrow,
  title,
  subtitle,
  actions,
}: {
  eyebrow?: string
  title: ReactNode
  subtitle?: ReactNode
  actions?: ReactNode
}) {
  return (
    <header className="research-page-header page-header">
      <div>
        {eyebrow ? <div className="eyebrow">{eyebrow}</div> : null}
        <Prose as="h1" className="page-title">
          {title}
        </Prose>
        {subtitle ? (
          <Prose as="p" className="page-subtitle">
            {subtitle}
          </Prose>
        ) : null}
      </div>
      {actions ? <div className="page-actions">{actions}</div> : null}
    </header>
  )
}

export function ResearchPanel({
  children,
  className = '',
  as: Component = 'section',
  title,
  extra,
}: {
  children: ReactNode
  className?: string
  as?: 'section' | 'div' | 'aside'
  title?: ReactNode
  extra?: ReactNode
}) {
  return (
    <Component className={`research-panel ${className}`.trim()}>
      {title ? (
        <>
          <div className="research-panel-heading">
            <Prose as="h2">{title}</Prose>
            {extra}
          </div>
          <div className="research-panel-body">{children}</div>
        </>
      ) : (
        children
      )}
    </Component>
  )
}

export function AsyncBoundary({
  loading,
  loadingRows = 4,
  error,
  onRetry,
  empty,
  children,
}: {
  loading?: boolean
  loadingRows?: number
  error?: unknown
  onRetry?: () => void
  empty?: boolean
  children: ReactNode
}) {
  if (loading) {
    return (
      <div className="async-boundary" aria-busy="true" aria-live="polite">
        <Skeleton active paragraph={{ rows: loadingRows }} aria-label="正在加载" />
      </div>
    )
  }
  if (error) {
    return (
      <Alert
        type="error"
        showIcon
        message="暂时无法加载"
        action={
          onRetry ? (
            <Button icon={<ReloadOutlined />} onClick={onRetry}>
              重试
            </Button>
          ) : undefined
        }
      />
    )
  }
  if (empty)
    return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无数据" />
  return <>{children}</>
}

export function PriceChange({
  value,
  suffix = '%',
  digits = 2,
}: {
  value: number | null | undefined
  suffix?: string
  digits?: number
}) {
  if (!isFiniteNumber(value)) return <span className="price-flat">—</span>
  const className = numberTone(value, digits)
  return (
    <span className={className}>
      {className === 'price-up' ? '+' : ''}
      {formatNumber(value, digits)}
      {suffix}
    </span>
  )
}

export function MetricCard({
  label,
  value,
  detail,
  tone = 'neutral',
}: {
  label: ReactNode
  value: ReactNode
  detail?: ReactNode
  tone?: 'neutral' | 'up' | 'down' | 'warning'
}) {
  return (
    <article className={`metric-card metric-card--${tone}`}>
      <span className="metric-card__label">{label}</span>
      <strong className="metric-card__value">{value}</strong>
      {detail ? <span className="metric-card__detail">{detail}</span> : null}
    </article>
  )
}

export function EmptyState({
  description = '暂无数据',
  action,
}: {
  description?: ReactNode
  action?: ReactNode
}) {
  return (
    <div className="research-empty-state">
      <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={description} />
      {action ? <div className="research-empty-state__action">{action}</div> : null}
    </div>
  )
}

export function JobProgressPanel({
  title,
  progress,
  message,
  detail,
  onCancel,
}: {
  title: ReactNode
  progress: number
  message?: ReactNode
  detail?: ReactNode
  onCancel?: () => void
}) {
  return (
    <section className="job-progress-panel" aria-live="polite" aria-busy="true">
      <div className="job-progress-panel__heading">
        <strong>{title}</strong>
        <span>{Math.round(progress)}%</span>
      </div>
      <Progress percent={Math.max(0, Math.min(100, progress))} showInfo={false} />
      {message ? <Prose as="p">{message}</Prose> : null}
      {detail ? <small>{detail}</small> : null}
      {onCancel ? (
        <Button size="small" onClick={onCancel}>
          取消任务
        </Button>
      ) : null}
    </section>
  )
}

export function ResearchResultCard({
  code,
  name,
  price,
  changePercent,
  signal,
  confidence,
  summary,
  metadata,
  actions,
}: {
  code: string
  name: string
  price?: number | null
  changePercent?: number | null
  signal?: string
  confidence?: number | null
  summary?: ReactNode
  metadata?: ReactNode
  actions?: ReactNode
}) {
  const signalLabel = signal === 'buy' ? '买入' : signal === 'sell' ? '卖出' : '持有'
  const signalTone = signal === 'buy' ? 'buy' : signal === 'sell' ? 'sell' : 'neutral'
  return (
    <article className={`research-result-card research-result-card--${signalTone}`}>
      <div className="research-result-card__identity">
        <strong>{name || code}</strong>
        <span>{code}</span>
      </div>
      <div className="research-result-card__quote">
        <strong>{price == null ? '—' : price.toFixed(2)}</strong>
        <PriceChange value={changePercent} />
      </div>
      <div className="research-result-card__signal">
        {signal ? (
          <Tag className={`research-signal-tag research-signal-tag--${signalTone}`}>
            {signalLabel}
          </Tag>
        ) : null}
        {confidence != null ? (
          <small>置信度 {Math.round(confidence * 100)}%</small>
        ) : null}
      </div>
      <div className="research-result-card__summary">{summary || '暂无研究摘要'}</div>
      {metadata ? (
        <div className="research-result-card__metadata">{metadata}</div>
      ) : null}
      {actions ? <div className="research-result-card__actions">{actions}</div> : null}
    </article>
  )
}

export function RowActionMenu({
  label,
  items,
}: {
  label: string
  items: MenuProps['items']
}) {
  return (
    <Dropdown
      menu={{ items, onClick: ({ domEvent }) => domEvent.stopPropagation() }}
      trigger={['click']}
    >
      <Button
        type="text"
        icon={<MoreOutlined />}
        aria-label={label}
        onClick={(event) => event.stopPropagation()}
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') event.stopPropagation()
        }}
      />
    </Dropdown>
  )
}
