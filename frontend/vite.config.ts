import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import viteCompression from 'vite-plugin-compression'
import { visualizer } from 'rollup-plugin-visualizer'

export default defineConfig({
  plugins: [
    {
      name: 'welcome-directory-index',
      configureServer(server) {
        server.middlewares.use((req, _res, next) => {
          const url = req.url || ''
          if (
            url === '/welcome' ||
            url === '/welcome/' ||
            url.startsWith('/welcome/?')
          ) {
            req.url = '/welcome/index.html'
          }
          next()
        })
      },
      configurePreviewServer(server) {
        server.middlewares.use((req, _res, next) => {
          const url = req.url || ''
          if (
            url === '/welcome' ||
            url === '/welcome/' ||
            url.startsWith('/welcome/?')
          ) {
            req.url = '/welcome/index.html'
          }
          next()
        })
      },
    },
    react(),
    viteCompression({
      algorithm: 'brotliCompress',
      ext: '.br',
      threshold: 1024,
      deleteOriginFile: false,
    }),
    viteCompression({
      algorithm: 'gzip',
      ext: '.gz',
      threshold: 1024,
      deleteOriginFile: false,
    }),
    visualizer({
      filename: 'dist/stats.html',
      title: 'Stock Backtest Bundle Visualizer',
      gzipSize: true,
      brotliSize: true,
      open: false,
    }),
  ],
  server: {
    host: '0.0.0.0',
    port: 5174,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8808',
        changeOrigin: true,
        ws: true,
      },
    },
  },
  build: {
    chunkSizeWarningLimit: 600,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined
          if (
            id.includes('@ant-design/icons') ||
            id.includes('@ant-design/icons-svg') ||
            id.includes('@ant-design/colors') ||
            id.includes('@ant-design/fast-color')
          )
            return 'antd-icons'
          if (id.includes('rc-util')) return 'rc-util'
          if (
            id.includes('antd') ||
            id.includes('@ant-design') ||
            id.includes('/rc-') ||
            id.includes('@rc-component')
          )
            return 'antd'
          if (id.includes('echarts') || id.includes('zrender')) return 'echarts'
          if (id.includes('dayjs')) return 'dayjs'
          if (id.includes('@tanstack/react-query')) return 'query'
          if (id.includes('react-markdown') || id.includes('remark-')) return 'markdown'
          if (
            id.includes('react/') ||
            id.includes('react-dom') ||
            id.includes('scheduler') ||
            id.includes('@babel/runtime') ||
            id.includes('classnames')
          )
            return 'react'
          return undefined
        },
      },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: false,
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
    exclude: ['node_modules', 'dist', 'e2e'],
  },
})
