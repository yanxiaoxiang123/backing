import { useState, useCallback, useMemo } from 'react'
import { Select, Spin } from 'antd'
import { HistoryOutlined, StarOutlined } from '@ant-design/icons'
import { useStockSearch, type StockOption } from '../hooks/useStockSearch'

interface StockSearchProps {
  value?: string
  onChange?: (code: string, option: StockOption) => void
  placeholder?: string
  style?: React.CSSProperties
  watchlistCodes?: string[]
  disabled?: boolean
}

export default function StockSearch({
  value,
  onChange,
  placeholder = '搜索股票（代码/名称）',
  style,
  watchlistCodes,
  disabled,
}: StockSearchProps) {
  const { loading, search, trackSelection } = useStockSearch()
  const [query, setQuery] = useState('')

  const options = useMemo(() => search(query, watchlistCodes), [query, search, watchlistCodes])
  const selectedLabel = useMemo(() => options.find(o => o.code === value)?.label, [value, options])

  const handleChange = useCallback(
    (_: string, option: any) => {
      const opt: StockOption = Array.isArray(option) ? option[0] : option
      if (opt?.code) trackSelection(opt)
      onChange?.(opt?.code ?? _, opt)
    },
    [onChange, trackSelection],
  )

  return (
    <Select
      showSearch
      value={value}
      placeholder={placeholder}
      style={{ width: '100%', ...style }}
      onChange={handleChange}
      onSearch={setQuery}
      filterOption={false}
      notFoundContent={loading ? <Spin size="small" /> : query ? '无匹配结果' : undefined}
      loading={loading}
      disabled={disabled}
      labelRender={() => selectedLabel || value || ''}
      options={options.map(o => ({
        value: o.code,
        label: o.label,
        __isRecent: false,
      }))}
      optionRender={(option) => {
        const isRecent = option?.data?.__isRecent
        const isWatchlist = !isRecent && watchlistCodes?.includes(String(option?.value ?? ''))
        return (
          <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {isRecent && <HistoryOutlined style={{ color: '#999', fontSize: 12 }} />}
            {isWatchlist && <StarOutlined style={{ color: '#faad14', fontSize: 12 }} />}
            <span>{option?.label ?? option?.value}</span>
          </span>
        )
      }}
    />
  )
}