import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from './App'
import './index.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      gcTime: 5 * 60_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

const antdTheme = {
  token: {
    colorPrimary: '#141413',
    colorInfo: '#141413',
    colorSuccess: '#16803c',
    colorError: '#c7352b',
    colorWarning: '#a66a00',
    colorBgBase: '#f3f0ee',
    colorBgContainer: '#fcfbfa',
    colorTextBase: '#141413',
    colorBorder: 'rgba(20, 20, 19, 0.12)',
    borderRadius: 10,
    fontFamily:
      "'Sofia Sans', -apple-system, BlinkMacSystemFont, 'SF Pro Display', sans-serif",
  },
  components: {
    Button: { controlHeight: 36, borderRadius: 999 },
    Input: { controlHeight: 38, borderRadius: 10 },
    Select: { controlHeight: 38, borderRadius: 10 },
    Card: { borderRadiusLG: 18 },
  },
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <ConfigProvider locale={zhCN} theme={antdTheme}>
        <BrowserRouter
          future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
        >
          <App />
        </BrowserRouter>
      </ConfigProvider>
    </QueryClientProvider>
  </React.StrictMode>,
)
