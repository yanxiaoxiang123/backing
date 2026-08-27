import { useCallback, useMemo } from 'react'
import { Button, Select, Spin } from 'antd'
import type { DefaultOptionType } from 'antd/es/select'
import { HistoryOutlined, StarOutlined } from '@ant-design/icons'
import {
  useStockSearch,
  type StockOption,
  type StockSearchResult,
} from '../hooks/useStockSearch'
import { sameStock } from '../utils/stockIdentity'

interface StockSearchProps {
  value?: string
  onChange?: (code: string, option: StockOption) => void
  placeholder?: string
  style?: React.CSSProperties
  watchlistCodes?: string[]
  disabled?: boolean
  autoFocus?: boolean
}

export default function StockSearch({
  value,
  onChange,
  placeholder = '搜索股票（代码/名称）',
  style,
  watchlistCodes,
  disabled,
  autoFocus,
}: StockSearchProps) {
  const { query, setQuery, loading, error, search, trackSelection, reload } =
    useStockSearch()

  const options = useMemo<StockSearchResult[]>(
    () => search(query, watchlistCodes),
    [query, search, watchlistCodes],
  )
  const selectedLabel = useMemo(
    () => options.find((o) => sameStock(o.code, value))?.label,
    [value, options],
  )

  const handleChange = useCallback(
    (selectedValue: string, option?: DefaultOptionType | DefaultOptionType[]) => {
      const selectedOption = Array.isArray(option) ? option[0] : option
      const opt = selectedOption?.stock as StockOption | undefined
      if (opt?.code) trackSelection(opt)
      onChange?.(
        opt?.code ?? selectedValue,
        opt ?? { code: selectedValue, name: '', label: selectedValue },
      )
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
      notFoundContent={
        loading ? (
          <Spin size="small" />
        ) : error ? (
          <Button type="link" size="small" onClick={() => void reload()}>
            加载失败，点击重试
          </Button>
        ) : query ? (
          '无匹配结果'
        ) : undefined
      }
      loading={loading}
      disabled={disabled}
      autoFocus={autoFocus}
      labelRender={() => selectedLabel || value || ''}
      options={options.map((o) => ({
        value: o.code,
        label: o.label,
        __isRecent: o.isRecent,
        stock: o,
      }))}
      optionRender={(option) => {
        const isRecent = option?.data?.__isRecent
        const isWatchlist =
          !isRecent &&
          watchlistCodes?.some((code) => sameStock(code, String(option?.value ?? '')))
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
