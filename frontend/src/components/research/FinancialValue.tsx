import { formatPercent, numberTone } from '../../utils/dataFormat'

export function FinancialValue({
  value,
  digits = 2,
  signed = true,
}: {
  value: unknown
  digits?: number
  signed?: boolean
}) {
  return (
    <span className={`financial-value ${numberTone(value, digits)}`}>
      {formatPercent(value, digits, signed)}
    </span>
  )
}
