<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch, watchEffect } from 'vue'
import type { InputMode } from '../types'
import { databaseResourceCatalog } from '../data/database-preview'
import { listSemanticResources, parseCitationMetadata, uploadSemanticResource } from '../services/api'

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
      { key: 'clc_labeled_data', label: '标准中图分类号标注数据', description: '支撑分类号判定、路径展示与校验', placeholder: '请选择标注数据版本', required: true },
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
const selectedResources = reactive<Record<string, string>>({})
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
const runtimeResourceCatalog = reactive<Record<string, typeof databaseResourceCatalog[string]>>({})
const resourceLoadError = ref('')
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
    const source = sourceModes[field.key]
    if (source === 'embedded') return
    payload[field.key] = source === 'upload'
      ? uploadedResources[field.key] || { source: 'upload', resource_id: null }
      : { source: 'database', resource_id: selectedResources[field.key] || null }
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
    citationParseState.value = 'empty'
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

function handleResourceUpload(event: Event, key: string) {
  uploadedResources[key] = (event.target as HTMLInputElement).files?.[0] || null
}

// 每字段记录文件 input 引用,取消时同步清空原生 value(否则重选同一文件不触发 change)
const resourceFileInputs: Record<string, HTMLInputElement | null> = {}
function setResourceFileInput(key: string, el: unknown) {
  resourceFileInputs[key] = (el as HTMLInputElement) || null
}
function clearUploadedResource(key: string) {
  uploadedResources[key] = null
  if (resourceFileInputs[key]) resourceFileInputs[key]!.value = ''
}

async function saveResourceToDatabase(key: string) {
  const file = uploadedResources[key]
  if (!file) { resourceSaveError.value = '请先选择要上传的资源文件'; return }
  savingResourceKey.value = key
  resourceSaveError.value = ''
  try {
    const res = await uploadSemanticResource(file, key)
    const rid = res?.data?.resource_id
    if (!rid) throw new Error('资源未登记入库')
    await loadRuntimeResources()
    selectedResources[key] = rid
    sourceModes[key] = 'database'
  } catch (error) {
    resourceSaveError.value = error instanceof Error ? error.message : '资源保存失败'
  } finally {
    savingResourceKey.value = null
  }
}

function availableResources(key: string) {
  const resources = runtimeResourceCatalog[key] || []
  const wantedStatus = sourceModes[key] === 'history' ? 'history' : 'current'
  return resources.filter(item => (item.status || 'current') === wantedStatus)
}

function selectedResource(key: string) {
  return (runtimeResourceCatalog[key] || []).find(item => item.id === selectedResources[key])
}

async function loadRuntimeResources() {
  resourceLoadError.value = ''
  try {
    const response = await listSemanticResources()
    Object.keys(runtimeResourceCatalog).forEach(key => delete runtimeResourceCatalog[key])
    for (const item of response.data || []) {
      const key = String(item.resource_key || '')
      if (!key) continue
      ;(runtimeResourceCatalog[key] ||= []).push({
        id: String(item.id),
        name: String(item.name),
        version: String(item.version),
        recordCount: item.record_count == null ? '未配置' : `${item.record_count} 条`,
        language: String(item.language || '未配置'),
        updatedAt: String(item.updated_at || ''),
        status: item.status === 'history' ? 'history' : 'current',
      })
    }
    currentGroup.value?.fields.forEach(field => {
      selectedResources[field.key] = availableResources(field.key)[0]?.id || ''
    })
  } catch (error) {
    resourceLoadError.value = error instanceof Error ? error.message : '数据库资源读取失败'
  }
}

onMounted(loadRuntimeResources)

watch(() => props.toolId, () => {
  Object.keys(sourceModes).forEach(key => delete sourceModes[key])
  Object.keys(selectedResources).forEach(key => delete selectedResources[key])
  Object.keys(uploadedResources).forEach(key => delete uploadedResources[key])
  currentGroup.value?.fields.forEach(field => {
    sourceModes[field.key] = props.toolId === 'structured-review' ? 'embedded' : 'database'
    selectedResources[field.key] = availableResources(field.key)[0]?.id || ''
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

watch(sourceModes, modes => {
  Object.entries(modes).forEach(([key, sourceMode]) => {
    if (sourceMode === 'upload' || sourceMode === 'embedded') return
    const options = availableResources(key)
    if (!options.some(item => item.id === selectedResources[key])) selectedResources[key] = options[0]?.id || ''
  })
}, { deep: true })

watchEffect(() => emit('update:payload', requestPayload.value))
</script>

<template>
  <div v-if="toolId === 'rq-detect'" class="settings-card requirement-supplement-card">
    <div class="field"><label><span class="label-main">文本格式要求</span><small>可选；未设置时自动识别</small></label><select v-model="textFormatRequirement" class="select"><option>自动识别</option><option>纯文本</option><option>章节结构文本</option><option>JSON 结构文本</option></select></div>
    <div class="format-example-box"><b>格式说明</b><span>纯文本可直接粘贴正文；章节结构文本应保留标题层级；JSON 结构文本应包含章节名称和正文内容。</span></div>
  </div>

  <div v-if="(toolId === 'citation-sentiment' || toolId === 'citation-intent') && mode === 'text'" class="settings-card requirement-supplement-card citation-metadata-card">
    <div class="settings-title"><b>被引文献元数据</b><span>{{ mode === 'text' || mode === 'batch-text' ? '由用户填写或上传' : '从文件参考文献列表自动解析' }}</span></div>

    <div v-if="mode === 'text'" class="citation-manual-metadata-panel">
      <div class="citation-metadata-section-head"><b><span class="required-mark">*</span> 参考文献原始条目</b><span>必填；可选择粘贴或上传，解析后核对识别结果</span></div>
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
            <span>⇧</span><b>{{ citationUploadName || '点击上传参考文献条目' }}</b><small>支持 TXT、JSON、JSONL、CSV</small>
          </label>
          <button v-if="citationUploadName" class="hover-copy-btn resource-cancel-btn" type="button" @click="clearCitationReferenceFile">✕ 取消</button>
        </div>
        <div class="citation-parser-action-row">
          <span v-if="citationParsing" class="citation-parse-status">解析中…（大模型解析多条条目约需数秒）</span>
          <span v-else-if="citationParseState === 'parsed'" class="citation-parse-status success">✓ 已解析 {{ citationMetadataList.length }} 条，请核对下方信息</span>
          <span v-else-if="citationParseState === 'empty'" class="citation-parse-status warning">! {{ citationParseError || '请先粘贴或上传参考文献条目' }}</span>
          <span v-else class="citation-parse-status">粘贴或上传条目后，点击开始解析</span>
          <button class="outline-btn citation-parse-button" type="button" :disabled="citationParsing" @click="parseCitationReference">{{ citationParsing ? '解析中…' : '开始解析' }}</button>
        </div>
      </div>
      <div class="citation-parsed-metadata">
        <div v-for="(entry, index) in citationMetadataList" :key="index" class="citation-metadata-entry">
          <div class="citation-metadata-entry-head"><b>条目 {{ index + 1 }}<span v-if="entry.reference_index"> [{{ entry.reference_index }}]</span></b><button class="ghost-btn danger" type="button" @click="removeCitationMetaEntry(index)">删除</button></div>
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
          <span>⇧</span><b>{{ citationBatchMetadataFile?.name || '上传批量被引文献元数据' }}</b><small>支持 JSON、JSONL、CSV、XLSX、TXT</small>
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
        <span>⇧</span><b>{{ uploadedResources['document_metadata']?.name || '点击上传文献元数据' }}</b><small>支持 JSON、JSONL、CSV、XLSX</small>
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
        <p>{{ field.description }}</p>
        <div class="requirement-resource-controls">
          <select v-model="sourceModes[field.key]" class="select resource-source-select">
            <option value="database">从数据库选择当前资源</option>
            <option v-if="!['zh-classify', 'domain-classify', 'en-classify', 'en-keyword', 'citation-intent', 'general-ner', 'research-ner', 'domain-ner'].includes(toolId)" value="history">从数据库选择历史版本</option>
            <option value="upload">用户上传资源</option>
          </select>
          <select v-if="sourceModes[field.key] !== 'upload'" v-model="selectedResources[field.key]" class="select">
            <option value="" disabled>{{ field.placeholder }}</option>
            <!-- 展示层只渲染资源文件名：version 是内容摘要随机串（如 789b9168abd6），
                 不展示给用户；option value 仍传完整资源ID，接口参数不受影响 -->
            <option v-for="item in availableResources(field.key)" :key="item.id" :value="item.id">{{ item.name }}</option>
          </select>
          <div v-else class="resource-upload-wrap">
            <label class="resource-upload-zone">
              <input :ref="el => setResourceFileInput(field.key, el)" type="file" :accept="field.accept || '.json'" @change="handleResourceUpload($event, field.key)" />
              <span>⇧</span><b>{{ uploadedResources[field.key]?.name || `点击上传${field.label}` }}</b><small>仅支持 JSON 文件；后端自动兼容常见非标准包装与字段别名，转换失败直接报错，不会静默回退内置逻辑</small>
            </label>
            <button v-if="uploadedResources[field.key]" class="hover-copy-btn resource-cancel-btn" type="button" @click="clearUploadedResource(field.key)">✕ 取消</button>
          </div>
        </div>
        <div v-if="sourceModes[field.key] === 'upload'" class="requirement-resource-summary"><span>入库方式</span><em>上传成功后生成资源编号并保存为可复用数据库资源</em><button type="button" class="primary-btn" :disabled="savingResourceKey === field.key || !uploadedResources[field.key]" @click="saveResourceToDatabase(field.key)">{{ savingResourceKey === field.key ? '保存中…' : '保存到数据库' }}</button><div v-if="resourceSaveError" class="info-banner error" style="margin-top:8px">{{ resourceSaveError }}</div></div>
      </article>
    </div>
  </div>
</template>
