import { useState } from 'react'
import { Button, Empty, List, Modal, Tag } from 'antd'
import type { ArtifactRecord } from '../../types/agent'
import { getArtifact } from '../../services/agentRuns'

interface ArtifactViewerProps {
  artifacts: ArtifactRecord[]
  runId?: string | null
}

/** 产物工作区：列表 + 查看内容（US-2.9；后端下载端点）。 */
export function ArtifactViewer({ artifacts, runId }: ArtifactViewerProps) {
  const [content, setContent] = useState<Record<string, unknown> | null>(null)
  const [open, setOpen] = useState(false)

  if (artifacts.length === 0) {
    return <Empty description="暂无产物" />
  }

  const view = (artifact: ArtifactRecord) => {
    if (!runId) return
    void getArtifact(runId, artifact.id)
      .then((data) => {
        setContent(data)
        setOpen(true)
      })
      .catch(() => undefined)
  }

  return (
    <>
      <List
        size="small"
        dataSource={artifacts}
        renderItem={(item) => (
          <List.Item
            actions={[
              <Button key="view" size="small" onClick={() => view(item)}>
                查看
              </Button>,
            ]}
          >
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
      <Modal
        title="产物内容"
        open={open}
        onCancel={() => setOpen(false)}
        footer={null}
        width={640}
      >
        <pre className="agent-artifact-content">{JSON.stringify(content, null, 2)}</pre>
      </Modal>
    </>
  )
}
