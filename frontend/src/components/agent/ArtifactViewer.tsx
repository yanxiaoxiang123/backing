import { Empty, List, Tag } from 'antd'
import type { ArtifactRecord } from '../../types/agent'

export function ArtifactViewer({ artifacts }: { artifacts: ArtifactRecord[] }) {
  if (artifacts.length === 0) {
    return <Empty description="暂无产物" />
  }
  return (
    <List
      size="small"
      dataSource={artifacts}
      renderItem={(item) => (
        <List.Item>
          <List.Item.Meta
            title={
              <span>
                <Tag color="blue">{item.artifact_type}</Tag>
                {item.uri}
              </span>
            }
            description={
              <span>
                {item.source_id && <>source: {item.source_id} · </>}
                {item.schema_version && <>schema: {item.schema_version} · </>}
                {item.as_of ?? '—'}
              </span>
            }
          />
        </List.Item>
      )}
    />
  )
}
