import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import fs from 'node:fs'
import path from 'node:path'

// 后端 API 密钥鉴权（2026-11-24 漏洞修复 V1 第一层）：
// 密钥只存在后端 config/.env，vite 代理转发时在服务端注入 X-API-Key，
// 浏览器端代码与网络面板均不接触密钥。后端关闭鉴权时不注入（无副作用）。
function backendApiKey(): string {
  try {
    const envText = fs.readFileSync(path.resolve(__dirname, '../config/.env'), 'utf-8')
    const enabled = /^API_AUTH_ENABLED=(.+)$/m.exec(envText)?.[1]?.trim().toLowerCase() === 'true'
    const keys = /^API_KEYS=(.+)$/m.exec(envText)?.[1]?.split(',').map(s => s.trim()).filter(Boolean) || []
    return enabled && keys.length ? keys[0] : ''
  } catch {
    return ''
  }
}

const apiKey = backendApiKey()

export default defineConfig({
  plugins: [vue()],
  server: {
    // 0.0.0.0 + 6006：AutoDL「自定义服务」默认映射 6006 端口为公网 URL
    host: '0.0.0.0',
    port: 6006,
    strictPort: true,
    // 放行 AutoDL 自定义服务的公网域名（vite 默认只允许 localhost，会 403）
    allowedHosts: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        configure: (proxy) => {
          if (!apiKey) return
          proxy.on('proxyReq', (proxyReq) => {
            proxyReq.setHeader('X-API-Key', apiKey)
          })
        },
      },
    },
  },
})
