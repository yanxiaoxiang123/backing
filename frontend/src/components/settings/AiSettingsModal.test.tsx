import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import api from '../../services/api'
import AiSettingsModal from './AiSettingsModal'

// Only the HTTP boundary is replaced; render the real modal and form.
vi.mock('../../services/api', () => ({
  default: { get: vi.fn(), put: vi.fn() },
}))

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(api.get).mockResolvedValue({ data: { deepseek_configured: true } })
  vi.mocked(api.put).mockResolvedValue({ data: { deepseek_configured: true } })
})

describe('AI settings modal', () => {
  it('shows configuration status with an empty password field', async () => {
    render(<AiSettingsModal open onClose={vi.fn()} />)
    expect(await screen.findByText('已配置')).toBeInTheDocument()
    const input = screen.getByLabelText('DeepSeek API Key')
    expect(input).toHaveAttribute('type', 'password')
    expect(input).toHaveValue('')
    expect(screen.queryByText(/Tavily/i)).not.toBeInTheDocument()
  })

  it('saves the new key and clears it when reopened', async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()
    const { rerender } = render(<AiSettingsModal open onClose={onClose} />)
    await screen.findByText('已配置')
    await user.type(screen.getByLabelText('DeepSeek API Key'), 'sk-new-secret')
    await user.click(screen.getByRole('button', { name: /保\s*存/ }))
    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1))
    expect(api.put).toHaveBeenCalledWith('/settings/ai', {
      deepseek_api_key: 'sk-new-secret',
    })
    rerender(<AiSettingsModal open={false} onClose={onClose} />)
    rerender(<AiSettingsModal open onClose={onClose} />)
    await screen.findByText('已配置')
    expect(screen.getByLabelText('DeepSeek API Key')).toHaveValue('')
  })

  it('preserves the existing key when input is blank', async () => {
    const onClose = vi.fn()
    render(<AiSettingsModal open onClose={onClose} />)
    await screen.findByText('已配置')
    fireEvent.click(screen.getByRole('button', { name: /保\s*存/ }))
    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1))
    expect(api.put).not.toHaveBeenCalled()
  })

  it('keeps the modal open after save failure and shows a safe message', async () => {
    vi.mocked(api.put).mockRejectedValue(new Error('request contains sk-new-secret'))
    const user = userEvent.setup()
    const onClose = vi.fn()
    render(<AiSettingsModal open onClose={onClose} />)
    await screen.findByText('已配置')
    await user.type(screen.getByLabelText('DeepSeek API Key'), 'sk-new-secret')
    await user.click(screen.getByRole('button', { name: /保\s*存/ }))
    expect(await screen.findByText('保存失败，请稍后重试')).toBeInTheDocument()
    expect(onClose).not.toHaveBeenCalled()
    expect(screen.queryByText(/request contains/)).not.toBeInTheDocument()
  })

  it('rejects an oversized paste without saving a truncated key', async () => {
    render(<AiSettingsModal open onClose={vi.fn()} />)
    await screen.findByText('已配置')
    const user = userEvent.setup()
    await user.click(screen.getByLabelText('DeepSeek API Key'))
    await user.paste('x'.repeat(513))
    await user.click(screen.getByRole('button', { name: /保\s*存/ }))
    expect(
      await screen.findByText('API Key 格式无效，请检查后重试'),
    ).toBeInTheDocument()
    expect(api.put).not.toHaveBeenCalled()
  })

  it('blocks saving when the current status cannot be loaded', async () => {
    vi.mocked(api.get).mockRejectedValue(new Error('offline'))
    render(<AiSettingsModal open onClose={vi.fn()} />)
    expect(await screen.findByText('读取配置失败，请关闭后重试')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /保\s*存/ })).toBeDisabled()
  })
})
