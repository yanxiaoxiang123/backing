import { describe, expect, it, vi } from 'vitest'
import { AxiosError, CanceledError } from 'axios'
import api, { getApiErrorMessage } from './api'
import { toast } from '../utils/toast'

function makeAxiosError(response: unknown): AxiosError {
  return new AxiosError(
    'Request failed with status code 500',
    'ERR_BAD_RESPONSE',
    undefined,
    undefined,
    response as never,
  )
}

describe('getApiErrorMessage', () => {
  it('优先返回后端统一错误体中的 message', () => {
    const err = makeAxiosError({
      status: 500,
      data: { error: { code: 'DB_ERR', message: '数据库繁忙' } },
    })
    expect(getApiErrorMessage(err)).toBe('数据库繁忙')
  })

  it('无响应体时返回服务器兜底文案', () => {
    const err = makeAxiosError({ status: 500, data: {} })
    expect(getApiErrorMessage(err)).toBe('服务器开小差了，请稍后重试')
  })

  it('网络错误（无响应）返回网络异常文案', () => {
    const err = new AxiosError('Network Error', 'ERR_NETWORK')
    expect(getApiErrorMessage(err)).toBe('网络异常，请检查网络后重试')
  })

  it('超时返回超时文案', () => {
    const err = new AxiosError('timeout of 120000ms exceeded', 'ECONNABORTED')
    expect(getApiErrorMessage(err)).toBe('请求超时，请稍后重试')
  })

  it('未知异常回退到通用文案', () => {
    expect(getApiErrorMessage('oops')).toBe('请求失败，请稍后重试')
    expect(getApiErrorMessage(null)).toBe('请求失败，请稍后重试')
  })
})

it('does not report a deliberate polling abort as a network error', async () => {
  const showError = vi.spyOn(toast, 'error')
  const cancelled = new CanceledError('page disposed')
  await expect(
    api.get('/jobs/cancelled', {
      adapter: () => Promise.reject(cancelled),
    }),
  ).rejects.toBe(cancelled)
  expect(showError).not.toHaveBeenCalled()
  showError.mockRestore()
})
