<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import type { InputMode, ToolDefinition } from '../types'
import { endpointFor, modesFor, pretty, requestPayloadFor, supportsVisualization } from '../utils/tooling'
import { ApiRequestError, apiUrl, executeToolRequest, listCompatibleHistory, listDictionaries, listDocumentCollections, listSemanticResources, parseCitationMetadata, saveDictionary } from '../services/api'
import { requirementInputsFor } from '../data/requirement-contracts'
import ModeSwitch from './ModeSwitch.vue'
import RequirementSupplement from './RequirementSupplement.vue'

const props = defineProps<{ toolId: string; tool: ToolDefinition }>()
const emit = defineEmits<{ visualize: [response: unknown]; preview: [mode: InputMode] }>()
const mode = ref<InputMode>('text')
const running = ref(false)
const result = ref<unknown | null>(null)
const requestError = ref('')
const dictionaryMode = ref('system')
const weightBoost = ref('0.08')
const selectedDictionaryId = ref('')
const selectedClusterTaskId = ref('')
const selectedCollectionId = ref('')
const selectedNerRecordId = ref('')
const savedDictionaryOptions = ref<any[]>([])
const savingDict = ref(false)
const clusterTaskOptions = ref<any[]>([])
const documentCollectionOptions = ref<any[]>([])
const nerHistoryOptions = ref<any[]>([])
type ReviewDocument = {
  id: string
  title: string
  authors: string
  institutions: string
  publication_date: string
  source: string
  keywords: string
  text: string
}

type BatchTextItem = {
  id: number
  projectName: string
  title: string
  text: string
}

type CitationMetaEntry = { reference_index: number | null; title: string; year: string; authorsText: string; venue: string; doi: string }
type CitationBatchItem = {
  id: number
  title: string
  documentText: string
  citationSentence: string
  previousContext: string
  nextContext: string
  citationMarker: string      // 本条绑定的文献编号（如 [1]，句内多标记拆分后各卡不同）
  subSpan: string             // 本条引用对应的局部语义子片段（意图判定用，留空回退整句）
  sourceId?: number | null   // 自动展开来源:由哪张卡片提取生成(手工卡片为 null)
  refsText: string           // 本条引用的参考文献条目原文(粘贴)
  metaList: CitationMetaEntry[]  // 解析出的被引文献元数据(可多条)
  refsParsing: boolean
  refsError: string
}

type UploadedFileItem = {
  id: string
  file: File
  name: string
  size: number
  type: string
  documentId: string
  title: string
  authors: string
  publicationDate: string
  source: string
  keywords: string
}

const docs = reactive<ReviewDocument[]>([])
const batchTexts = reactive<BatchTextItem[]>([])
const citationBatchItems = reactive<CitationBatchItem[]>([])
const uploadedFiles = reactive<UploadedFileItem[]>([])
let batchItemSequence = 0
const form = reactive({ projectName: '', documentTitle: '', text: '', batchText: '', language: '自动识别', domain: '自动识别', threshold: '0.75', outputFormat: 'JSON', clusterDimension: 'technology', algorithm: 'auto', clusterCount: '', historyId: '', topic: '' })
const citationSingle = reactive({ documentText: '' })
type CitationCard = { id: number; marker: string; sentence: string; subSpan: string; previousContext: string; nextContext: string }
const citationCards = reactive<CitationCard[]>([])
let citationCardSeq = 0

// 句内多引用拆分：单条自然句含多个文献编号（[1][2][3] 或复合 [1,2]/[1-3]）时，
// 每个文献编号生成一条独立引用句记录（同一意图共用子片段的 [4][5][6] 同样拆分）。
// 每条携带：marker=绑定的文献编号；subSpan=标记所在子句（按，,；;切分）去掉
// 引用标记后的局部语义片段。原始完整句子不做截断，保留在 sentence 供上下文核对。
function splitSentenceByMarkers(sentence: string): Array<{ marker: string; subSpan: string }> {
  const markerRe = /\[\d+(?:\s*[,，\-–~]\s*\d+)*\]/g
  const matches = Array.from(sentence.matchAll(markerRe))
  if (!matches.length) return []
  // 子句分段（记录起止位置）：引用标记归属其起点所在的子句段；
  // [n,m] 复合标记内的逗号不是子句边界（扫描时跳过方括号内的分隔符）
  const clauseRanges: Array<[number, number]> = []
  let clauseStart = 0
  let inBracket = false
  for (let i = 0; i < sentence.length; i += 1) {
    const ch = sentence[i]
    if (ch === '[') inBracket = true
    else if (ch === ']') inBracket = false
    else if (!inBracket && '，,；;'.includes(ch)) {
      clauseRanges.push([clauseStart, i])
      clauseStart = i + 1
    }
  }
  clauseRanges.push([clauseStart, sentence.length])
  // 去全部引用标记+合并空白+去尾部句读标点，得到干净的局部语义片段
  const stripMarkers = (text: string) => text.replace(markerRe, '').replace(/\s+/g, ' ').trim().replace(/[。．.!！?？；;，,、]+$/, '').trim()
  const out: Array<{ marker: string; subSpan: string }> = []
  for (const match of matches) {
    // 复合标记展开为单编号：[1,2]/[1-3] → [1][2]…；各条复用同一子片段
    const nums: number[] = []
    for (const part of match[0].slice(1, -1).split(/[,，]/)) {
      const range = part.trim().match(/^(\d+)\s*[-–~]\s*(\d+)$/)
      if (range) {
        for (let n = Number(range[1]); n <= Number(range[2]); n += 1) nums.push(n)
      } else if (/^\d+$/.test(part.trim())) {
        nums.push(Number(part.trim()))
      }
    }
    const markerNums = nums.length ? nums : [Number(match[0].replace(/\D/g, '')) || 0]
    const markerPos = match.index ?? 0
    const clause = clauseRanges.find(([start, end]) => markerPos >= start && markerPos < end)
    const clauseText = clause ? stripMarkers(sentence.slice(clause[0], clause[1])) : ''
    const subSpan = clauseText || stripMarkers(sentence)
    for (const num of markerNums) out.push({ marker: `[${num}]`, subSpan })
  }
  return out
}

// 引用句自动解析：文献文本是用户唯一需要输入的内容；系统从文献文本解析出
// 全部引用句（含引用标记的句子+前句/后句上下文），以卡片列表展示（可编辑/删除）；
// 句内多个文献编号按编号拆分为多张卡片（sentence 保留完整原句，subSpan 为
// 各自的局部子片段）；被引文献元数据由用户在下方补充。
let citationAutoTimer: ReturnType<typeof setTimeout> | null = null
let citationCardsEdited = false   // 用户增删改过卡片后不再自动覆盖
const citationExtractedCount = ref(0)
function autoExtractCitation() {
  const text = citationSingle.documentText.trim()
  if (!text) { citationExtractedCount.value = 0; return }
  const sentences = text.split(/(?<=[。！？!?])\s*|(?<=\.)\s+|\n+/).map(s => s.trim()).filter(Boolean)
  const cards: CitationCard[] = []
  sentences.forEach((s, i) => {
    for (const { marker, subSpan } of splitSentenceByMarkers(s)) {
      cards.push({
        id: ++citationCardSeq,
        marker,
        sentence: s,
        subSpan,
        previousContext: i > 0 ? sentences[i - 1] : '（文档开头，无上文）',
        nextContext: i + 1 < sentences.length ? sentences[i + 1] : '（文档结尾，无下文）',
      })
    }
  })
  citationExtractedCount.value = cards.length
  if (!cards.length) return
  citationCards.splice(0, citationCards.length, ...cards)
}
watch(() => citationSingle.documentText, () => {
  if (citationCardsEdited) return
  if (citationAutoTimer) clearTimeout(citationAutoTimer)
  citationAutoTimer = setTimeout(autoExtractCitation, 600)
})

function markCitationCardsEdited() { citationCardsEdited = true }
function forceAutoExtractCitation() {
  citationCardsEdited = false
  autoExtractCitation()
}
// 批量文本：从该条的文献文本提取全部引用句——句内多文献编号同样按编号拆分，
// 第一条填入本卡，其余自动展开为同题目/同文献文本的新卡片（sourceId 标记来源，
// 重复提取时先清理旧的）
function autoExtractBatchCitation(item: CitationBatchItem) {
  const text = (item.documentText || '').trim()
  if (!text) { requestError.value = '请先填写本条的文献文本，再自动提取引用句。'; return }
  const sentences = text.split(/(?<=[。！？!?])\s*|(?<=\.)\s+|\n+/).map(s => s.trim()).filter(Boolean)
  const hits: Array<{ s: string, i: number, marker: string, subSpan: string }> = []
  sentences.forEach((s, i) => {
    for (const { marker, subSpan } of splitSentenceByMarkers(s)) hits.push({ s, i, marker, subSpan })
  })
  if (!hits.length) { requestError.value = '本条文献文本中未发现引用标记（如 [1]），请手动填写引用句。'; return }
  requestError.value = ''
  const fill = (target: CitationBatchItem, hit: { s: string, i: number, marker: string, subSpan: string }) => {
    target.citationSentence = hit.s
    target.previousContext = hit.i > 0 ? sentences[hit.i - 1] : '（文档开头，无上文）'
    target.nextContext = hit.i + 1 < sentences.length ? sentences[hit.i + 1] : '（文档结尾，无下文）'
    target.citationMarker = hit.marker
    target.subSpan = hit.subSpan
  }
  fill(item, hits[0])
  // 清掉本卡之前展开的旧卡片（重复点击幂等），再按剩余引用句展开
  for (let i = citationBatchItems.length - 1; i >= 0; i -= 1) {
    if (citationBatchItems[i].sourceId === item.id) citationBatchItems.splice(i, 1)
  }
  for (const hit of hits.slice(1)) {
    const card: CitationBatchItem = {
      id: ++batchItemSequence,
      title: item.title,
      documentText: item.documentText,
      citationSentence: '',
      previousContext: '',
      nextContext: '',
      citationMarker: '',
      subSpan: '',
      sourceId: item.id,
      refsText: item.refsText,
      metaList: JSON.parse(JSON.stringify(item.metaList)),
      refsParsing: false,
      refsError: '',
    }
    fill(card, hit)
    citationBatchItems.push(card)
  }
}
function removeCitationCard(id: number) {
  markCitationCardsEdited()
  const index = citationCards.findIndex(c => c.id === id)
  if (index >= 0) citationCards.splice(index, 1)
}
// 批量文本：解析本条引用数据的参考文献条目 → 多条可编辑元数据
async function parseBatchCitationRefs(item: CitationBatchItem) {
  const raw = (item.refsText || '').trim()
  if (!raw) { item.refsError = '请先粘贴本条的参考文献条目'; return }
  item.refsParsing = true
  item.refsError = ''
  try {
    const response = await parseCitationMetadata(raw)
    const entries = (response.data || []) as Array<Record<string, unknown>>
    item.metaList = entries.map(entry => ({
      reference_index: entry.reference_index ?? null,
      title: String(entry.title || ''),
      year: entry.year == null ? '' : String(entry.year),
      authorsText: Array.isArray(entry.authors) ? entry.authors.join('; ') : String(entry.authors || ''),
      venue: String(entry.venue || ''),
      doi: String(entry.doi || ''),
    }))
    if (!item.metaList.length) item.refsError = '未能解析出任何条目，请检查格式'
  } catch (error) {
    item.refsError = error instanceof Error ? error.message : '解析失败，请检查条目格式'
  } finally {
    item.refsParsing = false
  }
}
function removeBatchMetaEntry(item: CitationBatchItem, index: number) {
  item.metaList.splice(index, 1)
}
// 深度聚类锚点资源:先选文件,点提交后上传入库并自动选中;取消则清空待上传文件
const anchorTrainFile = ref<File | null>(null)
const anchorGoldFile = ref<File | null>(null)
const anchorUploadingKey = ref('')
let anchorFileInput: HTMLInputElement | null = null
function handleAnchorFileChange(resourceKey: string, event: Event) {
  anchorFileInput = event.target as HTMLInputElement
  const file = (event.target as HTMLInputElement).files?.[0] || null
  if (resourceKey === 'training_samples') anchorTrainFile.value = file
  else anchorGoldFile.value = file
}
function clearAnchorFile(resourceKey: string) {
  if (resourceKey === 'training_samples') anchorTrainFile.value = null
  else anchorGoldFile.value = null
  if (anchorFileInput) anchorFileInput.value = ''
}
async function submitAnchorResource(resourceKey: string) {
  const file = resourceKey === 'training_samples' ? anchorTrainFile.value : anchorGoldFile.value
  if (!file) return
  anchorUploadingKey.value = resourceKey
  try {
    const formData = new FormData()
    formData.append('resource_key', resourceKey)
    formData.append('upload', file)
    const response = await fetch(apiUrl('/api/v1/semantic-resources/upload'), { method: 'POST', body: formData })
    const data = await response.json()
    if (data.code === 0) {
      const rid = data.data?.resource_id
      await loadAnchorOptions()
      if (resourceKey === 'training_samples') {
        selectedAnchorTrain.value = rid
        anchorTrainFile.value = null
        anchorTrainSource.value = 'database'
      } else {
        selectedAnchorGold.value = rid
        anchorGoldFile.value = null
        anchorGoldSource.value = 'database'
      }
      if (anchorFileInput) anchorFileInput.value = ''
    } else {
      requestError.value = data.detail || '上传失败'
    }
  } catch (error) {
    requestError.value = error instanceof Error ? error.message : '上传请求失败'
  } finally {
    anchorUploadingKey.value = ''
  }
}
const supplementalPayload = ref<Record<string, unknown>>({})
const labelLengthLimit = ref(12)
const labelLanguageType = ref('auto')
const customDictionaryName = ref('')
const customDictionaryTerms = ref('')
const customDictionaryFile = ref<File | null>(null)
const modes = computed(() => modesFor(props.tool))
const hasResult = computed(() => result.value !== null)
// 发表时间不能晚于今天(原生 date 选择器 max 属性)
const todayDateStr = new Date().toISOString().slice(0, 10)
const languageMismatch = computed(() => {
  const value = (result.value as Record<string, unknown> | null)?.language_mismatch
  return typeof value === 'string' ? value : ''
})
const canVisualize = computed(() => supportsVisualization(props.toolId))
const selectedClusterTask = computed(() => clusterTaskOptions.value.find(item => item.id === selectedClusterTaskId.value))
const selectedCollection = computed(() => documentCollectionOptions.value.find(item => item.id === selectedCollectionId.value))
const selectedNerRecord = computed(() => nerHistoryOptions.value.find(item => item.id === selectedNerRecordId.value))
const previewSentence = computed(() => {
  const s = selectedNerRecord.value?.sentence || ''
  // 文件上传的 NER 记录 sentence 是临时文件路径,不展示路径本身
  if (s.startsWith('/tmp/') || s.startsWith('/root/') || s.endsWith('.pdf')) {
    const n = selectedNerRecord.value?.entities?.length || 0
    return `(文件上传的NER记录,含 ${n} 个实体,提交后系统自动读取原文执行依存句法分析与关系抽取)`
  }
  return s.length > 1000 ? s.slice(0, 1000) + '…' : s
})

// 依存句法预览:选择上游记录后调后端 GLM 生成真实依存弧
const dependencyPreviewArcs = ref<any[]>([])
const dependencyPreviewLoading = ref(false)
const dependencyPreviewError = ref('')
watch(selectedNerRecordId, async recordId => {
  dependencyPreviewArcs.value = []
  dependencyPreviewError.value = ''
  if (!recordId || props.toolId !== 'relation-extract') return
  dependencyPreviewLoading.value = true
  try {
    const response = await fetch(apiUrl('/api/v1/relation/dependency-preview'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ upstream_entity_record_id: recordId }),
    })
    const data = await response.json()
    if (data.code === 0) {
      dependencyPreviewArcs.value = data.data || []
    } else {
      dependencyPreviewError.value = data.detail || data.message || '依存句法分析失败'
    }
  } catch (error) {
    dependencyPreviewError.value = error instanceof Error ? error.message : '依存句法分析请求失败'
  } finally {
    dependencyPreviewLoading.value = false
  }
}, { immediate: true })
const selectedDictionary = computed(() => savedDictionaryOptions.value.find(item => item.id === selectedDictionaryId.value))
const documentTitleToolIds = new Set(['zh-classify', 'en-classify', 'domain-classify', 'zh-keyword', 'en-keyword', 'rq-detect', 'zh-abstract-move', 'en-abstract-move', 'citation-sentiment', 'citation-intent'])
const needsDocumentTitle = computed(() => documentTitleToolIds.has(props.toolId))

// 深度聚类锚点资源（训练样本/人工标注类目，随「文本与文献元数据」面板展示）
type AnchorResourceOption = { id: string; name: string; version: string }
const anchorTrainOptions = ref<AnchorResourceOption[]>([])
const anchorGoldOptions = ref<AnchorResourceOption[]>([])
const anchorTrainSource = ref('database')
const anchorGoldSource = ref('database')
const selectedAnchorTrain = ref('')
const selectedAnchorGold = ref('')
async function loadAnchorOptions() {
  const response = await listSemanticResources()
  const items = (response.data || []) as Array<Record<string, unknown>>
  const toOption = (item: Record<string, unknown>) => ({ id: String(item.id), name: String(item.name), version: String(item.version), bundled: String(item.source_type ?? '') === 'bundled' })
  anchorTrainOptions.value = items.filter(item => item.resource_key === 'training_samples').map(toOption)
  anchorGoldOptions.value = items.filter(item => item.resource_key === 'manually_labeled_category_data').map(toOption)
}
// 默认选中系统内置预置资源（半监督系统原型引导）：不上传用户自定义文件时
// 界面默认即走内置分支；用户仍可改选数据库其它资源、上传或「不使用」。
const preferBuiltin = (list: Array<{ id: string; bundled: boolean }>) =>
  list.find(item => item.bundled)?.id || list[0]?.id || ''
watch(() => props.toolId, async toolId => {
  if (toolId !== 'deep-cluster') return
  try {
    await loadAnchorOptions()
    selectedAnchorTrain.value = preferBuiltin(anchorTrainOptions.value)
    selectedAnchorGold.value = preferBuiltin(anchorGoldOptions.value)
  } catch { /* 资源拉取失败不阻断聚类 */ }
}, { immediate: true })

const onlineRequestValues = computed<Record<string, unknown>>(() => {
  const values: Record<string, unknown> = { ...supplementalPayload.value }
  // 主文本字段 = 合同 inputs 中第一个非元数据字段(题目/项目名称不是主文本)
  const metadataFields = new Set(['document_title', 'project_name', 'cluster_task_id', 'upstream_ner_record_id'])
  const primaryField = (props.tool.params || []).find(
    ([name]) => !metadataFields.has(name) && !name.includes('.')
  )?.[0] || props.tool.params?.[0]?.[0]

  if (props.toolId === 'relation-extract') {
    values.upstream_ner_record_id = selectedNerRecordId.value
    return values
  }
  if (props.toolId === 'cluster-label') {
    values.cluster_phrase_sets = selectedClusterTask.value?.phraseSets || []
    values.label_length_limit = Number(labelLengthLimit.value)
    values.language_type = labelLanguageType.value
    values.distinctiveness_threshold = Number(form.threshold)
    return values
  }
  if (props.toolId === 'deep-cluster') {
    values.scientific_document_texts = mode.value === 'batch'
      ? uploadedFiles.map(item => item.file)
      : docs.map(item => ({ document_id: item.id, text: item.text }))
    values.document_metadata = mode.value === 'batch'
      ? uploadedFiles.map(item => ({ document_id: item.documentId, title: item.title, authors: item.authors, publication_date: item.publicationDate, source: item.source, keywords: item.keywords }))
      : docs.map(({ id: document_id, text: _text, ...metadata }) => ({ document_id, ...metadata }))
    values.cluster_dimension = form.clusterDimension
    values.clustering_algorithm_type = form.algorithm
    values.cluster_count = form.clusterCount === '' ? null : Number(form.clusterCount)
    values.output_format = form.outputFormat
    // 锚点辅助资源（可选）：选择后小样本聚类主题锚定到人工标注类目
    values.training_samples = anchorTrainSource.value === 'upload'
      ? { source: 'upload', resource_id: null }
      : { source: 'database', resource_id: selectedAnchorTrain.value || null }
    values.manually_labeled_category_data = anchorGoldSource.value === 'upload'
      ? { source: 'upload', resource_id: null }
      : { source: 'database', resource_id: selectedAnchorGold.value || null }
    return values
  }
  if (props.toolId === 'structured-review') {
    values.topic_or_keywords = form.topic
    if (mode.value === 'collection') {
      values.document_set = { source: 'database', collection_id: selectedCollectionId.value }
      values.document_metadata = { source: 'collection', collection_id: selectedCollectionId.value }
    } else if (mode.value === 'batch') {
      values.document_set = uploadedFiles.map(item => item.file)
      values.document_metadata = supplementalPayload.value.document_metadata instanceof File
        ? supplementalPayload.value.document_metadata
        : uploadedFiles.map(item => ({ document_id: item.documentId, title: item.title, authors: item.authors, publication_date: item.publicationDate, source: item.source, keywords: item.keywords }))
    } else {
      values.document_set = docs.map(item => ({ document_id: item.id, text: item.text }))
      values.document_metadata = docs.map(({ id: document_id, text: _text, ...metadata }) => ({ document_id, ...metadata }))
    }
    return values
  }
  if (props.toolId.startsWith('citation-')) {
    if (mode.value === 'text') {
      values.scientific_document_full_text = citationSingle.documentText
      // 提交解析出的全部引用句卡片（每条含上下文）；用户增删改过以卡片为准。
      // 句内多引用拆分后同一句多条记录：citation_marker 绑定各自文献编号，
      // citation_sub_span 为该条对应的局部语义子片段（后端意图判定优先采用）
      if (citationCards.length) {
        values.citation_sentence_and_context = citationCards.map(card => ({
          citation_sentence: card.sentence,
          previous_context: card.previousContext,
          next_context: card.nextContext,
          citation_marker: card.marker || undefined,
          citation_sub_span: card.subSpan || undefined,
        }))
      }
    } else if (mode.value === 'batch-text') {
      values.document_title = citationBatchItems.map(item => item.title.trim())
      if (props.toolId === 'citation-sentiment') values.scientific_document_full_text = citationBatchItems.map(item => ({ text: item.documentText }))
      values.citation_metadata = citationBatchItems.map(item => item.metaList.map(entry => ({
        citation_marker: entry.reference_index ? `[${entry.reference_index}]` : '',
        reference_index: entry.reference_index,
        authors: entry.authorsText.split(/[;；,，]/).map(s => s.trim()).filter(Boolean),
        title: entry.title,
        work_name: entry.title,
        publication_year: entry.year,
        year: entry.year,
        venue: entry.venue,
        doi: entry.doi,
      })))
      values.citation_sentence_and_context = citationBatchItems.map(item => ({
        citation_sentence: item.citationSentence,
        previous_context: item.previousContext,
        next_context: item.nextContext,
        citation_marker: item.citationMarker || undefined,
        citation_sub_span: item.subSpan || undefined,
      }))
    } else if (mode.value === 'file') {
      // citation-* 的主字段 citation_sentence_and_context 是结构化数据，不能作
      // 文件上传字段名（后端 /file 按 primary 字段名找不到文件会报「缺少上传
      // 字段」）；文件统一走通用上传字段，PDF 解析与引用句拆分由后端内置链路完成
      values.file = uploadedFiles[0]?.file || null
    } else if (mode.value === 'batch') {
      values.files = uploadedFiles.map(item => item.file)
    }
    return values
  }

  if (props.toolId === 'fund-move') {
    if (mode.value === 'text') {
      values.project_document_text = form.text
      values.project_name = form.projectName
    } else if (mode.value === 'batch-text') {
      values.project_document_text = batchTexts.map(item => ({ project_name: item.projectName, text: item.text }))
    } else {
      values.project_document_text = mode.value === 'file' ? uploadedFiles[0]?.file || null : uploadedFiles.map(item => item.file)
    }
    return values
  }

  if (primaryField) {
    if (mode.value === 'text') values[primaryField] = form.text
    if (mode.value === 'batch-text') values[primaryField] = batchTexts.map(item => ({
      id: `TEXT${String(item.id).padStart(3, '0')}`,
      ...(needsDocumentTitle.value && item.title.trim() ? { title: item.title.trim() } : {}),
      text: item.text,
    }))
    if (mode.value === 'file') values[primaryField] = uploadedFiles[0]?.file || null
    if (mode.value === 'batch') values[primaryField] = uploadedFiles.map(item => item.file)
  }
  if (props.toolId === 'definition-detect') {
    values.domain_label = form.domain || '自动识别'
    values.output_format_requirement = form.outputFormat
  }
  if (needsDocumentTitle.value && mode.value === 'text') values.document_title = form.documentTitle
  if (needsDocumentTitle.value && mode.value === 'batch-text' && !props.toolId.startsWith('citation-')) values.document_title = batchTexts.map(item => item.title.trim())
  if (props.toolId === 'domain-classify') values.professional_domain = form.domain
  if (props.toolId === 'zh-keyword') {
    // 系统预置模式不携带词典字段（后端 dictionary_usage=null、全部未命中属预期）
    if (dictionaryMode.value === 'system') {
      // 无词典参数
    } else if (dictionaryMode.value === 'saved') {
      // 请求模板白名单（strictRequirementPayload）只认合同字段 dictionary_id /
      // custom_dictionary：此前发 domain_terminology_dictionary 会被整字段过滤，
      // 后端收不到词典（dictionary_usage=null、命中全 false）。选中已存词典时
      // 必须完整携带资源ID。
      values.dictionary_id = selectedDictionaryId.value
    } else {
      values.custom_dictionary = {
        dictionary_name: customDictionaryName.value,
        weight_boost: Number(weightBoost.value),
        terms: customDictionaryTerms.value.split(/[,，;；\n]/).map(item => item.trim()).filter(Boolean),
        file: customDictionaryFile.value,
      }
    }
  }
  return values
})

// 真实接口接入时直接提交该对象；字段集合由 tooling 中的统一契约锁定。
const currentRequestPayload = computed(() => requestPayloadFor(props.tool, mode.value, onlineRequestValues.value))

// 深度聚类「类簇数量」越界判定：最低 1、最大类簇数量必须小于输入文献总数
// （如 4 篇文献最多 3 簇）。非空且越界时给出提示并禁用「在线测试」按钮。
const clusterCountError = computed(() => {
  if (props.toolId !== 'deep-cluster' || form.clusterCount === '' || form.clusterCount === null) return ''
  const count = Number(form.clusterCount)
  const total = mode.value === 'batch' ? uploadedFiles.length : docs.length
  if (!Number.isInteger(count) || count < 1) return '类簇数量必须是不小于 1 的整数（留空时自动确定）。'
  if (total > 1 && count >= total) return `类簇数量必须小于输入文献数量（当前 ${total} 篇，最大 ${total - 1}）。`
  return ''
})

function updateSupplementalPayload(payload: Record<string, unknown>) {
  supplementalPayload.value = payload
}

function handleDictionaryFile(event: Event) {
  customDictionaryFile.value = (event.target as HTMLInputElement).files?.[0] || null
}

const dictionaryFileInput = ref<HTMLInputElement | null>(null)
function clearDictionaryFile() {
  customDictionaryFile.value = null
  // 同时清空原生 input,否则重选同一文件不触发 change
  if (dictionaryFileInput.value) dictionaryFileInput.value.value = ''
}

async function saveCustomDictionary() {
  const name = customDictionaryName.value.trim()
  const terms = customDictionaryTerms.value.split(/[,，;；\n]/).map(item => item.trim()).filter(Boolean)
  if (!name) { requestError.value = '保存词典失败：请填写词典名称'; return }
  if (!terms.length) { requestError.value = '保存词典失败：请填写词典术语（文件词典将随在线测试上传，保存到数据库需手动填写术语）'; return }
  savingDict.value = true
  requestError.value = ''
  try {
    await saveDictionary({
      name,
      terms,
      language: props.toolId === 'en-keyword' ? 'en' : 'zh',
      weight_boost: Number(weightBoost.value),
    })
    await loadRuntimeDatabaseOptions()
    const created = savedDictionaryOptions.value.find(item => item.name === name)
    selectedDictionaryId.value = created?.id || savedDictionaryOptions.value[0]?.id || ''
    dictionaryMode.value = 'saved'
    customDictionaryName.value = ''
    customDictionaryTerms.value = ''
    customDictionaryFile.value = null
  } catch (error) {
    const message = error instanceof ApiRequestError ? error.message : (error instanceof Error ? error.message : '请求失败')
    requestError.value = `保存词典失败：${message}`
  } finally {
    savingDict.value = false
  }
}

function adjustThreshold(direction: 1 | -1) {
  const current = Number(form.threshold)
  const next = Math.min(1, Math.max(0, Math.round((current + direction * 0.05) * 100) / 100))
  form.threshold = next.toFixed(2)
}

function adjustWeightBoost(direction: 1 | -1) {
  const current = Number(weightBoost.value)
  const next = Math.min(0.5, Math.max(0, Math.round((current + direction * 0.01) * 100) / 100))
  weightBoost.value = next.toFixed(2)
}
const textInputLabel = computed(() => ({
  'zh-abstract-move': '中文科技文献摘要文本',
  'en-abstract-move': '英文科技论文摘要',
} as Record<string, string>)[props.toolId] || '文本')
const inputModeHint = computed(() => {
  if (props.toolId === 'rq-detect') return '支持单文本、批量文本、单文件、批量文件调用'
  if (props.toolId.startsWith('citation-')) return '支持引用句与上下文、批量结构化引用、单篇全文和批量全文'
  return `支持${modes.value.map(item => props.tool.modeLabels?.[item] || ({ text: '单文本', 'batch-text': '批量文本', file: '单文件', batch: '批量文件', collection: '已有文献集合', 'existing-result': '历史聚类任务' } as Record<string,string>)[item]).join('、')}调用`
})

function mapCollectionItem(item: any) {
  return {
    id: item.id, name: item.name, source: item.description || '数据库文献集',
    documentCount: item.document_count, timeRange: item.time_range || '由文献元数据确定',
    updatedAt: item.updated_at, topicSimilarity: item.topic_similarity,
  }
}

// 展示层时间格式化：ISO 串(2026-09-01T09:15:46.138858+00:00)只保留日期+时分
// （2026-09-01 09:15）。按原字符串字面截断而非 new Date() 本地时区转换，
// 避免时区偏移；传给后端的原始字段不做任何改动。
function formatDateTime(value: unknown): string {
  const text = String(value ?? '').trim()
  if (!text) return '—'
  const match = text.match(/^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2})/)
  return match ? `${match[1]} ${match[2]}` : text
}

// 结构化综述至少需要 3 篇文献：下拉只保留满足数量的文献集，
// 避免选中后提交才报"至少需要 3 项输入数据"。
function mapUsableCollections(data: any[]) {
  return (data || []).map(mapCollectionItem).filter(item => Number(item.documentCount) >= 3)
}

async function loadRuntimeDatabaseOptions() {
  const [dictionaryResponse, collectionResponse, clusterResponse, nerResponse] = await Promise.allSettled([
    listDictionaries(),
    listDocumentCollections(),
    listCompatibleHistory('cluster-label', 'cluster'),
    listCompatibleHistory('relation-extract', 'entity'),
  ])
  savedDictionaryOptions.value = dictionaryResponse.status === 'fulfilled'
    ? (dictionaryResponse.value.data || [])
        .map((item: any) => ({
          id: item.id, name: item.name, termCount: item.term_count, updatedAt: item.updated_at,
        }))
    : []
  documentCollectionOptions.value = collectionResponse.status === 'fulfilled'
    ? mapUsableCollections(collectionResponse.value.data)
    : []
  clusterTaskOptions.value = clusterResponse.status === 'fulfilled'
    ? (clusterResponse.value.data || []).map((item: any) => ({
        id: item.task_id, name: item.label, dimension: item.dimension || '未记录',
        completedAt: item.created_at, documentCount: item.document_count || 0,
        clusterCount: item.cluster_count || 0,
        phraseSets: (item.phrase_sets || []).map((row: any) => ({ clusterId: row.cluster_id, phrases: row.phrases || [] })),
      }))
    : []
  nerHistoryOptions.value = nerResponse.status === 'fulfilled'
    ? (nerResponse.value.data || []).map((item: any) => ({
        id: item.record_id, taskName: item.document_title || item.label,
        nerType: item.tool_id, documentId: item.document_id || '由原记录确定',
        sentenceId: item.sentence_id || '由原记录确定', sentence: item.sentence || '',
        entities: item.entities || [], completedAt: item.created_at,
      }))
    : []
  selectedDictionaryId.value = savedDictionaryOptions.value[0]?.id || ''
  selectedCollectionId.value = documentCollectionOptions.value[0]?.id || ''
  selectedClusterTaskId.value = clusterTaskOptions.value[0]?.id || ''
  selectedNerRecordId.value = nerHistoryOptions.value[0]?.id || ''
}

watch(() => props.toolId, () => {
  mode.value = modes.value[0]
  result.value = null
  requestError.value = ''
  dictionaryMode.value = 'system'
  selectedClusterTaskId.value = ''
  selectedCollectionId.value = ''
  selectedNerRecordId.value = ''
  docs.splice(0)
  batchTexts.splice(0)
  citationBatchItems.splice(0)
  uploadedFiles.splice(0)
  addBatchText()
  addBatchText()
  addCitationBatchItem()
  addCitationBatchItem()
  form.projectName = ''
  form.documentTitle = ''
  form.text = ''
  form.batchText = ''
  form.domain = props.toolId === 'domain-classify' ? '' : '自动识别'
  form.topic = ''
  customDictionaryName.value = ''
  customDictionaryTerms.value = ''
  customDictionaryFile.value = null
  void loadRuntimeDatabaseOptions()
}, { immediate: true })

// 结构化综述：研究主题变化时，按主题↔场景标签语义相似度刷新"已有文献集"下拉，
// 只显示与主题相似度≥阈值的场景文献集（用户设计闭环，省得文献集累积多了得一直找）。
let topicRefreshTimer: ReturnType<typeof setTimeout> | null = null
watch(() => form.topic, (topic) => {
  if (props.toolId !== 'structured-review') return
  if (topicRefreshTimer) clearTimeout(topicRefreshTimer)
  topicRefreshTimer = setTimeout(async () => {
    try {
      const response = await listDocumentCollections(topic)
      documentCollectionOptions.value = mapUsableCollections(response.data)
      if (!documentCollectionOptions.value.some(item => item.id === selectedCollectionId.value)) {
        selectedCollectionId.value = documentCollectionOptions.value[0]?.id || ''
      }
    } catch {
      // 过滤失败保持原列表
    }
  }, 400)
})

watch(mode, (next, previous) => {
  if (next !== previous && (next === 'file' || next === 'batch')) uploadedFiles.splice(0)
  if (next === 'batch-text' && batchTexts.length === 0) {
    addBatchText()
    addBatchText()
  }
  if (next === 'batch-text' && props.toolId.startsWith('citation-') && citationBatchItems.length === 0) {
    addCitationBatchItem()
    addCitationBatchItem()
  }
})

function addBatchText() {
  batchTexts.push({ id: ++batchItemSequence, projectName: '', title: '', text: '' })
}

function removeBatchText(id: number) {
  if (batchTexts.length <= 1) return
  const index = batchTexts.findIndex(item => item.id === id)
  if (index >= 0) batchTexts.splice(index, 1)
}

function addCitationBatchItem() {
  citationBatchItems.push({
    id: ++batchItemSequence,
    title: '',
    documentText: '',
    citationSentence: '',
    previousContext: '',
    nextContext: '',
    citationMarker: '',
    subSpan: '',
    refsText: '',
    metaList: [],
    refsParsing: false,
    refsError: '',
  })
}

function removeCitationBatchItem(id: number) {
  if (citationBatchItems.length <= 1) return
  const index = citationBatchItems.findIndex(item => item.id === id)
  if (index >= 0) citationBatchItems.splice(index, 1)
}

const MAX_BATCH_FILES = 20
function perFileLimitMB() { return props.toolId === 'structured-review' ? 80 : 50 }
function handleFileSelection(event: Event, multiple: boolean) {
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files || [])
  if (!multiple) uploadedFiles.splice(0)
  // 客户端即时校验:超限文件/超量批次在选择阶段直接拒绝,不必等后端报错
  const limitMB = perFileLimitMB()
  const oversized = files.filter(file => file.size > limitMB * 1024 * 1024)
  if (oversized.length) {
    requestError.value = `文件超过大小上限：${oversized.map(f => f.name).join('、')} 单个文件不能超过 ${limitMB}MB，请压缩后重新选择`
    input.value = ''
    return
  }
  if (multiple && uploadedFiles.length + files.length > MAX_BATCH_FILES) {
    requestError.value = `批量文件数量不能超过 ${MAX_BATCH_FILES} 个（错误码 42201）：当前已选 ${uploadedFiles.length} 个，本次又选择 ${files.length} 个`
    input.value = ''
    return
  }
  requestError.value = 
  files.forEach(file => {
    const duplicate = uploadedFiles.some(item => item.name === file.name && item.size === file.size && item.file.lastModified === file.lastModified)
    if (duplicate) return
    uploadedFiles.push({
      id: `${file.name}-${file.size}-${file.lastModified}`,
      file,
      name: file.name,
      size: file.size,
      type: file.name.split('.').pop()?.toUpperCase() || '文件',
      documentId: `DOC${String(uploadedFiles.length + 1).padStart(3, '0')}`,
      title: '',
      authors: '',
      publicationDate: '',
      source: '',
      keywords: '',
    })
  })
  input.value = ''
}

function removeUploadedFile(id: string) {
  const index = uploadedFiles.findIndex(item => item.id === id)
  if (index >= 0) uploadedFiles.splice(index, 1)
}

function formatFileSize(size: number) {
  if (size < 1024 * 1024) return `${Math.max(1, Math.round(size / 1024))} KB`
  return `${(size / 1024 / 1024).toFixed(1)} MB`
}

function addDoc() {
  docs.push({
    id: `DOC${String(docs.length + 1).padStart(3, '0')}`,
    title: '', authors: '', institutions: '', publication_date: '', source: '', keywords: '',
    text: '',
  })
}

function hasRequiredValue(value: unknown): boolean {
  if (value instanceof File) return value.size > 0
  if (typeof value === 'string') return value.trim().length > 0
  if (Array.isArray(value)) return value.length > 0 && value.some(hasRequiredValue)
  if (!value || typeof value !== 'object') return false
  const record = value as Record<string, unknown>
  if ('resource_id' in record || 'file' in record) return hasRequiredValue(record.resource_id) || hasRequiredValue(record.file)
  return Object.values(record).some(hasRequiredValue)
}

function requiredResourceError(): string {
  const primaryField = props.tool.params?.[0]?.[0]
  const excluded = new Set([
    primaryField,
    'document_set',
    'document_metadata',
    'domain_scientific_literature_data',
    'cluster_phrase_sets',
  ])
  const row = requirementInputsFor(props.toolId).find(([key, type, status]) =>
    status === 'required'
      && type.includes('resource')
      && !excluded.has(key)
      && !hasRequiredValue(supplementalPayload.value[key]),
  )
  return row ? `请配置必填资源“${row[3]}”。` : ''
}

function validateRequiredInputs(): string {
  if (props.toolId === 'relation-extract') return selectedNerRecordId.value ? '' : '请选择一条已完成的命名实体识别记录。'

  if (props.toolId === 'cluster-label') {
    if (!selectedClusterTaskId.value || !selectedClusterTask.value) return '请选择一项已完成的深度聚类任务。'
    if (!selectedClusterTask.value.phraseSets?.length) return '所选深度聚类任务没有可用的候选类目集合。'
    return ''
  }

  if (props.toolId === 'deep-cluster') {
    if (!form.clusterDimension) return '请选择聚类维度。'
    if (mode.value === 'batch-text') {
      if (docs.length < 4) return '深度聚类至少需要4篇科技文献文本。'
      const invalidIndex = docs.findIndex(item => !item.id.trim() || !item.title.trim() || !item.publication_date || !item.text.trim())
      if (invalidIndex >= 0) {
        const doc = docs[invalidIndex]
        const missing = [
          ...(!doc.id.trim() ? ['文献编号'] : []),
          ...(!doc.title.trim() ? ['题名'] : []),
          ...(!doc.publication_date ? ['发表时间'] : []),
          ...(!doc.text.trim() ? ['文本'] : []),
        ]
        return `文本${invalidIndex + 1}还缺少：${missing.join('、')}（均在每条文本卡片内），请补全后再测试。`
      }
    } else {
      if (uploadedFiles.length < 4) return '深度聚类至少需要上传4个文献文件。'
      const invalidIndex = uploadedFiles.findIndex(item => !item.documentId.trim() || !item.title.trim() || !item.publicationDate)
      if (invalidIndex >= 0) return `请完整填写文件${invalidIndex + 1}的文献编号、题名和发表时间。`
    }
    // 类簇数量约束：最低 1、最大必须小于输入文献数（留空=自动确定）。
    // 越界时同时禁用提交按钮（见 clusterCountError），提交前此处再兜底拦截。
    if (clusterCountError.value) return clusterCountError.value
    return ''
  }

  if (props.toolId === 'structured-review') {
    if (!form.topic.trim()) return '请输入研究主题或关键词。'
    if (mode.value === 'collection') return selectedCollectionId.value ? '' : '请选择指定文献集。'
    if (mode.value === 'batch-text') {
      if (docs.length < 3) return '结构化自动综述至少需要3篇文献文本。'
      const invalidIndex = docs.findIndex(item => !item.id.trim() || !item.title.trim() || !item.text.trim())
      if (invalidIndex >= 0) {
        const doc = docs[invalidIndex]
        const missing = [
          ...(!doc.id.trim() ? ['文献编号'] : []),
          ...(!doc.title.trim() ? ['题名'] : []),
          ...(!doc.text.trim() ? ['文本'] : []),
        ]
        return `文献${invalidIndex + 1}还缺少：${missing.join('、')}，请补全后再测试。`
      }
      return ''
    }
    return uploadedFiles.length >= 3 ? '' : '结构化自动综述至少需要上传3个文献文件。'
  }

  if (props.toolId.startsWith('citation-')) {
    if (mode.value === 'text') {
      if (!form.documentTitle.trim()) return '请输入题目（必填，用于标识响应结果及可视化弹窗中的当前文献）。'
      if (!citationSingle.documentText.trim()) return '请输入文献文本。'
      if (!citationCards.length) return '未解析出引用句：文献文本中未发现引用标记（如 [1]、[2,3]），可点击「从文献文本自动提取」或手动添加引用句。'
      const invalidCard = citationCards.find(card => !card.sentence.trim() || !card.previousContext.trim() || !card.nextContext.trim())
      if (invalidCard) return '存在引用句卡片未填写完整（引用句、上文、下文均需填写）。'
    } else if (mode.value === 'batch-text') {
      if (!citationBatchItems.length) return '请至少添加一条引用数据。'
      const noTitleIndex = citationBatchItems.findIndex(item => !item.title.trim())
      if (noTitleIndex >= 0) return `请输入引用数据${noTitleIndex + 1}的题目（必填，用于标识每条响应结果及可视化弹窗中的文献）。`
      const noMetaIndex = citationBatchItems.findIndex(item => !item.metaList.length)
      if (noMetaIndex >= 0) return `第 ${noMetaIndex + 1} 条引用数据尚未解析被引文献元数据，请粘贴参考文献条目并点击「开始解析」。`
      const invalidIndex = citationBatchItems.findIndex(item =>
        !item.documentText.trim()
          || !item.citationSentence.trim()
          || !item.previousContext.trim()
          || !item.nextContext.trim(),
      )
      if (invalidIndex >= 0) return `请完整填写引用数据${invalidIndex + 1}的必填内容。`
      const metadata = supplementalPayload.value.citation_metadata
      if (typeof metadata === 'string' && metadata.trim()) return '批量参考文献元数据必须是合法的 JSON 数组，或改为上传元数据文件。'
      if (!metadata || (Array.isArray(metadata) && metadata.length === 0)) return '请提供批量被引文献元数据。'
    } else if (mode.value === 'file' && !uploadedFiles.length) return '请选择一个文献文件。'
    else if (mode.value === 'batch' && !uploadedFiles.length) return '请至少上传一个文献文件。'

    if (mode.value === 'text' || mode.value === 'batch-text') {
      if (!hasRequiredValue(supplementalPayload.value.citation_metadata)) return '请提供被引文献元数据。'
    }
    return requiredResourceError()
  }

  if (props.toolId === 'domain-classify' && (!form.domain || form.domain === '请选择专业领域')) return '请选择专业领域。'
  if (mode.value === 'text' && !form.text.trim()) return `请输入${textInputLabel.value}。`
  if (mode.value === 'batch-text') {
    if (!batchTexts.length) return '请至少添加一条文本。'
    const invalidIndex = batchTexts.findIndex(item => !item.text.trim())
    if (invalidIndex >= 0) return `请输入文本${invalidIndex + 1}的内容。`
  }
  // 题目必填:弹窗可视化按题目/文件名标识当前文献,文本输入必须提供题目(文件模式由文件名兜底)
  if (needsDocumentTitle.value && mode.value === 'text' && !form.documentTitle.trim()) {
    return '请输入题目（必填，用于标识响应结果及可视化弹窗中的当前文献）。'
  }
  if (needsDocumentTitle.value && mode.value === 'batch-text' && !props.toolId.startsWith('citation-')) {
    const noTitleIndex = batchTexts.findIndex(item => !item.title.trim())
    if (noTitleIndex >= 0) return `请输入文本${noTitleIndex + 1}的题目（必填，用于标识每条响应结果及可视化弹窗中的文献）。`
  }
  if (mode.value === 'file' && !uploadedFiles.length) return '请选择一个文件。'
  if (mode.value === 'batch' && !uploadedFiles.length) return '请至少上传一个文件。'

  if (props.toolId === 'zh-keyword' && dictionaryMode.value === 'custom') {
    const terms = customDictionaryTerms.value.split(/[,，;；\n]/).map(item => item.trim()).filter(Boolean)
    if (!terms.length && !customDictionaryFile.value) return '已选择自定义领域词典，请填写词典术语或上传词典文件。'
  }
  return requiredResourceError()
}

async function run() {
  const validationError = validateRequiredInputs()
  if (validationError) {
    result.value = null
    requestError.value = `必填参数未完成：${validationError}`
    running.value = false
    return
  }
  running.value = true
  result.value = null
  requestError.value = ''
  try {
    result.value = await executeToolRequest(
      endpointFor(props.tool, mode.value),
      mode.value,
      currentRequestPayload.value,
    )
    // 引用工具文件模式：PDF 解析成功但未检测到引用标记时引擎返回空结果，
    // 给出业务提示（后端不报参数错误），避免用户只看到空列表
    if (props.toolId.startsWith('citation-') && (mode.value === 'file' || mode.value === 'batch')) {
      const data = (result.value as Record<string, unknown> | null)?.data as Record<string, unknown> | undefined
      const rows = (data?.citation_intent_results ?? data?.citation_sentiment_results ?? data?.results) as unknown
      if (Array.isArray(rows) && !rows.length) {
        requestError.value = `PDF解析完成，未检测到文中引用标记，无法执行${props.toolId === 'citation-intent' ? '引用意图' : '引用情感'}识别。请确认文献正文含 [n] 形式引用标记后重试。`
      }
    }
  } catch (error) {
    const message = error instanceof ApiRequestError
      ? error.message
      : error instanceof Error ? error.message : '接口请求失败，请检查 FastAPI 服务和网络连接。'
    requestError.value = `在线测试失败：${message}`
  } finally {
    running.value = false
  }
}
function clearResult() { result.value = null; requestError.value = '' }
// 结果框复制反馈：与调用示例/响应示例代码块一致的按钮本地状态切换
const resultCopied = ref(false)
let resultCopyTimer: ReturnType<typeof setTimeout> | undefined
async function copyResult() {
  if (!result.value) return
  try {
    await navigator.clipboard.writeText(pretty(result.value))
    resultCopied.value = true
    clearTimeout(resultCopyTimer)
    resultCopyTimer = setTimeout(() => { resultCopied.value = false }, 1200)
  } catch { resultCopied.value = false }
}
function downloadResult() { if (!result.value) return; const blob = new Blob([pretty(result.value)], { type: 'application/json' }); const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = `${props.toolId}_result.json`; a.click(); URL.revokeObjectURL(url) }
</script>

<template>
  <section class="section online-test-section">
    <div class="section-header">
      <div class="test-header-left"><h2 class="section-title">在线测试</h2><span class="pill ready">{{ running ? '执行中' : '就绪' }}</span></div>
      <button class="primary-btn" type="button" :disabled="running || !!clusterCountError" :title="clusterCountError || undefined" @click="run">{{ running ? '正在测试…' : '▶ 在线测试' }}</button>
    </div>
    <div class="test-panel">
      <div class="test-card request-card">
        <div class="test-card-header"><div class="test-card-title">请求参数</div></div>
        <div class="form-grid">
          <div v-if="toolId === 'relation-extract'" class="relation-source-card relation-source-first">
            <div class="field-heading"><b><span class="required-mark">*</span> 上游实体记录</b><span>必填；读取句子与实体，自动分析依存句法</span></div>
            <div class="database-selector-panel relation-ner-selector">
              <div class="database-selector-heading"><b>选择已完成的命名实体识别记录</b></div>
              <select v-model="selectedNerRecordId" class="select">
                <option v-if="!nerHistoryOptions.length" value="" disabled>暂无已完成的命名实体识别记录</option>
                <option v-for="item in nerHistoryOptions" :key="item.id" :value="item.id">{{ item.taskName || '未命名记录' }}</option>
              </select>
              <div v-if="!nerHistoryOptions.length" class="info-banner" style="margin-top:8px"><b>暂无数据</b><span>请先在"中英文通用领域命名实体识别"等工具中完成至少一次识别,再回来选择上游记录</span></div>
              <div v-if="selectedNerRecord" class="database-task-summary relation-record-summary">
                <span><small>识别类型</small><b>{{ selectedNerRecord.nerType }}</b></span><span><small>文献编号</small><b>{{ selectedNerRecord.documentId }}</b></span><span><small>句子编号</small><b>{{ selectedNerRecord.sentenceId }}</b></span><span><small>完成时间</small><b>{{ formatDateTime(selectedNerRecord.completedAt) }}</b></span>
              </div>
              <div v-if="selectedNerRecord" class="relation-readonly-preview">
                <div class="settings-title"><b>上游数据只读预览</b><span>数据库自动读取，仅供查看</span></div>
                <div class="relation-sentence-preview"><b>原始句子文本</b><p>{{ previewSentence }}</p></div>
                <div class="relation-entity-preview"><div><b>已识别实体列表</b><span>{{ selectedNerRecord.entities.length }} 个实体</span></div><ul><li v-for="entity in selectedNerRecord.entities" :key="`${entity.type}-${entity.text}`"><strong>{{ entity.text }}</strong><span>{{ entity.type }}</span></li></ul></div>
              </div>
              <div v-if="dependencyPreviewLoading" class="info-banner"><b>依存句法分析中...</b><span>正在对上游实体文本执行依存句法分析,约需数秒</span></div>
              <div v-else-if="dependencyPreviewError" class="info-banner relation-dependency-note"><b>依存句法预览不可用</b><span>{{ dependencyPreviewError }}</span></div>
              <div v-else-if="dependencyPreviewArcs.length" class="relation-dependency-preview">
                <div class="settings-title"><b>依存句法分析结果</b><span>共 {{ dependencyPreviewArcs.length }} 条依存弧,提交后系统基于此执行关系抽取</span></div>
                <div class="relation-dependency-scroll">
                  <table class="relation-dependency-table">
                    <thead><tr><th style="width:14%">句子编号</th><th style="width:24%">中心词</th><th style="width:22%">依存关系</th><th style="width:24%">依存词</th></tr></thead>
                    <tbody>
                      <tr v-for="(arc, index) in dependencyPreviewArcs" :key="index">
                        <td>{{ arc.sentence_id || '—' }}</td>
                        <td><b>{{ arc.head || '—' }}</b></td>
                        <td><span class="relation-dependency-label">{{ arc.relation || '—' }}</span></td>
                        <td><b>{{ arc.dependent || '—' }}</b></td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
              <div v-else class="info-banner relation-dependency-note"><b>内部自动处理</b><span>提交后，实体关系识别工具将对原始句子自动执行依存句法分析、实体对构造和关系判定，无需用户提供依存句法结果。</span></div>
            </div>
          </div>
          <div v-if="!['deep-cluster','cluster-label','structured-review','relation-extract'].includes(toolId)" class="field input-mode-field"><label><span class="label-main">输入方式</span><small>{{ inputModeHint }}</small></label><ModeSwitch v-model="mode" :modes="modes" :tool="tool" kind="在线测试输入方式" /></div>

          <div v-if="toolId === 'domain-classify'" class="field"><label><span class="label-main"><span class="required-mark">*</span> 专业领域</span><small>选择目标领域后执行三级分类</small></label><select v-model="form.domain" class="select"><option value="">请选择专业领域</option><option value="01">数学与计算科学</option><option value="02">力学与工程力学</option><option value="03">物理学与应用物理</option><option value="04">化学与化学科学</option><option value="05">天文学与空间科学</option><option value="06">地球科学与地质资源</option><option value="07">测绘遥感与地理信息</option><option value="08">气象海洋科学</option><option value="09">生物科学与生物技术</option><option value="10">医学与卫生健康</option><option value="11">药学与毒理学</option><option value="12">农业科学与农业工程</option><option value="13">林业畜牧兽医与水产</option><option value="14">材料科学与材料工程</option><option value="15">矿业与矿物加工</option><option value="16">石油与天然气工程</option><option value="17">冶金与金属加工</option><option value="18">机械工程与智能制造</option><option value="19">仪器仪表与计量检测</option><option value="20">能源与动力工程</option><option value="21">核科学与核工程</option><option value="22">电气工程与电力系统</option><option value="23">电子通信与半导体</option><option value="24">自动化与控制工程</option><option value="25">人工智能与计算机技术</option><option value="26">化学工程与过程工业</option><option value="27">轻工食品与纺织</option><option value="28">建筑与土木工程</option><option value="29">水利与水电工程</option><option value="30">交通运输工程</option><option value="31">航空航天工程</option><option value="32">环境与安全工程</option></select></div>

          <template v-if="toolId === 'deep-cluster'">
            <div class="field"><label><span class="label-main"><span class="required-mark">*</span> 聚类维度</span><small>选择本次聚类的语义分析视角</small></label><div class="dimension-options"><label :class="{ active: form.clusterDimension === 'technology' }"><input v-model="form.clusterDimension" type="radio" value="technology" /><span><b>技术路线聚类</b><small>重点分析文献采用的方法、模型结构、算法机制、数据处理流程和实验技术，将技术方案相近的文献聚合到<span class="dimension-term">同一类簇</span>。</small></span></label><label :class="{ active: form.clusterDimension === 'application_scenario' }"><input v-model="form.clusterDimension" type="radio" value="application_scenario" /><span><b>应用场景聚类</b><small>重点分析文献解决的任务、服务对象、行业领域、实际环境和应用目标，将面向相似使用场景的文献聚合到<span class="dimension-term">同一类簇</span>。</small></span></label></div></div>
            <div class="settings-card"><div class="settings-title"><b>算法与输出参数</b><span>可选算法、类簇数量与输出格式</span></div><div class="three-column"><div class="field"><label><span class="label-main">聚类算法类型</span></label><select v-model="form.algorithm" class="select"><option value="auto">自动选择</option><option value="kmeans">K-Means</option><option value="hierarchical">层次聚类</option><option value="hdbscan">HDBSCAN</option></select></div><div class="field"><label><span class="label-main">类簇数量</span></label><input v-model="form.clusterCount" class="input" type="number" min="1" step="1" placeholder="自动确定" /><small v-if="clusterCountError" class="field-error-hint" style="color:#d54949;display:block;margin-top:4px">{{ clusterCountError }}</small></div><div class="field"><label><span class="label-main">输出格式</span></label><select v-model="form.outputFormat" class="select"><option>JSON</option><option>CSV</option><option>数据库写入结构</option></select></div></div></div>
            <ModeSwitch v-model="mode" :modes="modes" :tool="tool" kind="深度聚类数据来源" />
          </template>

          <template v-if="toolId === 'cluster-label'">
            <div class="settings-card cluster-source-selector-card">
              <div class="settings-title"><b><span class="required-mark">*</span> 类簇短语集合</b><span>必填；从已完成的深度聚类结果获取</span></div>
              <div class="database-selector-panel cluster-task-selector">
                <div class="database-selector-heading"><b>选择已完成的深度聚类任务</b></div>
                <select v-model="selectedClusterTaskId" class="select">
                  <option v-if="!clusterTaskOptions.length" value="" disabled>暂无已完成的深度聚类任务</option>
                  <option v-for="task in clusterTaskOptions" :key="task.id" :value="task.id">{{ task.name || '未命名任务' }}</option>
                </select>
                <div v-if="!clusterTaskOptions.length" class="info-banner" style="margin-top:8px"><b>暂无数据</b><span>请先在"深度聚类工具"中完成至少一次聚类,再回来选择任务</span></div>
                <div v-if="selectedClusterTask" class="database-task-summary">
                  <span><small>聚类维度</small><b>{{ selectedClusterTask.dimension }}</b></span><span><small>文献数量</small><b>{{ selectedClusterTask.documentCount }} 篇</b></span><span><small>类簇数量</small><b>{{ selectedClusterTask.clusterCount }} 个</b></span><span><small>完成时间</small><b>{{ formatDateTime(selectedClusterTask.completedAt) }}</b></span>
                </div>
                <div v-if="selectedClusterTask" class="cluster-phrase-preview">
                  <div class="cluster-phrase-preview-title"><b>类簇短语预览</b><span>数据库将返回完整的类簇短语集合</span></div>
                  <div v-for="item in selectedClusterTask.phraseSets" :key="item.clusterId" class="cluster-phrase-preview-row"><strong>{{ item.clusterId }}</strong><span v-for="phrase in item.phrases" :key="phrase">{{ phrase }}</span></div>
                  <p v-if="selectedClusterTask.clusterCount > selectedClusterTask.phraseSets.length">另有 {{ selectedClusterTask.clusterCount - selectedClusterTask.phraseSets.length }} 个类簇，运行时从数据库完整读取。</p>
                </div>
                <div class="info-banner">用户选择的是深度聚类任务；后端根据任务编号读取类簇短语集合，再将该集合提交给标签生成算法。</div>
              </div>
            </div>
          </template>

          <template v-if="toolId === 'structured-review'">
            <div class="settings-card structured-review-scope-card"><div class="settings-title"><b>研究主题或关键词</b><span>限定结构化综述范围</span></div><div class="field"><label><span class="label-main"><span class="required-mark">*</span> 研究主题或关键词</span></label><input v-model="form.topic" class="input" placeholder="例如：多变量时间序列异常检测；联邦学习、时频融合" /></div></div>
            <ModeSwitch v-model="mode" :modes="modes" :tool="tool" kind="结构化综述数据来源" />
          </template>

          <template v-if="toolId === 'deep-cluster' && mode === 'batch-text'">
            <div class="special-panel">
              <div class="special-panel-head"><div><strong>文本与文献元数据</strong><span>逐条填写文本及对应元数据</span></div></div>
              <div v-if="!docs.length" class="empty-input"><b>尚未添加文本</b><span>至少添加 4 条，并为每条文本填写对应的文献元数据。</span><button class="outline-btn" @click="addDoc">＋ 添加第一条文本</button></div>
              <div v-for="(doc,index) in docs" :key="doc.id" class="document-card deep-cluster-document-card">
                <div class="document-card-head"><b>文本 {{ index + 1 }}</b><button class="ghost-btn danger" @click="docs.splice(index,1)">删除</button></div>
                <div class="settings-title deep-cluster-metadata-title"><b>文献元数据</b><span>与文本一并提交</span></div>
                <div class="two-column deep-cluster-metadata-grid">
                  <div class="field"><label><span class="label-main"><span class="required-mark">*</span> 文献编号</span></label><input v-model="doc.id" class="input" placeholder="例如：DOC001" /></div>
                  <div class="field"><label><span class="label-main"><span class="required-mark">*</span> 发表时间</span></label><input v-model="doc.publication_date" class="input" type="date" :max="todayDateStr" /></div>
                  <div class="field"><label><span class="label-main"><span class="required-mark">*</span> 题名</span></label><input v-model="doc.title" class="input" placeholder="请输入题名" /></div>
                  <div class="field"><label><span class="label-main">作者</span><small>可选</small></label><input v-model="doc.authors" class="input" placeholder="多人使用逗号分隔" /></div>
                  <div class="field"><label><span class="label-main">文献来源</span><small>可选</small></label><input v-model="doc.source" class="input" placeholder="期刊、会议、报告或其他来源" /></div>
                  <div class="field"><label><span class="label-main">关键词</span><small>可选</small></label><input v-model="doc.keywords" class="input" placeholder="多个关键词使用逗号分隔" /></div>
                </div>
                <div class="field deep-cluster-text-field"><label><span class="label-main"><span class="required-mark">*</span> 文本</span><small>支持各类科技文本，最多 8000 字</small></label><textarea v-model="doc.text" class="textarea compact" maxlength="8000" placeholder="请输入完整文本"></textarea></div>
              </div>
              <button v-if="docs.length" class="outline-btn deep-cluster-add-doc-btn" type="button" @click="addDoc">＋ 添加文本</button>
              <div class="two-column deep-cluster-metadata-grid deep-cluster-anchor-grid">
                <div class="field"><label><span class="label-main">训练样本</span><small>可选</small></label>
                  <div class="requirement-resource-controls">
                    <select v-model="anchorTrainSource" class="select resource-source-select"><option value="database">从数据库选择当前资源</option><option value="upload">用户上传资源</option></select>
                    <select v-if="anchorTrainSource === 'database'" v-model="selectedAnchorTrain" class="select"><option value="">不使用</option><option v-for="item in anchorTrainOptions" :key="item.id" :value="item.id">{{ item.name }}</option></select>
                    <div v-else class="resource-upload-wrap"><label class="resource-upload-zone"><input type="file" accept=".json" @change="handleAnchorFileChange('training_samples', $event)" /><span>⇧</span><b>{{ anchorTrainFile?.name || '点击上传训练样本' }}</b><small>仅标准 JSON 数组生效</small></label><div class="anchor-upload-actions"><button type="button" class="primary-btn" :disabled="anchorUploadingKey === 'training_samples' || !anchorTrainFile" @click="submitAnchorResource('training_samples')">{{ anchorUploadingKey === 'training_samples' ? '提交中…' : '提交' }}</button><button v-if="anchorTrainFile" class="hover-copy-btn resource-cancel-btn" type="button" @click="clearAnchorFile('training_samples')">✕ 取消</button></div></div><p class="anchor-format-hint">仅支持 JSON 文件</p>
                  </div>
                </div>
                <div class="field"><label><span class="label-main">人工标注类目标签数据</span><small>可选</small></label>
                  <div class="requirement-resource-controls">
                    <select v-model="anchorGoldSource" class="select resource-source-select"><option value="database">从数据库选择当前资源</option><option value="upload">用户上传资源</option></select>
                    <select v-if="anchorGoldSource === 'database'" v-model="selectedAnchorGold" class="select"><option value="">不使用</option><option v-for="item in anchorGoldOptions" :key="item.id" :value="item.id">{{ item.name }}</option></select>
                    <div v-else class="resource-upload-wrap"><label class="resource-upload-zone"><input type="file" accept=".json" @change="handleAnchorFileChange('manually_labeled_category_data', $event)" /><span>⇧</span><b>{{ anchorGoldFile?.name || '点击上传人工标注类目标签数据' }}</b><small>仅标准 JSON 数组生效</small></label><div class="anchor-upload-actions"><button type="button" class="primary-btn" :disabled="anchorUploadingKey === 'manually_labeled_category_data' || !anchorGoldFile" @click="submitAnchorResource('manually_labeled_category_data')">{{ anchorUploadingKey === 'manually_labeled_category_data' ? '提交中…' : '提交' }}</button><button v-if="anchorGoldFile" class="hover-copy-btn resource-cancel-btn" type="button" @click="clearAnchorFile('manually_labeled_category_data')">✕ 取消</button></div></div><p class="anchor-format-hint">仅支持 JSON 文件</p>
                  </div>
                </div>
              </div>
            </div>
          </template>

          <template v-else-if="toolId === 'cluster-label' && mode === 'batch-text'">
            <div class="settings-card"><div class="settings-title"><b>可选标签生成参数</b><span>可选标签长度、语言与差异阈值</span></div><div class="three-column"><div class="field"><label><span class="label-main">标签长度限制</span></label><input v-model="labelLengthLimit" class="input" type="number" min="1" /></div><div class="field"><label><span class="label-main">语言类型</span></label><select v-model="labelLanguageType" class="select"><option value="auto">自动</option><option value="zh">中文</option><option value="en">英文</option></select></div><div class="field"><label><span class="label-main">差异度阈值</span></label><div class="numeric-stepper"><input v-model="form.threshold" class="input numeric-stepper-input" type="text" inputmode="none" readonly aria-label="差异度阈值" /><span class="numeric-stepper-controls"><button type="button" aria-label="增加差异度阈值" :disabled="Number(form.threshold) >= 1" @click="adjustThreshold(1)">▲</button><button type="button" aria-label="减小差异度阈值" :disabled="Number(form.threshold) <= 0" @click="adjustThreshold(-1)">▼</button></span></div></div></div></div>
          </template>

          <template v-else-if="toolId === 'structured-review' && mode === 'batch-text'">
            <div class="special-panel structured-review-document-set">
              <div class="special-panel-head"><div><strong>文献集</strong><span>{{ docs.length }} 篇，至少需要 3 篇</span></div></div>
              <div v-if="!docs.length" class="empty-input"><b>尚未添加文献</b><span>逐篇录入文本及对应元数据。</span><button class="outline-btn" @click="addDoc">＋ 添加第一篇文献</button></div>
              <div v-for="(doc,index) in docs" :key="doc.id" class="document-card review-document-card-v634">
                <div class="document-card-head"><b>文献 {{ index + 1 }} · {{ doc.id }}</b><button class="ghost-btn danger" @click="docs.splice(index,1)">删除</button></div>
                <div class="settings-title review-metadata-title"><b>文献元数据</b><span>支撑团队分析、趋势计算与溯源</span></div>
                <div class="two-column review-document-meta-grid-v637">
                  <div class="field"><label><span class="label-main"><span class="required-mark">*</span> 文献编号</span></label><input v-model="doc.id" class="input" placeholder="例如：DOC001" /></div>
                  <div class="field"><label><span class="label-main"><span class="required-mark">*</span> 题名</span></label><input v-model="doc.title" class="input" placeholder="可填写科技文献题名" /></div>
                  <div class="field"><label><span class="label-main">作者</span></label><input v-model="doc.authors" class="input" placeholder="多人使用逗号分隔" /></div>
                  <div class="field"><label><span class="label-main">研究团队或机构</span></label><input v-model="doc.institutions" class="input" placeholder="请输入研究团队或机构" /></div>
                  <div class="field"><label><span class="label-main">发表时间</span></label><input v-model="doc.publication_date" class="input" type="date" :max="todayDateStr" /></div>
                  <div class="field"><label><span class="label-main">文献来源</span></label><input v-model="doc.source" class="input" placeholder="期刊、会议、报告或知识库" /></div>
                  <div class="field full"><label><span class="label-main">文献关键词</span><small>多个关键词可使用逗号、顿号或分号分隔</small></label><input v-model="doc.keywords" class="input" placeholder="多个关键词使用逗号、顿号或分号分隔" /></div>
                </div>
                <div class="field review-fulltext-v634"><label><span class="label-main"><span class="required-mark">*</span> 文本</span><small>支持各类科技文本，最多 8000 字</small></label><textarea v-model="doc.text" class="textarea compact" maxlength="8000" placeholder="请输入文本内容"></textarea></div>
              </div>
              <button v-if="docs.length" class="outline-btn deep-cluster-add-doc-btn" type="button" @click="addDoc">＋ 添加文献</button>
            </div>
          </template>

          <template v-else-if="toolId.startsWith('citation-') && mode === 'text'">
            <div class="citation-structured-input">
              <div class="field document-title-field"><label><span class="label-main"><span class="required-mark">*</span> 题目</span><small>必填；用于标识响应结果及可视化弹窗中的当前文献</small></label><input v-model="form.documentTitle" class="input" maxlength="300" placeholder="请输入题目" /></div>
              <div v-if="toolId === 'citation-sentiment' || toolId === 'citation-intent'" class="field"><label><span class="label-main"><span class="required-mark">*</span> 文献文本</span><small>最多 8000 字</small></label><textarea v-model="citationSingle.documentText" class="textarea main-textarea" maxlength="8000" placeholder="请输入文献文本"></textarea></div>
              <div class="field"><label><span class="label-main"><span class="required-mark">*</span> 引用句解析</span><button type="button" class="citation-extract-btn" @click="forceAutoExtractCitation"><i>✦</i>从文献文本自动提取</button></label><small v-if="citationExtractedCount" class="range-hint">已从文献文本解析出 {{ citationCards.length }} 条引用句（含上下文），提交时全部识别；卡片可编辑与删除。</small></div>
              <div v-for="(card, index) in citationCards" :key="card.id" class="document-card citation-card">
                <div class="document-card-head"><b>引用句 {{ index + 1 }}<span v-if="card.marker" class="citation-marker-bind"> · 文献 {{ card.marker }}</span></b><button class="ghost-btn danger" type="button" @click="removeCitationCard(card.id)">删除</button></div>
                <div class="field"><label><span class="label-main"><span class="required-mark">*</span> 引用句文本</span><small>保留完整原句供上下文核对；句内多文献引用已按编号拆分为多张卡片</small></label><textarea v-model="card.sentence" class="textarea compact" placeholder="包含引文标记的引用句" @input="markCitationCardsEdited"></textarea></div>
                <div class="field"><label><span class="label-main">局部子片段</span><small>该文献编号对应的局部语义片段；意图/情感识别以此为准，留空则用整句判定</small></label><textarea v-model="card.subSpan" class="textarea compact" placeholder="本条引用对应的局部子片段，可编辑" @input="markCitationCardsEdited"></textarea></div>
                <div class="two-column"><div class="field"><label><span class="label-main"><span class="required-mark">*</span> 引用句上文</span></label><textarea v-model="card.previousContext" class="textarea compact citation-context-area" placeholder="引用句前文" @input="markCitationCardsEdited"></textarea></div><div class="field"><label><span class="label-main"><span class="required-mark">*</span> 引用句下文</span></label><textarea v-model="card.nextContext" class="textarea compact citation-context-area" placeholder="引用句后文" @input="markCitationCardsEdited"></textarea></div></div>
              </div>
            </div>
          </template>
          <template v-else-if="toolId.startsWith('citation-') && mode === 'batch-text'">
            <div class="special-panel batch-text-panel citation-batch-panel">
              <div class="special-panel-head"><div><strong>批量引用数据</strong><span>已添加 {{ citationBatchItems.length }} 条，每条作为一个独立任务</span></div><button class="outline-btn" type="button" @click="addCitationBatchItem">＋ 添加引用数据</button></div>
              <div v-for="(item,index) in citationBatchItems" :key="item.id" class="document-card batch-text-item-card citation-batch-item-card">
                <div class="document-card-head"><b>引用数据 {{ index + 1 }}<span v-if="item.citationMarker" class="citation-marker-bind"> · 文献 {{ item.citationMarker }}</span></b><button class="ghost-btn danger" type="button" :disabled="citationBatchItems.length <= 1" @click="removeCitationBatchItem(item.id)">删除</button></div>
                <div class="field"><label><span class="label-main"><span class="required-mark">*</span> 题目</span><small>必填；用于标识本条响应结果及可视化弹窗中的文献</small></label><input v-model="item.title" class="input" maxlength="300" placeholder="请输入本条文献题目" /></div>
                <div v-if="toolId === 'citation-sentiment' || toolId === 'citation-intent'" class="field"><label><span class="label-main"><span class="required-mark">*</span> 文献文本</span><small>最多 8000 字</small></label><textarea v-model="item.documentText" class="textarea compact" maxlength="8000" placeholder="请输入本条引用所属的文献文本"></textarea></div>
                <div class="field"><label><span class="label-main"><span class="required-mark">*</span> 引用句文本</span><button v-if="toolId === 'citation-sentiment' || toolId === 'citation-intent'" type="button" class="citation-extract-btn" @click="autoExtractBatchCitation(item)"><i>✦</i>从文献文本自动提取</button></label><textarea v-model="item.citationSentence" class="textarea compact citation-sentence-area" placeholder="可点击右上按钮从本条文献文本自动提取，也可手动填写"></textarea></div>
                <div class="field"><label><span class="label-main">局部子片段</span><small>该文献编号对应的局部语义片段；意图/情感识别以此为准，留空则用整句判定</small></label><textarea v-model="item.subSpan" class="textarea compact" placeholder="本条引用对应的局部子片段，可编辑"></textarea></div>
                <div class="two-column"><div class="field"><label><span class="label-main"><span class="required-mark">*</span> 引用句上文</span></label><textarea v-model="item.previousContext" class="textarea compact citation-context-area" placeholder="请输入引用句前文"></textarea></div><div class="field"><label><span class="label-main"><span class="required-mark">*</span> 引用句下文</span></label><textarea v-model="item.nextContext" class="textarea compact citation-context-area" placeholder="请输入引用句后文"></textarea></div></div>
                <div class="citation-card-metadata">
                  <div class="citation-metadata-section-head"><b><span class="required-mark">*</span> 被引文献元数据</b><span>粘贴本条引用的参考文献条目，支持多条</span></div>
                  <textarea v-model="item.refsText" class="textarea compact citation-refs-area" placeholder="每行一条参考文献条目，例如：&#10;[3] Wang F, Li H. Neural Message Passing. ICML, 2020."></textarea>
                  <div class="citation-parser-action-row">
                    <span v-if="item.refsParsing" class="citation-parse-status">解析中…</span>
                    <span v-else-if="item.refsError" class="citation-parse-status warning">! {{ item.refsError }}</span>
                    <span v-else-if="item.metaList.length" class="citation-parse-status success">✓ 已解析 {{ item.metaList.length }} 条</span>
                    <span v-else class="citation-parse-status">粘贴条目后，点击开始解析</span>
                    <button class="outline-btn citation-parse-button" type="button" :disabled="item.refsParsing" @click="parseBatchCitationRefs(item)">{{ item.refsParsing ? '解析中…' : '开始解析' }}</button>
                  </div>
                  <div v-for="(entry, eIndex) in item.metaList" :key="eIndex" class="citation-metadata-entry">
                    <div class="citation-metadata-entry-head"><b>条目 {{ eIndex + 1 }}<span v-if="entry.reference_index"> [{{ entry.reference_index }}]</span></b><button class="ghost-btn danger" type="button" @click="removeBatchMetaEntry(item, eIndex)">删除</button></div>
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
            </div>
          </template>
          <template v-else-if="mode === 'text' && toolId !== 'relation-extract'">
            <div v-if="toolId === 'definition-detect'" class="settings-card definition-basic-options two-column"><div class="field"><label><span class="label-main">领域标签</span><small>注入领域语境辅助概念判定</small></label><select v-model="form.domain" class="select"><option value="自动识别">自动识别</option><option value="01">数学与计算科学</option><option value="02">力学与工程力学</option><option value="03">物理学与应用物理</option><option value="04">化学与化学科学</option><option value="05">天文学与空间科学</option><option value="06">地球科学与地质资源</option><option value="07">测绘遥感与地理信息</option><option value="08">气象海洋科学</option><option value="09">生物科学与生物技术</option><option value="10">医学与卫生健康</option><option value="11">药学与毒理学</option><option value="12">农业科学与农业工程</option><option value="13">林业畜牧兽医与水产</option><option value="14">材料科学与材料工程</option><option value="15">矿业与矿物加工</option><option value="16">石油与天然气工程</option><option value="17">冶金与金属加工</option><option value="18">机械工程与智能制造</option><option value="19">仪器仪表与计量检测</option><option value="20">能源与动力工程</option><option value="21">核科学与核工程</option><option value="22">电气工程与电力系统</option><option value="23">电子通信与半导体</option><option value="24">自动化与控制工程</option><option value="25">人工智能与计算机技术</option><option value="26">化学工程与过程工业</option><option value="27">轻工食品与纺织</option><option value="28">建筑与土木工程</option><option value="29">水利与水电工程</option><option value="30">交通运输工程</option><option value="31">航空航天工程</option><option value="32">环境与安全工程</option></select></div><div class="field"><label><span class="label-main">输出格式要求</span><small>附输出结构</small></label><select v-model="form.outputFormat" class="select"><option>JSON</option><option>CSV</option><option>数据库写入结构</option></select></div></div>
            <div v-if="toolId === 'fund-move'" class="field fund-project-name-field"><label><span class="label-main">项目名称</span><small>可选；用于标识本次基金项目语步识别结果</small></label><input v-model="form.projectName" class="input" maxlength="200" placeholder="请输入项目名称" /></div>
            <div v-if="needsDocumentTitle" class="field document-title-field"><label><span class="label-main"><span class="required-mark">*</span> 题目</span><small>必填；用于标识响应结果及可视化弹窗中的当前文献</small></label><input v-model="form.documentTitle" class="input" maxlength="300" placeholder="请输入题目" /></div>
            <div class="field primary-text-field"><label><span class="label-main"><span class="required-mark">*</span> {{ textInputLabel }}</span><small>最多 8000 字</small></label><textarea v-model="form.text" class="textarea main-textarea primary-textarea" maxlength="8000" :placeholder="`请输入${textInputLabel}`"></textarea></div>
          </template>
          <template v-else-if="mode === 'batch-text' && toolId !== 'relation-extract'">
            <div class="special-panel batch-text-panel">
              <div class="special-panel-head"><div><strong>{{ textInputLabel }}集合</strong><span>已添加 {{ batchTexts.length }} 条，每条独立提交和返回结果</span></div><button class="outline-btn" type="button" @click="addBatchText">＋ 添加文本</button></div>
              <div v-for="(item,index) in batchTexts" :key="item.id" class="document-card batch-text-item-card">
                <div class="document-card-head"><b><span class="required-mark">*</span> 文本 {{ index + 1 }}</b><button class="ghost-btn danger" type="button" :disabled="batchTexts.length <= 1" @click="removeBatchText(item.id)">删除</button></div>
                <div v-if="toolId === 'fund-move'" class="field fund-project-name-field"><label><span class="label-main">项目名称</span><small>可选；对应第 {{ index + 1 }} 条文本</small></label><input v-model="item.projectName" class="input" maxlength="200" :placeholder="`请输入第 ${index + 1} 个项目名称`" /></div>
                <div v-if="needsDocumentTitle" class="field document-title-field"><label><span class="label-main"><span class="required-mark">*</span> 题目</span><small>必填；对应第 {{ index + 1 }} 条文本</small></label><input v-model="item.title" class="input" maxlength="300" :placeholder="`请输入第 ${index + 1} 篇文献题目`" /></div>
                <div class="field batch-text-content-field"><div class="batch-text-limit">最多 8000 字</div><textarea v-model="item.text" class="textarea compact batch-textarea" maxlength="8000" :placeholder="`请输入第 ${index + 1} 条${textInputLabel}`"></textarea></div>
              </div>
            </div>
          </template>
          <template v-else-if="mode === 'file' && toolId !== 'relation-extract'">
            <div class="field single-file-field"><label><span class="label-main"><span class="required-mark">*</span> {{ textInputLabel }}文件</span><small>本次只处理一个文件</small></label><label class="upload-zone single-file-upload-zone"><input type="file" accept=".pdf,.docx,.txt" @change="handleFileSelection($event, false)" /><span class="upload-icon">⇧</span><b>选择一个文件或拖拽到此处</b><small>支持 PDF、DOCX、TXT，单文件最大 50 MB</small></label><div v-if="uploadedFiles.length" class="selected-file-list single-file-list"><article v-for="item in uploadedFiles.slice(0,1)" :key="item.id" class="selected-file-row"><span class="selected-file-type">{{ item.type }}</span><div><b>{{ item.name }}</b><small>{{ formatFileSize(item.size) }} · 等待提交</small></div><button class="ghost-btn danger" type="button" @click="removeUploadedFile(item.id)">移除</button></article></div></div>
          </template>
          <template v-else-if="mode === 'batch' && toolId !== 'relation-extract'">
            <div class="special-panel batch-file-panel">
              <div class="special-panel-head"><div><strong><span class="required-mark">*</span> {{ toolId === 'structured-review' ? '文献集文件' : '批量文件上传' }}</strong><span>必填；{{ textInputLabel }}<span class="nowrap-chunk"> · 已选择 {{ uploadedFiles.length }} 个文件</span></span></div><label class="outline-btn file-add-button"><input type="file" multiple accept=".pdf,.docx,.txt" @change="handleFileSelection($event, true)" />＋ 添加文件</label></div>
              <label class="upload-zone batch-file-upload-zone"><input type="file" multiple accept=".pdf,.docx,.txt" @change="handleFileSelection($event, true)" /><span class="upload-icon">⇧</span><b>一次选择或拖拽多个文件</b><small>支持 PDF、DOCX、TXT；单文件最大 {{ toolId === 'structured-review' ? '80' : '50' }} MB</small></label>
              <div class="batch-file-queue">
                <div class="batch-file-queue-head"><b>待处理文件队列</b><span>{{ uploadedFiles.length }} 个文件</span></div>
                <div v-if="!uploadedFiles.length" class="batch-file-empty">选择文件后，将在这里逐项显示文件名称、大小和处理状态。</div>
                <template v-if="toolId === 'deep-cluster'">
                  <article v-for="(item,index) in uploadedFiles" :key="item.id" class="document-card deep-cluster-file-card">
                    <div class="document-card-head"><b>文件 {{ index + 1 }} · {{ item.name }}</b><button class="ghost-btn danger" type="button" @click="removeUploadedFile(item.id)">移除</button></div>
                    <div class="selected-file-summary"><span class="selected-file-type">{{ item.type }}</span><span>{{ formatFileSize(item.size) }} · 等待提交</span></div>
                    <div class="settings-title deep-cluster-metadata-title"><b>文献元数据</b><span>由用户填写，与当前文件一一关联</span></div>
                    <div class="two-column deep-cluster-metadata-grid">
                      <div class="field"><label><span class="label-main"><span class="required-mark">*</span> 文献编号</span></label><input v-model="item.documentId" class="input" placeholder="例如：DOC001" /></div>
                      <div class="field"><label><span class="label-main"><span class="required-mark">*</span> 发表时间</span></label><input v-model="item.publicationDate" class="input" type="date" :max="todayDateStr" /></div>
                      <div class="field"><label><span class="label-main"><span class="required-mark">*</span> 题名</span></label><input v-model="item.title" class="input" placeholder="请输入题名" /></div>
                      <div class="field"><label><span class="label-main">作者</span><small>可选</small></label><input v-model="item.authors" class="input" placeholder="多人使用逗号分隔" /></div>
                      <div class="field"><label><span class="label-main">文献来源</span><small>可选</small></label><input v-model="item.source" class="input" placeholder="期刊、会议、报告或其他来源" /></div>
                      <div class="field"><label><span class="label-main">关键词</span><small>可选</small></label><input v-model="item.keywords" class="input" placeholder="多个关键词使用逗号分隔" /></div>
                    </div>
                  </article>
                </template>
                <template v-else>
                  <article v-for="(item,index) in uploadedFiles" :key="item.id" class="selected-file-row"><i>{{ index + 1 }}</i><span class="selected-file-type">{{ item.type }}</span><div><b>{{ item.name }}</b><small>{{ formatFileSize(item.size) }} · 等待提交</small></div><button class="ghost-btn danger" type="button" @click="removeUploadedFile(item.id)">移除</button></article>
                </template>
              </div>
              <div class="two-column deep-cluster-metadata-grid deep-cluster-anchor-grid">
                <div class="field"><label><span class="label-main">训练样本</span><small>可选</small></label>
                  <div class="requirement-resource-controls">
                    <select v-model="anchorTrainSource" class="select resource-source-select"><option value="database">从数据库选择当前资源</option><option value="upload">用户上传资源</option></select>
                    <select v-if="anchorTrainSource === 'database'" v-model="selectedAnchorTrain" class="select"><option value="">不使用</option><option v-for="item in anchorTrainOptions" :key="item.id" :value="item.id">{{ item.name }}</option></select>
                    <div v-else class="resource-upload-wrap"><label class="resource-upload-zone"><input type="file" accept=".json" @change="handleAnchorFileChange('training_samples', $event)" /><span>⇧</span><b>{{ anchorTrainFile?.name || '点击上传训练样本' }}</b><small>仅标准 JSON 数组生效</small></label><div class="anchor-upload-actions"><button type="button" class="primary-btn" :disabled="anchorUploadingKey === 'training_samples' || !anchorTrainFile" @click="submitAnchorResource('training_samples')">{{ anchorUploadingKey === 'training_samples' ? '提交中…' : '提交' }}</button><button v-if="anchorTrainFile" class="hover-copy-btn resource-cancel-btn" type="button" @click="clearAnchorFile('training_samples')">✕ 取消</button></div></div><p class="anchor-format-hint">仅支持 JSON 文件</p>
                  </div>
                </div>
                <div class="field"><label><span class="label-main">人工标注类目标签数据</span><small>可选</small></label>
                  <div class="requirement-resource-controls">
                    <select v-model="anchorGoldSource" class="select resource-source-select"><option value="database">从数据库选择当前资源</option><option value="upload">用户上传资源</option></select>
                    <select v-if="anchorGoldSource === 'database'" v-model="selectedAnchorGold" class="select"><option value="">不使用</option><option v-for="item in anchorGoldOptions" :key="item.id" :value="item.id">{{ item.name }}</option></select>
                    <div v-else class="resource-upload-wrap"><label class="resource-upload-zone"><input type="file" accept=".json" @change="handleAnchorFileChange('manually_labeled_category_data', $event)" /><span>⇧</span><b>{{ anchorGoldFile?.name || '点击上传人工标注类目标签数据' }}</b><small>仅标准 JSON 数组生效</small></label><div class="anchor-upload-actions"><button type="button" class="primary-btn" :disabled="anchorUploadingKey === 'manually_labeled_category_data' || !anchorGoldFile" @click="submitAnchorResource('manually_labeled_category_data')">{{ anchorUploadingKey === 'manually_labeled_category_data' ? '提交中…' : '提交' }}</button><button v-if="anchorGoldFile" class="hover-copy-btn resource-cancel-btn" type="button" @click="clearAnchorFile('manually_labeled_category_data')">✕ 取消</button></div></div><p class="anchor-format-hint">仅支持 JSON 文件</p>
                  </div>
                </div>
              </div>
            </div>
          </template>
          <template v-else-if="(mode === 'existing-result' || mode === 'collection') && toolId !== 'relation-extract'">
            <div class="settings-card database-collection-card">
              <div class="settings-title"><b>{{ mode === 'existing-result' ? '数据库历史聚类任务' : '指定文献集' }}</b><span>{{ mode === 'collection' ? '从科技文献检索结果集、科技情报平台、科研管理系统或知识库选择' : '从系统数据库读取已完成并持久化保存的聚类结果' }}</span></div>
              <div v-if="mode === 'collection'" class="database-selector-panel">
                <div class="database-selector-heading"><b><span class="required-mark">*</span> 选择已有文献集</b><span>必填</span></div>
                <select v-model="selectedCollectionId" class="select"><option v-if="!documentCollectionOptions.length" value="" disabled>暂无文献数据集</option><option v-for="collection in documentCollectionOptions" :key="collection.id" :value="collection.id">{{ collection.name }} · {{ collection.documentCount }} 篇<template v-if="collection.topicSimilarity != null"> · 相似度 {{ collection.topicSimilarity }}</template></option></select>
                <div v-if="!documentCollectionOptions.length" class="info-banner" style="margin-top:8px"><b>暂无数据</b><span>暂无满足数量要求的文献数据集（综述至少需要 3 篇文献，不足 3 篇的文献集已过滤）；请先在"聚类标签生成工具"中完成标签生成或更换包含 3 篇以上文献的文献集</span></div>
                <div v-if="selectedCollection" class="database-task-summary collection-summary"><span><small>数据来源</small><b>{{ selectedCollection.source }}</b></span><span><small>文献数量</small><b>{{ selectedCollection.documentCount }} 篇</b></span><span><small>时间范围</small><b>{{ selectedCollection.timeRange }}</b></span><span><small>更新时间</small><b>{{ formatDateTime(selectedCollection.updatedAt) }}</b></span></div>
                <div class="info-banner">系统根据文献集编号读取每篇文献的文本和对应元数据；用户不需要手工填写数据库编号或文本。</div>
              </div>
              <div v-else class="database-selector-panel">
                <div class="database-selector-heading"><b><span class="required-mark">*</span> 选择已完成的深度聚类任务</b><span>必填</span></div>
                <select v-model="selectedClusterTaskId" class="select"><option v-if="!clusterTaskOptions.length" value="" disabled>暂无已完成的深度聚类任务</option><option v-for="task in clusterTaskOptions" :key="task.id" :value="task.id">{{ task.name }} · {{ task.id }}</option></select>
                <div v-if="!clusterTaskOptions.length" class="info-banner" style="margin-top:8px"><b>暂无数据</b><span>请先在"深度聚类工具"中完成至少一次聚类,再回来选择任务</span></div>
                <div v-if="selectedClusterTask" class="database-task-summary"><span><small>聚类维度</small><b>{{ selectedClusterTask.dimension }}</b></span><span><small>文献数量</small><b>{{ selectedClusterTask.documentCount }} 篇</b></span><span><small>类簇数量</small><b>{{ selectedClusterTask.clusterCount }} 个</b></span><span><small>完成时间</small><b>{{ formatDateTime(selectedClusterTask.completedAt) }}</b></span></div>
                <div class="info-banner">系统使用任务编号读取关联类簇和短语集合，任务编号仅用于数据库关联。</div>
              </div>
            </div>
          </template>

          <RequirementSupplement v-if="toolId !== 'deep-cluster' && toolId !== 'structured-review'" :tool-id="toolId" :mode="mode" @update:payload="updateSupplementalPayload" />


          <div v-if="toolId === 'zh-keyword'" class="settings-card generic-settings">
            <div class="dictionary-card"><div class="field-heading"><b>可选领域术语词典</b><span>用户词典为可选输入</span></div><div class="field"><label><span class="label-main">词典使用方式</span><small>区分数据库资源与用户录入</small></label><select v-model="dictionaryMode" class="select"><option value="system">使用系统预置术语词典（默认）</option><option value="saved">从数据库选择已保存的用户词典</option><option value="custom">新建或上传用户自定义领域词典</option></select></div><div v-if="dictionaryMode === 'system'" class="info-banner dictionary-status">✓ 默认状态：使用系统预置术语词典，不提交用户词典参数。</div><div v-else-if="dictionaryMode === 'saved'" class="database-selector-panel"><div class="database-selector-heading"><b>选择已保存的用户领域词典</b></div><select v-model="selectedDictionaryId" class="select"><option v-for="item in savedDictionaryOptions" :key="item.id" :value="item.id">{{ item.name }} · {{ item.termCount }} 词</option></select><div v-if="selectedDictionary" class="database-record-summary"><span>术语数量：{{ selectedDictionary.termCount }}</span><span>更新时间：{{ formatDateTime(selectedDictionary.updatedAt) }}</span></div></div><div v-else class="two-column dictionary-custom"><div class="field"><label><span class="label-main">用户词典名称</span><small>用于识别和管理词典</small></label><input v-model="customDictionaryName" class="input" /></div><div class="field"><label><span class="label-main">命中权重增量</span></label><div class="numeric-stepper"><input v-model="weightBoost" class="input numeric-stepper-input" type="text" inputmode="none" readonly aria-label="命中权重增量" /><span class="numeric-stepper-controls"><button type="button" aria-label="增加命中权重增量" :disabled="Number(weightBoost) >= 0.5" @click="adjustWeightBoost(1)">▲</button><button type="button" aria-label="减小命中权重增量" :disabled="Number(weightBoost) <= 0" @click="adjustWeightBoost(-1)">▼</button></span></div></div><div class="field full"><label><span class="label-main">词典术语</span><small>每行一个术语</small></label><textarea v-model="customDictionaryTerms" class="textarea compact"></textarea></div><div class="field full dictionary-upload-field"><label class="resource-upload-zone"><input ref="dictionaryFileInput" type="file" accept=".json,.csv,.xlsx,.txt" @change="handleDictionaryFile" /><span>⇧</span><b>上传用户词典文件</b><small>{{ customDictionaryFile ? customDictionaryFile.name : '上传后保存到数据库并生成词典编号' }}</small></label><button v-if="customDictionaryFile" class="hover-copy-btn dictionary-cancel-btn" type="button" @click="clearDictionaryFile">✕ 取消</button></div><div class="field full dictionary-save-row"><button type="button" class="primary-btn" :disabled="savingDict" @click="saveCustomDictionary">{{ savingDict ? '保存中…' : '保存词典到数据库' }}</button></div></div></div>
          </div>

        </div>
      </div>

      <div class="test-card response-card">
        <div v-if="languageMismatch" class="info-banner warning" style="margin:0 0 10px"><b>语言不匹配提示</b><span>{{ languageMismatch }}</span></div>
        <div class="test-card-header"><div class="test-card-title">响应结果</div><div class="response-card-actions-v645"><button id="downloadResultBtnV732" class="ghost-btn" :disabled="!hasResult" @click="downloadResult">⇩ 下载结果</button><button v-if="canVisualize" id="viewVisualizationBtnV645" class="outline-btn visual-btn" :disabled="!hasResult" @click="emit('visualize', result)">▦ 查看可视化结果</button><button id="clearBtn" class="ghost-btn" @click="clearResult">⌫ 清除结果</button></div></div>
        <div class="response-result-body hover-copy-box"><pre v-if="hasResult" class="console">{{ pretty(result) }}</pre><div v-else-if="requestError" class="console placeholder request-error">{{ requestError }}</div><div v-else class="console placeholder">等待后端返回真实测试结果…</div><button id="copyResultBtnV732" class="hover-copy-btn result-copy" :disabled="!hasResult" @click="copyResult">{{ resultCopied ? '✔' : '⧉ 复制' }}</button></div>
      </div>
    </div>
    <RequirementSupplement v-if="toolId === 'deep-cluster'" :tool-id="toolId" :mode="mode" />
  </section>
</template>
