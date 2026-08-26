import { createHash } from 'node:crypto'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const scriptDirectory = dirname(fileURLToPath(import.meta.url))
const projectDirectory = resolve(scriptDirectory, '..')
const sourceFile = resolve(process.argv[2] || 'C:/Users/setfi/Downloads/semantic_toolkit_prototype_v7_74_cluster_review_overview_cleanup.html')
const expectedFileName = 'semantic_toolkit_prototype_v7_74_cluster_review_overview_cleanup.html'
const expectedSha256 = 'c73d2b43b86fe4b17f2707b3a2602fb9f7ac33b41c4f65ea3691c1f71ef6c2af'

function extractBalanced(source, marker, opening, closing) {
  const markerIndex = source.indexOf(marker)
  if (markerIndex < 0) throw new Error(`未找到原型标记：${marker}`)
  const start = source.indexOf(opening, markerIndex + marker.length)
  if (start < 0) throw new Error(`未找到 ${marker} 的起始符号`)

  let depth = 0
  let quote = ''
  let escaped = false
  let lineComment = false
  let blockComment = false

  for (let index = start; index < source.length; index += 1) {
    const character = source[index]
    const next = source[index + 1]

    if (lineComment) {
      if (character === '\n') lineComment = false
      continue
    }
    if (blockComment) {
      if (character === '*' && next === '/') {
        blockComment = false
        index += 1
      }
      continue
    }
    if (quote) {
      if (escaped) escaped = false
      else if (character === '\\') escaped = true
      else if (character === quote) quote = ''
      continue
    }
    if (character === '/' && next === '/') {
      lineComment = true
      index += 1
      continue
    }
    if (character === '/' && next === '*') {
      blockComment = true
      index += 1
      continue
    }
    if (character === '"' || character === "'" || character === '`') {
      quote = character
      continue
    }
    if (character === opening) depth += 1
    if (character === closing) {
      depth -= 1
      if (depth === 0) return source.slice(start, index + 1)
    }
  }
  throw new Error(`未找到 ${marker} 的结束符号`)
}

function extractThrough(source, startMarker, endMarker) {
  const start = source.indexOf(startMarker)
  if (start < 0) throw new Error(`未找到原型运行时标记：${startMarker}`)
  const endStart = source.indexOf(endMarker, start)
  if (endStart < 0) throw new Error(`未找到原型运行时结束标记：${endMarker}`)
  return source.slice(start, endStart + endMarker.length)
}

function extractBetween(source, startMarker, endMarker, from = 0) {
  const start = source.indexOf(startMarker, from)
  if (start < 0) throw new Error(`未找到原型运行时标记：${startMarker}`)
  const end = source.indexOf(endMarker, start)
  if (end < 0) throw new Error(`未找到原型运行时结束标记：${endMarker}`)
  return source.slice(start, end)
}

const source = await readFile(sourceFile, 'utf8')
const sourceSha256 = createHash('sha256').update(source).digest('hex')
if (!sourceFile.endsWith(expectedFileName)) {
  throw new Error(`原型文件名不匹配，拒绝提取：${sourceFile}`)
}
if (sourceSha256 !== expectedSha256) {
  throw new Error(`V7.74 原型内容哈希不匹配，拒绝提取：${sourceSha256}`)
}
const groupsSource = extractBalanced(source, 'const groups =', '[', ']')
const toolsSource = extractBalanced(source, 'const tools =', '{', '}')
// V7.74 keeps the user-facing request table in the later requirement-audit
// block.  It intentionally hides internal/adaptive parameters, so extracting
// only the first `tools` object would expose an earlier parameter contract.
const requirementsSource = extractBalanced(source, 'const audit =', '{', '}')
const deepClusterDemoSource = extractBalanced(source, 'const demoDocuments =', '[', ']')
const deepRuntimeSource = extractThrough(
  source,
  'const deepClusterTool = tools["deep-cluster"];',
  'deepClusterTool.response = deepClusterTool.demoBatchTextResult;'
)
const evaluationReportSource = extractBalanced(source, 'const EVALUATION_REPORT =', '{', '}')

// The final deep-cluster examples are produced by deterministic functions in
// the locked prototype rather than being literals in the first tool catalog.
// Execute only that bounded, data-only block and serialize its resulting data.
const runtimeTools = Function(`"use strict"; return (${toolsSource});`)()
Function('tools', 'cloneJson', 'window', `"use strict"; ${deepRuntimeSource}`)(
  runtimeTools,
  value => JSON.parse(JSON.stringify(value)),
  {}
)
const evaluationReport = Function(`"use strict"; return (${evaluationReportSource});`)()
for (const key of ['demoBatchTextResult', 'demoBatchFileResult', 'response']) {
  const response = runtimeTools['deep-cluster']?.[key]
  if (!response) continue
  response.data ||= {}
  response.data.training_evaluation = JSON.parse(JSON.stringify(evaluationReport))
  response.data.manual_correction = JSON.parse(JSON.stringify(evaluationReport.correction_loop))
  response.meta ||= {}
  response.meta.prototype_data_notice = evaluationReport.notice
  response.meta.supported_result_formats = ['json', 'csv']
}
const deepClusterRuntime = runtimeTools['deep-cluster']
const clusterLabelScriptStart = source.indexOf('<script id="v705-cluster-label-requirement-script">')
const clusterLabelRuntimeSource = extractBetween(
  source,
  'const cloneV705 =',
  'function buildPythonV705(',
  clusterLabelScriptStart
)
const emptyDocumentStub = {
  getElementById: () => null,
  querySelector: () => null,
  querySelectorAll: () => [],
  createElement: () => ({})
}
const clusterLabelRuntimeResponses = Function(
  'targetTool', 'document', 'window', 'tools',
  `"use strict"; ${clusterLabelRuntimeSource}\nreturn { demoDocuments: deepClusterDocumentsV731, batchText: targetTool.response, batchFile: makeResponseV705('batch', sampleValidationV731('batch')), history: makeResponseV705('existing-result', sampleValidationV731('existing-result')) };`
)(runtimeTools['cluster-label'], emptyDocumentStub, {}, runtimeTools)
const structuredReviewScriptStart = source.indexOf('<script id="v710-structured-review-requirement-script">')
const structuredReviewRuntimeSource = extractBetween(
  source,
  'const esc =',
  'const previousBuildPython =',
  structuredReviewScriptStart
)
const structuredReviewRuntime = Function(
  'tool', 'document', 'window', 'tools', 'escapeHtml',
  `"use strict"; ${structuredReviewRuntimeSource}\nreturn { demoDocuments: DEMO_DOCS, batchText: buildReviewResponse('batch-text', false), batchFile: buildReviewResponse('batch', false), collection: buildReviewResponse('collection', false) };`
)(runtimeTools['structured-review'], emptyDocumentStub, {}, runtimeTools, value => String(value ?? ''))
const styleBlocks = [...source.matchAll(/<style\b[^>]*>([\s\S]*?)<\/style>/gi)].map((match) => match[1].trim())
const scriptCount = [...source.matchAll(/<script\b/gi)].length

const dataOutput = `// 由 V7.74 HTML 原型机械提取。不要手工修改；业务修订写入 tool-overrides.ts。\nexport const groups = ${groupsSource}\n\nexport const tools = ${toolsSource}\n\nconst param = (name, type, required, description) => [name, type, required, description]\nexport const requirements = ${requirementsSource}\n\nexport const deepClusterDemoDocuments = ${deepClusterDemoSource}\n\nexport const deepClusterRuntime = ${JSON.stringify(deepClusterRuntime, null, 2)}\n\nexport const clusterLabelRuntimeResponses = ${JSON.stringify(clusterLabelRuntimeResponses, null, 2)}\n\nexport const structuredReviewRuntime = ${JSON.stringify(structuredReviewRuntime, null, 2)}\n`
const cssOutput = `/* 由 V7.74 HTML 原型按源顺序合并，共 ${styleBlocks.length} 个样式块。 */\n${styleBlocks.join('\n\n')}`
const manifest = {
  sourceFile,
  sourceSha256,
  sourceBytes: Buffer.byteLength(source),
  sourceLines: source.split(/\r?\n/).length,
  styleBlocks: styleBlocks.length,
  scriptBlocks: scriptCount,
  generatedAt: new Date().toISOString(),
}

await mkdir(resolve(projectDirectory, 'src/data'), { recursive: true })
await mkdir(resolve(projectDirectory, 'src/styles'), { recursive: true })
await mkdir(resolve(projectDirectory, 'parity'), { recursive: true })
await writeFile(resolve(projectDirectory, 'src/data/prototype.generated.js'), dataOutput, 'utf8')
await writeFile(resolve(projectDirectory, 'src/styles/prototype.generated.css'), cssOutput, 'utf8')
await writeFile(resolve(projectDirectory, 'parity/prototype-manifest.json'), `${JSON.stringify(manifest, null, 2)}\n`, 'utf8')

console.log(JSON.stringify(manifest, null, 2))
