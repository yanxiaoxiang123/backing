import { beforeEach, describe, expect, it, vi } from 'vitest'
import axios from 'axios'
import {
  bootstrapAuth,
  getAuthState,
  loginWithApiKey,
  logout,
  onAuthChange,
} from './api'

// api.ts 依赖 axios.create()（实例 + 拦截器）与顶层 axios.get/post（认证函数），
// 工厂 mock 保留真实 create 形状并接管网络调用。
vi.mock('axios', async (importOriginal) => {
  const actual = await importOriginal<typeof import('axios')>()
  const instance = {
    interceptors: {
      request: { use: vi.fn() },
      response: { use: vi.fn() },
    },
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  }
  return {
    ...actual,
    default: {
      ...actual.default,
      create: vi.fn(() => instance),
      get: vi.fn(),
      post: vi.fn(),
      put: vi.fn(),
      delete: vi.fn(),
    },
  }
})

const mockedAxios = axios as unknown as {
  get: ReturnType<typeof vi.fn>
  post: ReturnType<typeof vi.fn>
}

describe('会话认证状态机', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('bootstrapAuth 探测到有效会话 → authenticated', async () => {
    mockedAxios.get.mockResolvedValue({ data: { authenticated: true } })
    const states: string[] = []
    onAuthChange((s) => states.push(s))
    await bootstrapAuth()
    expect(getAuthState()).toBe('authenticated')
    expect(states).toContain('authenticated')
  })

  it('bootstrapAuth 无会话（401）→ unauthenticated', async () => {
    mockedAxios.get.mockRejectedValue(new Error('401'))
    await bootstrapAuth()
    expect(getAuthState()).toBe('unauthenticated')
  })

  it('loginWithApiKey 成功后 → authenticated', async () => {
    mockedAxios.post.mockResolvedValue({ data: { success: true } })
    await loginWithApiKey('my-key')
    expect(getAuthState()).toBe('authenticated')
    // key 只出现在本次请求体
    expect(mockedAxios.post).toHaveBeenCalledWith(
      '/api/v1/auth/session',
      { api_key: 'my-key' },
      { baseURL: '' },
    )
  })

  it('logout 后 → unauthenticated', async () => {
    mockedAxios.post.mockResolvedValue({ data: { success: true } })
    await loginWithApiKey('k')
    await logout()
    expect(getAuthState()).toBe('unauthenticated')
  })

  it('onAuthChange 返回取消订阅函数', async () => {
    mockedAxios.get.mockResolvedValue({ data: { authenticated: true } })
    const listener = vi.fn()
    const unsubscribe = onAuthChange(listener)
    await bootstrapAuth()
    expect(listener).toHaveBeenCalledTimes(1)
    unsubscribe()
    mockedAxios.get.mockRejectedValue(new Error('401'))
    await bootstrapAuth()
    expect(listener).toHaveBeenCalledTimes(1) // 不再收到通知
  })
})
