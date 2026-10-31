import { useEffect, useState } from 'react'
import { Alert, Form, Input, Modal, Spin, Tag } from 'antd'
import api from '../../services/api'

interface AiSettingsModalProps {
  open: boolean
  onClose: () => void
}

export default function AiSettingsModal({ open, onClose }: AiSettingsModalProps) {
  const [key, setKey] = useState('')
  const [configured, setConfigured] = useState<boolean | null>(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    setKey('')
    setError('')
    setConfigured(null)
    if (!open) return
    let active = true
    void api.get<{ deepseek_configured: boolean }>('/settings/ai').then(
      ({ data }) => {
        if (active) setConfigured(data.deepseek_configured)
      },
      () => {
        if (active) setError('读取配置失败，请关闭后重试')
      },
    )
    return () => {
      active = false
    }
  }, [open])

  const close = () => {
    if (saving) return
    setKey('')
    onClose()
  }

  const save = async () => {
    if (configured === null || saving) return
    const apiKey = key.trim()
    if (!apiKey) {
      close()
      return
    }
    if (
      /\s/.test(apiKey) ||
      Array.from(apiKey).some(
        (char) => char.charCodeAt(0) < 32 || char.charCodeAt(0) === 127,
      ) ||
      apiKey.length > 512
    ) {
      setError('API Key 格式无效，请检查后重试')
      return
    }
    setSaving(true)
    setError('')
    try {
      await api.put('/settings/ai', { deepseek_api_key: apiKey })
      setKey('')
      onClose()
    } catch {
      setError('保存失败，请稍后重试')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      title="AI 服务配置"
      open={open}
      width={440}
      okText="保存"
      cancelText="取消"
      onOk={() => void save()}
      onCancel={close}
      confirmLoading={saving}
      okButtonProps={{ disabled: configured === null }}
      cancelButtonProps={{ disabled: saving }}
      closable={!saving}
      maskClosable={!saving}
      keyboard={!saving}
      destroyOnHidden
    >
      {error && (
        <Alert type="error" message={error} showIcon style={{ marginBottom: 16 }} />
      )}
      {configured === null && !error ? (
        <Spin tip="读取配置中…">
          <div style={{ minHeight: 100 }} />
        </Spin>
      ) : (
        <Form layout="vertical" onFinish={() => void save()}>
          <Form.Item
            label="DeepSeek API Key"
            htmlFor="deepseek-api-key"
            extra={
              <>
                {configured !== null && (
                  <Tag color={configured ? 'success' : 'default'}>
                    {configured ? '已配置' : '未配置'}
                  </Tag>
                )}
                留空保留原密钥，输入新密钥后点击保存。
              </>
            }
          >
            <Input.Password
              id="deepseek-api-key"
              value={key}
              onChange={(event) => setKey(event.target.value)}
              placeholder="输入新的 API Key"
              autoComplete="new-password"
              disabled={saving || configured === null}
            />
          </Form.Item>
          <p style={{ color: 'var(--text-secondary)', marginBottom: 0 }}>
            密钥保存在服务器，仅显示配置状态。保存后对本服务后续 AI 请求生效。 独立任务
            worker 或其他服务实例需重启；环境变量注入密钥的部署需同步更新部署配置。
          </p>
        </Form>
      )}
    </Modal>
  )
}
