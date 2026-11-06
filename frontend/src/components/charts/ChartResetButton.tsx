import { Button } from 'antd'
import { UndoOutlined } from '@ant-design/icons'

export function ChartResetButton({ onReset }: { onReset: () => void }) {
  return (
    <Button
      type="text"
      size="small"
      icon={<UndoOutlined role="presentation" aria-hidden="true" />}
      onClick={onReset}
    >
      重置视图
    </Button>
  )
}
