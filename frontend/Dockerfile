FROM node:22-alpine AS builder
WORKDIR /app
COPY package*.json ./
# playwright 仅为本地 e2e 测试依赖，镜像构建无需其浏览器二进制
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
RUN npm install
COPY . .
# 公网网关（edu.itic-sci.com）把服务挂在 /dma/sem/ 下且只转发带该前缀的路径，
# API 请求与页面路由的前缀需在构建期烘焙进产物；内网根路径访问由
# nginx.conf 中 /dma/sem/ 内部重写兜底，两种入口共用同一份产物
ARG PUBLIC_BASE=/dma/sem
RUN npm run build -- --base=${PUBLIC_BASE}/

FROM nginx:1.27-alpine
# 官方镜像启动时对 templates/*.template 做 envsubst 渲染到 conf.d，
# 用于把运行期环境变量 NGINX_API_KEY 注入为后端要求的 X-API-Key 请求头
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80
