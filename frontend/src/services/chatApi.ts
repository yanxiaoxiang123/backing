import axios from 'axios'
import type { ChatMessage, ChatRequest, AgentRequest } from '../types'

const api = axios.create({
  baseURL: '/api',
  timeout: 120000
})

api.interceptors.request.use((config) => {
  const apiKey = import.meta.env.VITE_API_KEY
  if (apiKey) {
    config.headers['X-API-Key'] = apiKey
  }
  return config
})

export async function* streamChat(messages: ChatMessage[]): AsyncGenerator<string> {
  const request: ChatRequest = {
    messages: messages.map(m => ({ role: m.role, content: m.content }))
  }

  const response = await api.post('/chat/stream', request, {
    responseType: 'text',
    timeout: 120000
  })

  const reader = response.data.getReader()
  const decoder = new TextDecoder()

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    const chunk = decoder.decode(value)
    const lines = chunk.split('\n')

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try {
          const data = JSON.parse(line.slice(6))
          if (data.content === '[DONE]') {
            return
          }
          if (data.error) {
            throw new Error(data.error)
          }
          yield data.content
        } catch (e) {
          // 忽略解析错误
        }
      }
    }
  }
}

export async function* streamAgent(
  endpoint: string,
  request: AgentRequest
): AsyncGenerator<string> {
  const response = await api.post(endpoint, request, {
    responseType: 'text',
    timeout: 120000
  })

  const reader = response.data.getReader()
  const decoder = new TextDecoder()

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    const chunk = decoder.decode(value)
    const lines = chunk.split('\n')

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try {
          const data = JSON.parse(line.slice(6))
          if (data.content === '[DONE]') {
            return
          }
          if (data.error) {
            throw new Error(data.error)
          }
          yield data.content
        } catch (e) {
          // 忽略解析错误
        }
      }
    }
  }
}

export const COMMAND_LIST = [
  { command: '/技术', description: '技术面分析', example: '/技术 000001' },
  { command: '/情绪', description: '社交媒体情绪', example: '/情绪 贵州茅台' },
  { command: '/新闻', description: '新闻搜索分析', example: '/新闻 财报' },
  { command: '/基本面', description: '财务报表分析', example: '/基本面 000001' },
  { command: '/政策', description: '政策影响分析', example: '/政策' },
  { command: '/热钱', description: '主力资金追踪', example: '/热钱' },
  { command: '/解禁', description: '解禁股分析', example: '/解禁' },
]