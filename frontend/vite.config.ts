import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

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
      '/api': 'http://127.0.0.1:8000',
    },
  },
})
