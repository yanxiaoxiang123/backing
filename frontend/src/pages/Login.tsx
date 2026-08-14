import { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { Button, Form, Input, Typography, Alert } from 'antd'
import { LockOutlined } from '@ant-design/icons'
import { loginWithApiKey } from '../services/api'

const { Title, Paragraph } = Typography

interface LoginFormValues {
  apiKey: string
}

/**
 * 登录页：提交一次 API key 换取短期 HttpOnly session cookie。
 *
 * API key 只在本次请求中出现（内存态），随后即被丢弃——不写入
 * localStorage、不进入 bundle、不随后续请求发送。
 */
export default function Login() {
  const navigate = useNavigate()
  const location = useLocation()
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const from = (location.state as { from?: string } | null)?.from || '/'

  const onFinish = async (values: LoginFormValues) => {
    setSubmitting(true)
    setError(null)
    try {
      await loginWithApiKey(values.apiKey.trim())
      navigate(from, { replace: true })
    } catch {
      setError('登录失败：API Key 无效或服务不可用，请检查后重试')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <Title level={3} className="login-title">
          量化系统
        </Title>
        <Paragraph type="secondary" className="login-subtitle">
          请输入 API Key 登录（密钥仅本次提交，会话由 HttpOnly Cookie 维持）
        </Paragraph>
        {error && (
          <Alert type="error" showIcon message={error} style={{ marginBottom: 16 }} />
        )}
        <Form<LoginFormValues>
          layout="vertical"
          onFinish={onFinish}
          requiredMark={false}
        >
          <Form.Item
            name="apiKey"
            rules={[{ required: true, message: '请输入 API Key' }]}
          >
            <Input.Password
              prefix={<LockOutlined />}
              placeholder="API Key"
              autoFocus
              autoComplete="current-password"
            />
          </Form.Item>
          <Button type="primary" htmlType="submit" block loading={submitting}>
            登录
          </Button>
        </Form>
      </div>
    </div>
  )
}
