<script setup lang="ts">
import { computed, reactive, ref, watch, watchEffect } from 'vue'
import type { InputMode } from '../types'
import { parseCitationMetadata, uploadSemanticResource, validateSemanticResource, getIndexStatus } from '../services/api'

type ResourceField = {
  key: string
  label: string
  description: string
  placeholder: string
  required?: boolean
  accept?: string
}

const props = defineProps<{ toolId: string; mode: InputMode }>()
const emit = defineEmits<{ 'update:payload': [payload: Record<string, unknown>] }>()

const resourceGroups: Record<string, { title: string; description: string; fields: ResourceField[] }> = {
  'zh-classify': {
    title: '分类标准数据配置',
    description: '选择标准中图分类号标注数据',
    fields: [
      { key: 'clc_labeled_data', label: '标准中图分类号标注数据', description: '支撑分类号判定、路径展示与校验', placeholder: '请选择标注数据版本', required: true },
    ],
  },
  'en-classify': {
    title: '分类标准与映射规则',
    description: '跨语言映射后输出中图分类结果',
    fields: [
      { key: 'clc_labeled_data', label: '中图分类标准', description: '分类号与类目体系', placeholder: '请选择分类标准版本', required: true },
      { key: 'classification_standard_mapping_table', label: '映射规则', description: '英文术语对应中文标准表达', placeholder: '请选择映射规则版本', required: true },
    ],
  },
  'domain-classify': {
    title: '专业领域分类支撑资源',
    description: '选择专业分类规则与人工标注数据',
    fields: [
      { key: 'domain_classification_rules', label: '领域分类规则', description: '定义三级专业类目与判定规则', placeholder: '请选择领域分类规则', required: true },
      { key: 'manually_labeled_training_data', label: '人工标注训练数据', description: '支撑训练、校验与低置信排序', placeholder: '请选择人工标注数据', required: true },
    ],
  },
  'en-keyword': {
    title: '英文关键词识别资源',
    description: '用于术语消歧、规范化与标签映射',
    fields: [
      { key: 'domain_terminology_library', label: '领域术语库', description: '补充术语、缩写、别名与规范表达', placeholder: '请选择领域术语库', required: true },
      { key: 'classification_standard_mapping_table', label: '分类标准映射表', description: '将英文术语映射为科研分类标签', placeholder: '请选择分类标准映射表', required: true },
    ],
  },
  'citation-intent': {
    title: '引用意图训练资源',
    description: '选择清洗、统一且平衡的训练集',
    fields: [
      { key: 'preprocessed_training_set', label: '预处理后的训练集', description: '支撑意图判定与训练证据匹配', placeholder: '请选择训练集版本', required: true },
    ],
  },
  'general-ner': {
    title: '通用实体语料配置',
    description: '选择匹配语言和实体类型的标注语料',
    fields: [
      { key: 'general_domain_annotated_corpus', label: '通用领域标注语料', description: '支撑通用实体识别与校验', placeholder: '请选择通用领域标注语料', required: true },
    ],
  },
  'research-ner': {
    title: '科研实体语料配置',
    description: '科研语料与标注数据配套使用',
    fields: [
      { key: 'multi_domain_scientific_corpus', label: '多领域科研语料', description: '覆盖论文、报告与项目科研表达', placeholder: '请选择多领域科研语料', required: true },
      { key: 'manually_labeled_data', label: '人工标注数据', description: '监督科研实体识别', placeholder: '请选择人工标注数据', required: true },
    ],
  },
  'domain-ner': {
    title: '专业实体知识资源',
    description: '本体限定分类，标注数据支撑识别',
    fields: [
      { key: 'ontology_classification_system', label: '本体分类体系', description: '限定实体类型与分类层级', placeholder: '请选择当前本体分类体系', required: true },
      { key: 'domain_labeled_training_data', label: '领域标注训练数据', description: '支撑实体识别与本体映射', placeholder: '请选择当前领域标注训练数据', required: true },
    ],
  },
  'structured-review': {
    title: '综述文献元数据',
    description: '提供综述溯源所需元数据',
    fields: [
      { key: 'document_metadata', label: '文献元数据', description: '包含题名、作者、年份与来源等信息', placeholder: '请选择或上传文献元数据' },
    ],
  },
}

const sourceModes = reactive<Record<string, string>>({})
const uploadedResources = reactive<Record<string, File | null>>({})
const citationRawReference = ref('')
const citationParseState = ref<'idle' | 'parsed' | 'partial' | 'empty'>('idle')
const citationReferenceSource = ref<'paste' | 'upload'>('paste')
const citationUploadName = ref('')
const citationBatchMetadataText = ref('')
const citationBatchMetadataFile = ref<File | null>(null)
const citationFallbackMetadataText = ref('')
const citationFallbackMetadataFile = ref<File | null>(null)
// 被引文献元数据（多条）：参考文献条目整段粘贴/上传 → 后端 GLM 批量解析 → 可编辑列表
type CitationMetaEntry = { reference_index: number | null; title: string; year: string; authorsText: string; venue: string; doi: string }
const citationMetadataList = ref<CitationMetaEntry[]>([])
const citationParsing = ref(false)
const citationParseError = ref('')
const textFormatRequirement = ref('自动识别')
const currentGroup = computed(() => resourceGroups[props.toolId])

function parsedCitationBatchMetadata() {
  const text = citationBatchMetadataText.value.trim()
  if (!text) return null
  try {
    return JSON.parse(text)
  } catch {
    return text
  }
}

const requestPayload = computed<Record<string, unknown>>(() => {
  const payload: Record<string, unknown> = {}
  if (props.toolId === 'rq-detect') payload.text_format_requirement = textFormatRequirement.value

  if (props.toolId === 'citation-sentiment' || props.toolId === 'citation-intent') {
    if (props.mode === 'text') {
      payload.citation_metadata = citationMetadataList.value.map(entry => ({
        citation_marker: entry.reference_index ? `[${entry.reference_index}]` : '',
        reference_index: entry.reference_index,
        authors: entry.authorsText.split(/[;；,，]/).map(item => item.trim()).filter(Boolean),
        title: entry.title,
        work_name: entry.title,
        publication_year: entry.year,
        year: entry.year,
        venue: entry.venue,
        doi: entry.doi,
      }))
    } else {
      payload.citation_metadata = citationFallbackMetadataFile.value || citationFallbackMetadataText.value || { source: 'file_auto_parse' }
    }
  }

  currentGroup.value?.fields.forEach(field => {
    // 内置 = 不提交该资源字段，后端使用系统预置资源；仅用户上传时携带文件
    if (sourceModes[field.key] !== 'upload') return
    const file = uploadedResources[field.key]
    if (file) payload[field.key] = file
    else {
      // 切了"用户上传资源"但尚未选文件：带内部标记供提交校验拦截
      // （必填资源不能静默回退内置），提交前由 OnlineTester 剔除
      if (!Array.isArray(payload.__pending_uploads)) payload.__pending_uploads = []
      ;(payload.__pending_uploads as Array<{ key: string, label: string }>).push({ key: field.key, label: field.label })
    }
    // 分类知识库索引构建中：构建未完成禁止提交在线测试（2026-09-19 用户定调：
    // 构建中点在线测试要拦截报错提示等待，而不是带内置/词面检索直接跑），
    // 带内部标记供提交校验拦截，提交前由 OnlineTester 剔除
    if (resourceProbes[field.key]?.indexStatus === 'building') {
      if (!Array.isArray(payload.__building_uploads)) payload.__building_uploads = []
      ;(payload.__building_uploads as Array<{ key: string, label: string, progress: number }>).push({
        key: field.key, label: field.label,
        progress: Number(resourceProbes[field.key]?.indexProgress || 0),
      })
    }
  })
  return payload
})

function cleanCitationPart(value = '') {
  return value.replace(/^[\s,.;，；。]+|[\s,.;，；。]+$/g, '').trim()
}

function switchCitationReferenceSource(source: 'paste' | 'upload') {
  if (citationReferenceSource.value === source) return
  citationReferenceSource.value = source
  citationRawReference.value = ''
  citationUploadName.value = ''
  citationParseState.value = 'idle'
  citationMetadataList.value = []
}

async function parseCitationReference() {
  const raw = citationRawReference.value.trim()
  if (!raw) {
    citationParseState.value = 'idle'
    citationMetadataList.value = []
    return
  }
  citationParsing.value = true
  citationParseError.value = ''
  try {
    const response = await parseCitationMetadata(raw)
    const entries = (response.data || []) as Array<Record<string, unknown>>
    citationMetadataList.value = entries.map(entry => ({
      reference_index: entry.reference_index ?? null,
      title: String(entry.title || ''),
      year: entry.year == null ? '' : String(entry.year),
      authorsText: Array.isArray(entry.authors) ? entry.authors.join('; ') : String(entry.authors || ''),
      venue: String(entry.venue || ''),
      doi: String(entry.doi || ''),
    }))
    citationParseState.value = citationMetadataList.value.length ? 'parsed' : 'empty'
    if (!citationMetadataList.value.length) citationParseError.value = '未能解析出任何条目，请检查条目格式'
  } catch (error) {
    citationParseState.value = 'empty'
    citationParseError.value = error instanceof Error ? error.message : '解析失败，请检查条目格式'
  } finally {
    citationParsing.value = false
  }
}

function removeCitationMetaEntry(index: number) {
  citationMetadataList.value.splice(index, 1)
}

// 参考文献条目自动解析（2026-09-15 用户定调：粘贴/上传即解析，无需手动按钮）
let _refParseTimer: ReturnType<typeof setTimeout> | null = null
watch(citationRawReference, (val) => {
  if (_refParseTimer) clearTimeout(_refParseTimer)
  const raw = val.trim()
  if (!raw) return
  _refParseTimer = setTimeout(() => { parseCitationReference() }, 800)
})

async function handleCitationReferenceFile(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  citationUploadName.value = file?.name || ''
  citationParseState.value = 'idle'
  if (!file) return

  const fileText = (await file.text()).trim()
  let rawReference = fileText
  try {
    const parsedFile = JSON.parse(fileText)
    const firstRecord = Array.isArray(parsedFile) ? parsedFile[0] : parsedFile
    rawReference = firstRecord?.raw_reference
      || firstRecord?.reference_entry
      || firstRecord?.reference
      || firstRecord?.citation
      || fileText
  } catch {
    // TXT、CSV 等文本格式直接交给参考文献解析器处理。
  }
  citationRawReference.value = String(rawReference).trim()
}

const citationReferenceFileInput = ref<HTMLInputElement | null>(null)
const citationBatchMetadataFileInput = ref<HTMLInputElement | null>(null)
const citationFallbackMetadataFileInput = ref<HTMLInputElement | null>(null)
function clearCitationReferenceFile() {
  citationUploadName.value = ''
  citationRawReference.value = ''
  citationParseState.value = 'idle'
  if (citationReferenceFileInput.value) citationReferenceFileInput.value.value = ''
}
function clearCitationMetadataFile(target: 'batch' | 'fallback') {
  if (target === 'batch') citationBatchMetadataFile.value = null
  else citationFallbackMetadataFile.value = null
  const el = target === 'batch' ? citationBatchMetadataFileInput.value : citationFallbackMetadataFileInput.value
  if (el) el.value = ''
}
function handleCitationMetadataFile(event: Event, target: 'batch' | 'fallback') {
  const file = (event.target as HTMLInputElement).files?.[0] || null
  if (target === 'batch') citationBatchMetadataFile.value = file
  else citationFallbackMetadataFile.value = file
}

const savingResourceKey = ref<string | null>(null)
const resourceSaveError = ref('')
const resourceSaveNotice = ref('')
// 各资源字段上传文件的格式与字段说明（与后端 normalize.py 行有效性规则对应，
// 文案样式与深度聚类锚点上传一致：仅 .json：字段 + 字段）
const resourceFieldHints: Record<string, string> = {
  clc_labeled_data: '仅 .json：三个字段 clc_code（分类号）+ clc_name（类目名称）+ parent_code（父级分类号，可选）',
  domain_terminology_library: '仅 .json：canonical（标准术语）+ variants（变体/缩写/同义词）',
  manually_labeled_training_data: '仅 .json：text（示例文本）+ label（类目名，可不带分类号）',
  manually_labeled_data: '仅 .json：canonical（标准中文词）+ variants（变体列表）+ canonical_en（标准英文词）+ type（五类之一）',
  domain_labeled_training_data: '仅 .json：text（示例文本）+ entities（实体数组：text 实体词 + type 用本体类型 code）——教实体边界切法',
  general_domain_annotated_corpus: '仅 .json：text（示例文本）+ entities（实体数组：text 实体词 + type 四类之一 PERSON/LOCATION/ORGANIZATION/EVENT）',
  multi_domain_scientific_corpus: '仅 .json：text（示例文本）+ entities（实体数组：text 实体词 + type 五类之一 METHOD/DATASET/INSTRUMENT/THEORY/TOPIC）',
  training_samples: '仅 .json：编号 + 文本 + 题名',
  manually_labeled_category_data: '仅 .json：编号 + 人工标注类目标签',
  domain_classification_rules: '仅 .json：clc_code（分类号）+ clc_name（类目名）+ parent_code（父级分类号，构成三级树）',
  preprocessed_training_set: '仅 .json：document_title（题目）+ document_text（含引用句的文本）+ intent（分类结果：背景介绍/引入研究方法/结果比较）；reference_entries（参考文献条目）选填',
  ontology_classification_system: '仅 .json：types（类型数组：code 类型码 + name 中文名 + description 判定标准 + examples 示例词）；领域在请求参数下拉里选',
}
function fieldHint(key: string): string {
  // 映射表字段两个工具共用但格式不同（2026-09-19 用户反馈：两种格式混在一条
  // 提示里看不懂"怎么还有关键词"）——按当前工具只显示对应格式
  if (key === 'classification_standard_mapping_table') {
    return props.toolId === 'en-keyword'
      ? '仅 .json：term（英文术语）+ clc_code（分类号）+ clc_name（类目名）'
      : '仅 .json：term（英文术语）+ zh_term/label（中文标准表达）'
  }
  return resourceFieldHints[key] || '仅 .json'
}

// 资源预检状态（选文件即解析：加载/归一/大模型重构在参数录入阶段完成，
// 点击在线测试只跑功能——与 PDF 预解析同款架构）
type ResourceProbe = { status: 'checking' | 'ready' | 'error'; rows: number | null; normalizedBy: string | null; error: string; indexStatus: string; indexProgress: number }
const resourceProbes = reactive<Record<string, ResourceProbe>>({})

// 预检白名单（2026-09-15 用户定调）：先只对已测试通过的工具+资源槽开放
// "选文件即解析"；其余工具（NER/引用意图/深度聚类等）待测试通过后再加进来，
// 期间维持原有"提交时处理"的行为
const PRECHECK_TOOLS: Record<string, Set<string>> = {
  'zh-classify': new Set(['clc_labeled_data']),
  'en-classify': new Set(['clc_labeled_data', 'classification_standard_mapping_table']),
  'domain-classify': new Set(['domain_classification_rules', 'manually_labeled_training_data']),
  'en-keyword': new Set(['domain_terminology_library', 'classification_standard_mapping_table']),
  'citation-intent': new Set(['preprocessed_training_set']),
  'general-ner': new Set(['general_domain_annotated_corpus']),
  'research-ner': new Set(['multi_domain_scientific_corpus', 'manually_labeled_data']),
  'domain-ner': new Set(['ontology_classification_system', 'domain_labeled_training_data']),
}
function precheckEnabled(key: string): boolean {
  return PRECHECK_TOOLS[props.toolId]?.has(key) ?? false
}

function _resetProbe(key: string) {
  delete resourceProbes[key]
}

// 索引进度轮询：3s 一次直到 done/failed（进度条文案与文件解析一致）
async function pollIndexBuild(key: string, storageUri: string) {
  const file = uploadedResources[key]
  if (!file) return
  try {
    // 轻量轮询 GET /index-status（不重复上传/预检/触发构建）
    const resp = await getIndexStatus(storageUri) as Record<string, unknown>
    // 响应是 {code:0, data:{status,progress,...}}——业务字段在 data 层
    const st = (resp?.data ?? resp) as Record<string, unknown>
    const probe = resourceProbes[key]
    if (!probe || uploadedResources[key] !== file) return
    const status = String(st?.status || '')
    probe.indexStatus = status
    probe.indexProgress = Number(st?.progress || 0)
    if (status !== 'done') {
      if (status === 'failed') return
      setTimeout(() => { pollIndexBuild(key, storageUri) }, 2000)
    }
  } catch {
    // 轮询失败静默（不影响 ready 状态展示）
  }
}

async function handleResourceUpload(event: Event, key: string) {
  const file = (event.target as HTMLInputElement).files?.[0] || null
  // 仅放行 .json：accept 只过滤系统选择器，用户切"所有文件"仍可选 txt/csv
  if (file && !file.name.toLowerCase().endsWith('.json')) {
    uploadedResources[key] = null
    if (resourceFileInputs[key]) resourceFileInputs[key]!.value = ''
    if (precheckEnabled(key)) {
      resourceProbes[key] = { status: 'error', rows: null, normalizedBy: null, error: '仅支持标准 JSON 文件（CSV、JSONL、TXT 暂不支持）' }
    } else {
      resourceSaveError.value = '仅支持标准 JSON 文件（CSV、JSONL、TXT 暂不支持）'
    }
    return
  }
  uploadedResources[key] = file
  resourceSaveError.value = ''
  _resetProbe(key)
  if (!file || !precheckEnabled(key)) return  // 白名单外：维持原有提交时处理行为
  resourceProbes[key] = { status: 'checking', rows: null, normalizedBy: null, error: '', indexStatus: '', indexProgress: 0 }
  try {
    const res = await validateSemanticResource(file, key) as Record<string, unknown>
    if (uploadedResources[key] !== file) return  // 用户已换文件/取消：丢弃过期结果
    if (res?.valid) {
      resourceProbes[key] = { status: 'ready', rows: (res.rows as number) ?? null,
                              normalizedBy: (res.normalized_by as string) || null, error: '',
                              indexStatus: '', indexProgress: 0 }
      // CLC 大表索引构建进度（2026-09-19 用户定调：bge 编码过程要像文件解析
      // 一样有进度——validate 返回 index_build 后轮询 /index-status 渲染进度条）
      const ib = (res as Record<string, unknown>).index_build as Record<string, unknown> | undefined | null
      if (ib && ib.storage_uri) {
        const probe = resourceProbes[key]
        if (probe) {
          probe.indexStatus = String(ib.status || '')
          probe.indexProgress = Number(ib.progress || 0)
        }
        if (String(ib.status) !== 'done') pollIndexBuild(key, String(ib.storage_uri))
      }
    } else {
      resourceProbes[key] = { status: 'error', rows: null, normalizedBy: null,
                              error: String(res?.error || '资源文件校验失败') }
    }
  } catch (err) {
    if (uploadedResources[key] !== file) return
    resourceProbes[key] = { status: 'error', rows: null, normalizedBy: null,
                            error: err instanceof Error ? err.message : '资源预检请求失败', indexStatus: '', indexProgress: 0 }
  }
}

// 每字段记录文件 input 引用,取消时同步清空原生 value(否则重选同一文件不触发 change)
const resourceFileInputs: Record<string, HTMLInputElement | null> = {}
function setResourceFileInput(key: string, el: unknown) {
  resourceFileInputs[key] = (el as HTMLInputElement) || null
}
// 切换资源来源（内置↔用户上传）即清空该字段已选文件（2026-09-15）：
// 切回"用户上传"时上传框必须是空的等待重新选择，不残留之前的内容
function handleSourceModeChange(key: string) {
  uploadedResources[key] = null
  if (resourceFileInputs[key]) resourceFileInputs[key]!.value = ''
  resourceSaveError.value = ''
  _resetProbe(key)
}

function clearUploadedResource(key: string) {
  uploadedResources[key] = null
  if (resourceFileInputs[key]) resourceFileInputs[key]!.value = ''
  _resetProbe(key)
}


watch(() => props.toolId, () => {
  Object.keys(sourceModes).forEach(key => delete sourceModes[key])
  Object.keys(uploadedResources).forEach(key => delete uploadedResources[key])
  Object.keys(resourceProbes).forEach(key => delete resourceProbes[key])
  currentGroup.value?.fields.forEach(field => {
    sourceModes[field.key] = 'builtin'
  })
  citationRawReference.value = ''
  citationParseState.value = 'idle'
  citationReferenceSource.value = 'paste'
  citationUploadName.value = ''
  citationBatchMetadataText.value = ''
  citationBatchMetadataFile.value = null
  citationFallbackMetadataText.value = ''
  citationFallbackMetadataFile.value = null
  citationMetadataList.value = []
  textFormatRequirement.value = '自动识别'
}, { immediate: true })

watchEffect(() => emit('update:payload', requestPayload.value))
</script>

<template>
  <div v-if="toolId === 'rq-detect'" class="settings-card requirement-supplement-card">
    <div class="field"><label><span class="label-main">文本格式要求</span><small>可选；未设置时自动识别</small></label><select v-model="textFormatRequirement" class="select"><option>自动识别</option><option>纯文本</option><option>章节结构文本</option><option>JSON 结构文本</option></select></div>
    
  </div>

  <div v-if="(toolId === 'citation-sentiment' || toolId === 'citation-intent') && mode === 'text'" class="settings-card requirement-supplement-card citation-metadata-card">
    <div class="settings-title"><b>被引文献元数据</b><span>{{ mode === 'text' || mode === 'batch-text' ? '由用户填写或上传' : '从文件参考文献列表自动解析' }}</span></div>

    <div v-if="mode === 'text'" class="citation-manual-metadata-panel">
      <div class="citation-metadata-section-head"><b>参考文献原始条目</b><span>选填；可选择粘贴或上传，提供时作为判定辅助因素</span></div>
      <div class="citation-reference-parser">
        <div class="citation-reference-source-switch" role="radiogroup" aria-label="参考文献条目提供方式">
          <button type="button" :class="{ active: citationReferenceSource === 'paste' }" @click="switchCitationReferenceSource('paste')">粘贴条目</button>
          <button type="button" :class="{ active: citationReferenceSource === 'upload' }" @click="switchCitationReferenceSource('upload')">上传条目</button>
        </div>
        <div v-if="citationReferenceSource === 'paste'" class="field full citation-reference-paste-field">
          <label><span class="label-main">粘贴参考文献条目</span><small>支持一次粘贴多条（每行一条），中英文格式均可</small></label>
          <textarea v-model="citationRawReference" class="textarea compact" rows="5" placeholder="每行一条参考文献，例如：&#10;[1] 张三，李四. 科技文献语义分析研究[J]. 情报学报，2024，43(2)：120-130.&#10;[2] Smith J, et al. A survey of NLP. ACL, 2020."></textarea>
        </div>
        <div v-else class="resource-upload-wrap">
          <label class="resource-upload-zone citation-reference-upload-zone">
            <input ref="citationReferenceFileInput" type="file" accept=".txt,.json,.jsonl,.csv" @change="handleCitationReferenceFile" />
            <span>⇧</span><b>{{ citationUploadName || '点击上传参考文献条目' }}</b><small>支持 TXT/JSON/JSONL/CSV：参考文献条目原文</small>
          </label>
            <button v-if="citationUploadName" class="hover-copy-btn resource-cancel-btn" type="button" @click="clearCitationReferenceFile">✕ 取消</button>
          </div>
        <div class="citation-parser-action-row">
          <span v-if="citationParsing" class="citation-parse-status">解析中…（大模型解析多条条目约需数秒）</span>
          <span v-else-if="citationParseState === 'empty'" class="citation-parse-status warning">! {{ citationParseError || '请先粘贴或上传参考文献条目' }}</span>
        </div>
      </div>
      <div class="citation-parsed-metadata">
        <div v-for="(entry, index) in citationMetadataList" :key="index" class="citation-metadata-entry">
          <div class="citation-metadata-entry-head"><b>参考文献{{ entry.reference_index ? `[${entry.reference_index}]` : ` ${index + 1}` }}</b><button class="ghost-btn danger" type="button" @click="removeCitationMetaEntry(index)">删除</button></div>
          <div class="citation-metadata-form-grid">
            <div class="field"><label><span class="label-main">发表年份</span></label><input v-model="entry.year" class="input" placeholder="例如：2024" /></div>
            <div class="field"><label><span class="label-main">作者</span></label><input v-model="entry.authorsText" class="input" placeholder="多个作者用分号分隔" /></div>
            <div class="field"><label><span class="label-main"><span class="required-mark">*</span> 文献题名</span></label><input v-model="entry.title" class="input" placeholder="请输入被引文献题名" /></div>
            <div class="field"><label><span class="label-main">期刊或会议</span></label><input v-model="entry.venue" class="input" placeholder="请输入期刊或会议名称" /></div>
            <div class="field"><label><span class="label-main">DOI</span><small>选填</small></label><input v-model="entry.doi" class="input" placeholder="例如：10.xxxx/xxxxx" /></div>
          </div>
        </div>
      </div>
    </div>

    <div v-else-if="mode === 'batch-text'" class="citation-manual-metadata-panel">
      <div class="citation-metadata-section-head"><b>提供批量被引文献元数据</b><span>按引文标记或记录编号与每条引用文本关联</span></div>
      <div class="field citation-metadata-json"><label><span class="label-main"><span class="required-mark">*</span> 批量参考文献元数据</span><small>可以粘贴 JSON 数组，或直接上传元数据文件</small></label><textarea v-model="citationBatchMetadataText" class="textarea compact json-textarea" placeholder='[{"citation_marker":"[12]","raw_reference":"Zhang XX, Li XX..."}]'></textarea></div>
      <div class="resource-upload-wrap">
        <label class="resource-upload-zone citation-metadata-upload-zone">
          <input ref="citationBatchMetadataFileInput" type="file" accept=".json,.jsonl,.csv,.xlsx,.txt" @change="handleCitationMetadataFile($event, 'batch')" />
          <span>⇧</span><b>{{ citationBatchMetadataFile?.name || '上传批量被引文献元数据' }}</b><small>支持 JSON/JSONL/CSV/XLSX/TXT：引用标记 + 参考文献原文</small>
        </label>
        <button v-if="citationBatchMetadataFile" class="hover-copy-btn resource-cancel-btn" type="button" @click="clearCitationMetadataFile('batch')">✕ 取消</button>
        </div>
    </div>

  </div>

  <div v-if="toolId === 'structured-review' && mode === 'batch'" class="settings-card requirement-supplement-card structured-review-metadata-card">
    <div class="settings-title"><b>文献元数据</b><span>文献文件需同时提供元数据</span></div>
    <div class="field">
      <label><span class="label-main"><span class="required-mark">*</span> 文献元数据</span></label>
      <select v-model="sourceModes.document_metadata" class="select">
        <option value="embedded">从文献文件自动解析题名、作者、年份、来源、关键词和文献编号</option>
        <option value="upload">上传元数据文件进行补充或校正</option>
      </select>
    </div>
    <div v-if="sourceModes.document_metadata === 'upload'" class="resource-upload-wrap">
      <label class="resource-upload-zone">
        <input :ref="el => setResourceFileInput('document_metadata', el)" type="file" accept=".json,.jsonl,.csv,.xlsx" @change="handleResourceUpload($event, 'document_metadata')" />
        <span>⇧</span><b>{{ uploadedResources['document_metadata']?.name || '点击上传文献元数据' }}</b><small>支持 JSON/JSONL/CSV/XLSX：文献编号（或文件名）+ 题名 + 作者 + 年份 + 来源</small>
      </label>
      <button v-if="uploadedResources['document_metadata']" class="hover-copy-btn resource-cancel-btn" type="button" @click="clearUploadedResource('document_metadata')">✕ 取消</button>
      </div>
    <div class="info-banner">元数据按文献编号或文件名与文献集逐篇关联；缺失字段由文件解析结果补充。</div>
  </div>

  <div v-else-if="toolId === 'structured-review' && mode === 'collection'" class="settings-card requirement-supplement-card structured-review-metadata-card">
    <div class="settings-title"><b>文献元数据</b><span>随指定文献集参数一并读取</span></div>
    <div class="info-banner">系统从科技文献检索结果集、科技情报平台、科研管理系统或知识库读取题名、作者、年份、来源、关键词和文献编号。</div>
  </div>

  <div v-else-if="currentGroup && toolId !== 'structured-review'" class="settings-card requirement-supplement-card">
    <div class="requirement-resource-grid" :class="{ single: currentGroup.fields.length === 1 }">
      <article v-for="field in currentGroup.fields" :key="field.key" class="requirement-resource-item">
        <div class="requirement-resource-heading">
          <div><span v-if="field.required" class="required-mark">*</span><b>{{ field.label }}</b></div>
        </div>
        <p v-if="field.description">{{ field.description }}</p>
        <div class="requirement-resource-controls">
          <select v-model="sourceModes[field.key]" class="select resource-source-select" @change="handleSourceModeChange(field.key)">
            <option value="builtin">内置</option>
            <option value="upload">用户上传资源</option>
          </select>
          <div v-if="sourceModes[field.key] === 'upload'" class="resource-upload-wrap">
            <label class="resource-upload-zone">
              <input :ref="el => setResourceFileInput(field.key, el)" type="file" :accept="field.accept || '.json'" @change="handleResourceUpload($event, field.key)" />
              <span>⇧</span><b>{{ uploadedResources[field.key]?.name || `点击上传${field.label}` }}</b><small>{{ fieldHint(field.key) }}</small>
            </label>
            <button v-if="uploadedResources[field.key]" class="hover-copy-btn resource-cancel-btn" type="button" @click="clearUploadedResource(field.key)">✕ 取消</button>
            </div>
        </div>
        
        <p v-if="sourceModes[field.key] === 'upload' && resourceSaveError" class="anchor-format-hint" style="color:#c0392b">{{ resourceSaveError }}</p>
        <p v-if="sourceModes[field.key] === 'upload' && resourceSaveNotice" class="anchor-format-hint">{{ resourceSaveNotice }}</p>
        <p v-if="sourceModes[field.key] === 'upload' && resourceProbes[field.key]?.status === 'checking'" class="anchor-format-hint">⏳ 正在解析资源文件（结构非标准时将自动用大模型整理）…</p>
        <p v-if="sourceModes[field.key] === 'upload' && resourceProbes[field.key]?.status === 'ready'" class="anchor-format-hint" style="color:#1e8e3e">✓ 资源已就绪{{ resourceProbes[field.key]?.rows != null ? ` · 已解析 ${resourceProbes[field.key]?.rows} 条` : '' }}{{ resourceProbes[field.key]?.normalizedBy === 'glm' ? '（大模型已整理为标准格式，提交时直接复用）' : '' }}</p>
        <div v-if="sourceModes[field.key] === 'upload' && resourceProbes[field.key]?.indexStatus" style="display:flex;align-items:center;gap:10px;padding:4px 0;">
          <span class="parse-ring" :data-state="resourceProbes[field.key]?.indexStatus === 'done' ? 'done' : resourceProbes[field.key]?.indexStatus === 'failed' ? 'error' : 'parsing'" :style="`--p:${resourceProbes[field.key]?.indexProgress || 0}%`"><i>{{ resourceProbes[field.key]?.indexStatus === 'done' ? '✓' : resourceProbes[field.key]?.indexStatus === 'failed' ? '✗' : (resourceProbes[field.key]?.indexProgress || 0) + '%' }}</i></span>
          <span v-if="resourceProbes[field.key]?.indexStatus === 'done'" class="parse-text ok clc-progress-text">分类知识库构建完成，提交即用用户体系分类</span>
          <span v-else-if="resourceProbes[field.key]?.indexStatus === 'failed'" class="parse-text err clc-progress-text">分类知识库构建失败，可重新选文件重试</span>
          <span v-else class="parse-text clc-progress-text">构建分类知识库（bge 向量编码）{{ resourceProbes[field.key]?.indexProgress || 0 }}% —— 构建完成前暂不能提交在线测试</span>
        </div>
        <p v-if="sourceModes[field.key] === 'upload' && resourceProbes[field.key]?.status === 'error'" class="anchor-format-hint" style="color:#c0392b">✕ {{ resourceProbes[field.key]?.error }}</p>
      </article>
    </div>
  </div>
</template>
