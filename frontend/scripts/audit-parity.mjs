import fs from 'node:fs'
import path from 'node:path'
import crypto from 'node:crypto'
import ts from '../.tools/typescript/package/lib/typescript.js'
import { compileTemplate, parse as parseVueSfc } from '@vue/compiler-sfc'
import { clusterLabelRuntimeResponses, deepClusterRuntime, groups, requirements, structuredReviewRuntime } from '../src/data/prototype.generated.js'
import { requirementContracts } from '../src/data/requirement-contracts.ts'
import { tools } from '../src/data/tool-overrides.ts'
import { noVisualizationToolIds } from '../src/utils/tooling.ts'
import { renderPrototypeVisualization } from '../src/utils/prototypeVisualizationRenderers.js'

const root = path.resolve(import.meta.dirname, '..')
const source = 'C:\\Users\\setfi\\Downloads\\semantic_toolkit_prototype_v7_74_cluster_review_overview_cleanup.html'
const expectedHash = 'c73d2b43b86fe4b17f2707b3a2602fb9f7ac33b41c4f65ea3691c1f71ef6c2af'
const expectedIds = groups.flatMap(group => group.items.map(item => item[0]))
const failures = []
const checks = []
const check = (name, ok, detail = '') => { checks.push({ name, ok, detail }); if (!ok) failures.push(name) }

const sourceBuffer = fs.readFileSync(source)
check('唯一原型文件 SHA-256', crypto.createHash('sha256').update(sourceBuffer).digest('hex') === expectedHash)
check('功能项数量为 19', expectedIds.length === 19, String(expectedIds.length))
check('Vue 工具 ID 与原型完全一致', expectedIds.every(id => tools[id]) && Object.keys(tools).length === 19)
check('10 个功能分组', groups.length === 10, String(groups.length))
check('所有工具均含请求参数', expectedIds.every(id => Array.isArray(tools[id].params) && tools[id].params.length > 0))
check('所有工具均含演示响应', expectedIds.every(id => tools[id].response && typeof tools[id].response === 'object'))
check('当前需规请求参数合同逐字段一致', expectedIds.every(id => JSON.stringify(tools[id].params) === JSON.stringify(requirementContracts[id]?.inputs || [])))

const sourceFiles = []
for (const directory of ['src', 'scripts']) {
  const visit = dir => fs.readdirSync(dir, { withFileTypes: true }).forEach(entry => {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) visit(full)
    else if (/\.(js|ts|vue|css|mjs)$/.test(entry.name) && !entry.name.includes('generated')) sourceFiles.push(full)
  })
  visit(path.join(root, directory))
}
const allUi = sourceFiles.filter(file => file.startsWith(path.join(root, 'src'))).map(file => fs.readFileSync(file, 'utf8')).join('\n')
check('未引用其他 HTML 原型', !/semantic_toolkit_prototype_v(?!7_74_cluster_review_overview_cleanup)/i.test(allUi))
check('页面版本锁定 V7.74', allUi.includes('V7.74'))
check('19 个功能的输入字段均由当前需规合同驱动', expectedIds.every(id => requirementContracts[id]?.inputs.every(row => tools[id].params.some(candidate => candidate[0] === row[0]))))
check('评审表资源与格式控件已在在线测试区呈现', ['标准中图分类号标注数据','中图分类标准及映射规则','领域分类规则','人工标注训练数据','领域术语库','分类标准映射表','文本格式要求','预处理后的训练集','通用领域标注语料','多领域科研语料','人工标注数据','本体分类体系','领域标注训练数据','研究主题或关键词'].every(marker => allUi.includes(marker)))
check('评审表新增结果报告已在弹窗呈现', ['文献分布分析报告','数据分布报告','识别统计分析报告','标签生成过程报告','标签差异化优化结果','聚类及类簇归纳结果','趋势分析与研究热点分布图'].every(marker => allUi.includes(marker)))
check('概念定义响应示例包含统计分析报告', Boolean(tools['definition-detect'].response?.data?.statistical_analysis_report))
check('聚类标签响应示例包含生成过程与差异化结果', Boolean(tools['cluster-label'].demoBatchTextResult?.data?.label_generation_process_report) && Boolean(tools['cluster-label'].demoBatchTextResult?.data?.label_distinctiveness_optimization_result))
check('结构化综述响应示例包含类簇归纳与趋势热点', Boolean(tools['structured-review'].demoBatchTextResult?.data?.cluster_induction_results) && Boolean(tools['structured-review'].demoBatchTextResult?.data?.trend_hotspot_distribution))
check('结构化综述输入严格为需规三项', JSON.stringify(tools['structured-review'].params.map(row => row[0])) === JSON.stringify(['document_set','topic_or_keywords','document_metadata']))
check('结构化综述批量文本统一为 document_id 与 text', (tools['structured-review'].payload?.document_set || []).every(item => JSON.stringify(Object.keys(item)) === JSON.stringify(['document_id','text'])))
check('结构化综述业务输出完整覆盖需规四项', ['tree','cluster_induction_results','structured_report','trend_hotspot_distribution'].every(name => name in (tools['structured-review'].demoBatchTextResult?.data || {})))
check('结构化综述响应不携带原型元信息', !('meta' in (tools['structured-review'].demoBatchTextResult || {})))
check('API 与 SDK 共享模式切换', allUi.includes('API 调用') && allUi.includes('SDK 调用') && allUi.includes('ModeSwitch'))
check('实体关系弹窗含 V7.74 RDF 页签', allUi.includes('data-relation-tab="rdf">RDF表示') && allUi.includes('relation-rdf-preview-v699'))
check('深度聚类含评测与人工校正', allUi.includes('评测与人工校正'))
check('深度聚类文本为发表时间 + text', allUi.includes('publication_date') && allUi.includes('发表时间') && allUi.includes('text'))
check('聚类标签含 0—1 差异阈值', allUi.includes('类簇间差异阈值') && allUi.includes('0—1'))
check('左右区域独立滚动且隐藏滚动条', allUi.includes('.sidebar::-webkit-scrollbar') && allUi.includes('.content-wrap::-webkit-scrollbar'))
const visualizationIds = expectedIds.filter(id => !noVisualizationToolIds.has(id))
const renderedVisualizations = Object.fromEntries(visualizationIds.map(id => [id, renderPrototypeVisualization(id, tools[id].response)]))
check('17 个有可视化能力的功能均使用专属结果布局', visualizationIds.length === 17 && visualizationIds.every(id => renderedVisualizations[id]?.trim()))
check('V7.74 无弹窗功能清单准确', JSON.stringify([...noVisualizationToolIds]) === JSON.stringify(['zh-abstract-move','en-abstract-move']))
check('研究问题识别最终支持四种输入方式', JSON.stringify(tools['rq-detect'].inputModes) === JSON.stringify(['text','batch-text','file','batch']))
check('实体关系 RDF 与三元组读取当前响应', renderedVisualizations['relation-extract'].includes('RDF表示') && renderedVisualizations['relation-extract'].includes('relation-rdf-preview-v699') && !renderedVisualizations['relation-extract'].includes('doc:MultiScaleModel'))
check('深度聚类演示结果与 V7.74 运行时一致', deepClusterRuntime.response?.data?.input_summary?.document_count === 12 && deepClusterRuntime.response?.data?.clusters?.length === 5 && deepClusterRuntime.response?.data?.clustering_quality?.silhouette_score === 0.825)
check('深度聚类评测指标与人工校正字段完整', deepClusterRuntime.response?.data?.training_evaluation?.metrics?.adjusted_rand_index === 0.736 && Array.isArray(deepClusterRuntime.response?.data?.manual_correction?.supported_operations))
check('聚类标签演示结果与 V7.74 运行时一致', clusterLabelRuntimeResponses.batchText?.data?.source?.document_count === 6 && clusterLabelRuntimeResponses.batchText?.data?.cluster_count === 2 && clusterLabelRuntimeResponses.batchText?.data?.labels?.length === 2)
check('结构化综述演示结果与 V7.74 运行时一致', structuredReviewRuntime.batchText?.data?.document_count === 5 && structuredReviewRuntime.batchText?.data?.tree?.length === 3 && structuredReviewRuntime.batchText?.data?.statistics?.evidence_sentence_count === 15)
const onlineTesterSource = fs.readFileSync(path.join(root, 'src/components/OnlineTester.vue'), 'utf8')
check('结构化综述在线录入仅保留 text 且题名选填', onlineTesterSource.includes('v-model="doc.title"') && onlineTesterSource.includes('v-model="doc.text"') && !onlineTesterSource.includes('v-model="doc.abstract"') && !onlineTesterSource.includes('v-model="doc.references"'))
const prototypeCssSource = fs.readFileSync(path.join(root, 'src/styles/prototype.generated.css'), 'utf8')
check('聚类标签参数区无定时重排逻辑', !/setInterval|MutationObserver/.test(onlineTesterSource))
check('在线测试不提供演示数据生成入口', !onlineTesterSource.includes('生成演示数据') && !onlineTesterSource.includes('demoDocs'))
check('在线测试不使用原型响应冒充后端结果', !onlineTesterSource.includes('responseFor') && onlineTesterSource.includes('executeToolRequest') && onlineTesterSource.includes('等待后端返回真实测试结果'))
check('弹窗审查预览与真实响应入口相互隔离', onlineTesterSource.includes("emit('preview', mode)") && allUi.includes('modalPreview') && !onlineTesterSource.includes('responseFor'))
check('临时弹窗预览按钮未被原型白名单隐藏', prototypeCssSource.includes(':not(#previewVisualizationBtnReview)'))

for (const file of sourceFiles.filter(file => /\.(ts|vue)$/.test(file) && !file.endsWith('.d.ts'))) {
  const text = fs.readFileSync(file, 'utf8')
  const script = file.endsWith('.vue') ? (text.match(/<script setup(?: lang="ts")?>([\s\S]*?)<\/script>/)?.[1] || '') : text
  const output = ts.transpileModule(script, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext }, reportDiagnostics: true, fileName: file })
  const diagnostics = output.diagnostics || []
  check(`TypeScript 语法：${path.relative(root, file)}`, diagnostics.length === 0, diagnostics.map(item => ts.flattenDiagnosticMessageText(item.messageText, '\n')).join('; '))
  if (file.endsWith('.vue')) {
    const relative = path.relative(root, file)
    const parsed = parseVueSfc(text, { filename: relative })
    const parseErrors = parsed.errors.map(error => error instanceof Error ? error.message : String(error))
    if (parsed.descriptor.template) {
      const compiled = compileTemplate({
        id: relative,
        filename: relative,
        source: parsed.descriptor.template.content,
        compilerOptions: { bindingMetadata: {} },
      })
      parseErrors.push(...compiled.errors.map(error => error instanceof Error ? error.message : String(error)))
    } else parseErrors.push('缺少 template 区块')
    check(`Vue 模板编译：${relative}`, parseErrors.length === 0, parseErrors.join('; '))
  }
}

for (const item of checks) console.log(`${item.ok ? 'PASS' : 'FAIL'}  ${item.name}${item.detail ? ` (${item.detail})` : ''}`)
if (failures.length) { console.error(`\n${failures.length} 项检查失败。`); process.exit(1) }
console.log(`\n全部 ${checks.length} 项静态一致性检查通过。`)
