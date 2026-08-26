import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5174,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8808',
        changeOrigin: true,
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined
          if (id.includes('@tanstack/react-query')) return 'query'
          if (id.includes('echarts') || id.includes('zrender')) return 'charts'
          if (
            id.includes('antd') ||
            id.includes('@ant-design') ||
            id.includes('/rc-') ||
            id.includes('@rc-component')
          )
            return 'antd'
          if (id.includes('react-markdown') || id.includes('remark-')) return 'markdown'
          if (
            id.includes('react/') ||
            id.includes('react-dom') ||
            id.includes('scheduler')
          )
            return 'react'
          return 'vendor'
        },
      },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: false,
  },
})
