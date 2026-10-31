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
    colorPrimary: '#1f201d',
    colorInfo: '#1b6e66',
    colorLink: '#1b6e66',
    colorSuccess: '#2e7d32',
    colorError: '#b42318',
    colorWarning: '#92400e',
    colorBgBase: '#ffffff',
    colorBgContainer: '#ffffff',
    colorBgLayout: '#ffffff',
    colorBgElevated: '#ffffff',
    colorTextBase: '#1f201d',
    colorTextSecondary: '#636361',
    colorBorder: '#eaeaea',
    colorBorderSecondary: '#f3f3f3',
    borderRadius: 10,
    borderRadiusLG: 22,
    fontSize: 13,
    fontSizeLG: 14,
    fontSizeSM: 12,
    controlHeight: 36,
    fontFamily:
      "'PingFang SC', 'Microsoft YaHei', 'Noto Sans CJK SC', 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif",
  },
  components: {
    Button: {
      controlHeight: 36,
      borderRadius: 999,
      primaryShadow: 'none',
      defaultShadow: 'none',
      dangerShadow: 'none',
    },
    Input: { controlHeight: 36, borderRadius: 10 },
    Select: { controlHeight: 36, borderRadius: 10 },
    Card: { borderRadiusLG: 22 },
    Table: {
      headerBg: 'transparent',
      headerSplitColor: 'transparent',
      headerColor: '#636361',
      rowHoverBg: '#f9f9f9',
      borderColor: '#eaeaea',
      fontSize: 13,
    },
    Tabs: {
      itemSelectedColor: '#1f201d',
      itemColor: '#636361',
      inkBarColor: '#1b6e66',
    },
    Tag: {
      defaultBg: '#f3f3f3',
      defaultColor: '#3d3d3a',
      borderRadiusSM: 999,
    },
    Tooltip: { colorBgSpotlight: '#1f201d', borderRadius: 6 },
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
