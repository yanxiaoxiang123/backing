import { Alert, Descriptions, Empty, Table, Tag } from 'antd'
import type { RiskPanelData } from '../../types/agent'

export function RiskPanel({ data }: { data?: RiskPanelData | null }) {
  if (!data) {
    return <Empty description="尚无风险数据" />
  }
  return (
    <div>
      {data.rejected && (
        <Alert
          type="error"
          showIcon
          message="组合被拒绝"
          description={(data.rejection_reasons ?? []).join('；')}
          style={{ marginBottom: 12 }}
        />
      )}
      {data.positions && data.positions.length > 0 && (
        <Table
          size="small"
          rowKey="code"
          pagination={false}
          dataSource={data.positions}
          columns={[
            { title: '代码', dataIndex: 'code' },
            { title: '动作', dataIndex: 'action' },
            {
              title: '权重',
              dataIndex: 'weight',
              render: (value: number) => `${(value * 100).toFixed(1)}%`,
            },
            {
              title: '置信度',
              dataIndex: 'confidence',
              render: (value: number) => `${Math.round(value * 100)}%`,
            },
          ]}
        />
      )}
      <Descriptions size="small" column={1} style={{ marginTop: 12 }}>
        {(data.constraints ?? []).map((c, i) => (
          <Descriptions.Item key={i} label={c.rule}>
            <Tag color={c.passed ? 'green' : 'red'}>{c.passed ? '通过' : '未通过'}</Tag>
            {c.detail}
          </Descriptions.Item>
        ))}
      </Descriptions>
    </div>
  )
}
