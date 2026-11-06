import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from './App'
import './index.css'
import { ui } from './styles/uiTheme'

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
    colorPrimary: ui.action,
    colorInfo: '#1b6e66',
    colorLink: '#1b6e66',
    colorSuccess: '#2e7d32',
    colorError: '#b42318',
    colorWarning: '#92400e',
    colorBgBase: ui.panel,
    colorBgContainer: ui.panel,
    colorBgLayout: ui.main,
    colorBgElevated: ui.panel,
    colorTextBase: ui.ink,
    colorTextSecondary: ui.muted,
    colorTextDisabled: ui.muted,
    colorTextPlaceholder: ui.muted,
    colorBorder: ui.line,
    colorBorderSecondary: ui.line,
    boxShadow: 'none',
    boxShadowSecondary: 'none',
    motionDurationFast: ui.fast,
    motionDurationMid: ui.normal,
    motionDurationSlow: ui.overlay,
    motionEaseInOut: ui.ease,
    motionEaseOut: ui.ease,
    motionEaseOutBack: ui.ease,
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
      headerColor: ui.muted,
      rowHoverBg: ui.main,
      borderColor: ui.line,
      fontSize: 13,
    },
    Tabs: {
      itemSelectedColor: ui.ink,
      itemColor: ui.muted,
      inkBarColor: '#1b6e66',
    },
    Tag: {
      defaultBg: ui.main,
      defaultColor: '#3d3d3a',
      borderRadiusSM: 999,
    },
    Tooltip: {
      colorBgSpotlight: ui.panel,
      colorTextLightSolid: ui.ink,
      borderRadius: 6,
    },
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
