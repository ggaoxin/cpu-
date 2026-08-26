# 前端文献题目输入补充说明

## 修改范围

以下功能的可视化弹窗包含“文献”名称，但此前文本输入没有题目字段，因此补充题目输入：

1. 中文科技文献分类
2. 英文科技文献分类
3. 专业领域科技文献分类
4. 中文科技文献关键词识别
5. 英文科技文献关键词识别

已经具有项目名称或题名元数据的功能不重复增加；弹窗不展示文献名称的功能保持不变。

## 交互规则

- 单文本：用户填写一个必填“题目”。
- 批量文本：每条文本分别填写一个必填“题目”。
- 单文件、批量文件：不增加手工题目输入，由后端从文件解析题目；解析不到时可使用文件名作为展示标识。

## 接口字段

- 单文本请求：新增 `document_title: string`。
- 批量文本请求：新增 `document_title: string[]`，同时每条文本对象携带 `title`。
- 文件请求：不提交 `document_title`。
- 响应：弹窗优先读取 `data.document_title`，并兼容原有 `data.document.title`。

## 修改文件

- `frontend/src/components/OnlineTester.vue`
- `frontend/src/data/requirement-contracts.ts`
- `frontend/src/utils/tooling.ts`
- `frontend/src/utils/visualizationRenderers.js`
- `frontend/src/utils/prototypeVisualizationRenderers.js`

## 验证结果

- Vue 生产构建通过。
- 19 个功能、67 种功能/输入方式组合的接口一致性检查通过。
- 5 个目标功能均显示题目输入并在 API/SDK 示例中包含 `document_title`。
- 批量文本逐条显示题目；文件模式和非目标功能未误加题目输入。
- 页面控制台无错误。
