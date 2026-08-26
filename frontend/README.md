# Semantic Toolkit Vue V7.74

本目录是语义计算工具库的唯一 Vue 前端，界面与演示逻辑只允许来自以下原型：

`C:\Users\setfi\Downloads\semantic_toolkit_prototype_v7_74_cluster_review_overview_cleanup.html`

原型 SHA-256：

`c73d2b43b86fe4b17f2707b3a2602fb9f7ac33b41c4f65ea3691c1f71ef6c2af`

## 本地运行

```powershell
npm install
npm run dev
```

浏览器访问：`http://127.0.0.1:5173/`

## 核验与构建

```powershell
npm run extract:prototype -- "C:\Users\setfi\Downloads\semantic_toolkit_prototype_v7_74_cluster_review_overview_cleanup.html"
npm run audit:parity
npm run build
```

提取命令会校验文件名与 SHA-256；传入其他 HTML 会直接失败。

开发环境中的 `/api` 请求由 Vite 转发到 `http://127.0.0.1:8000`。在线测试当前不生成演示数据，也不会把原型响应冒充后端结果；接口尚未联调时会明确提示未生成响应。

为便于本轮逐项验收弹窗，17 个具备可视化能力的功能暂时提供“预览可视化弹窗”按钮，预览数据只用于检查 V7.74 弹窗布局，不写入数据库，也不属于在线测试响应。V7.74 中没有弹窗的“中文摘要语步识别”和“英文摘要语步识别”不会显示该按钮。正式联调并验收完成后，应移除这组临时预览入口，真实“查看可视化结果”只读取 FastAPI 返回值。
