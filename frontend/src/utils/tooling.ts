import type { CallType, InputMode, ToolDefinition } from '../types'
import { requirementContracts } from '../data/requirement-contracts.ts'
import { demoResponseForMode } from '../data/tool-overrides.ts'
import vizWhitelist from '../data/viz-field-whitelist.json' with { type: 'json' }
import { clusterTaskOptions, databaseResourceCatalog, documentCollectionOptions } from '../data/database-preview.ts'

export const modeLabels: Record<InputMode, string> = {
  text: '单文本', 'batch-text': '批量文本', file: '单文件', batch: '批量文件',
  'existing-result': '历史聚类任务', collection: '已有文献集合'
}

// 中英文摘要语步识别已补充可视化弹窗（renderAbstractMove），不再排除。
export const noVisualizationToolIds = new Set<string>()
export const supportsVisualization = (toolId: string) => !noVisualizationToolIds.has(toolId)

export function modesFor(tool: ToolDefinition): InputMode[] {
  if (tool.inputModes?.length) return tool.inputModes
  if (tool.supportsFileUpload) return ['text', 'batch-text', 'file', 'batch']
  return ['text']
}

export function labelFor(tool: ToolDefinition, mode: InputMode) {
  return tool.modeLabels?.[mode] || modeLabels[mode]
}

export function endpointFor(tool: ToolDefinition, mode: InputMode) {
  const keys: Record<InputMode, string> = {
    text: 'textEndpoint', 'batch-text': 'batchTextEndpoint', file: 'fileEndpoint', batch: 'batchFileEndpoint',
    'existing-result': 'historyTaskEndpoint', collection: 'collectionEndpoint'
  }
  return String(tool[keys[mode]] || tool.endpoint || '/api/v1/semantic-toolkit/run')
}

function requirementExampleValue(name: string, type: string, mode: InputMode, tool: ToolDefinition, primary: boolean) {
  if (primary && mode === 'file') return '@paper.pdf'
  if (primary && mode === 'batch') {
    const batchCount = Math.max(3, Array.isArray((tool as any).demoBatchTexts) ? (tool as any).demoBatchTexts.length : 0)
    return Array.from({ length: batchCount }, (_, index) => `@paper_${String(index + 1).padStart(2, '0')}.${index % 2 ? 'docx' : 'pdf'}`)
  }
  if (name === 'citation_sentence_and_context') {
    const single = {
      citation_sentence: String(tool.payload?.citation_sentence || '本文采用已有研究提出的方法[12]。'),
      previous_context: String(tool.payload?.previous_context || '本研究需要增强结构表示能力。'),
      next_context: String(tool.payload?.next_context || '实验结果验证了该方法的有效性。'),
    }
    if (mode !== 'batch-text') return [single]
    return [
      single,
      {
        citation_sentence: 'Recent findings [20, 29, 30, 38, 48] indicate minimal variation in adjacent-timestep features.',
        previous_context: 'Diffusion models repeatedly execute denoising blocks and incur high inference costs.',
        next_context: 'This observation motivates feature reuse and timestep-specific computation.',
      },
      {
        citation_sentence: 'Frame-level methods have evolved from uniform sampling to adaptive methods that identify and discard irrelevant frames [8].',
        previous_context: 'Video reasoning suffers from temporal and spatial redundancy.',
        next_context: 'The method further unifies frame selection and token allocation as hierarchical visual budgeting.',
      },
    ]
  }
  if (name === 'citation_metadata') return Array.isArray(tool.payload?.citation_metadata) && tool.payload.citation_metadata.length
    ? (mode === 'batch-text' || mode === 'batch'
        ? Array.from({ length: 3 }, (_, index) => ({
            ...tool.payload.citation_metadata[index % tool.payload.citation_metadata.length],
            reference_id: `REF-${index + 1}`,
          }))
        : tool.payload.citation_metadata)
    : [{
        raw_reference: '[12] 作者甲. 被引文献题名[J]. 情报学报, 2024, 43(2): 120-130.',
        citation_marker: '[12]',
        publication_year: '2024',
        authors: ['作者甲'],
        work_name: '被引文献题名',
        venue: '情报学报',
        doi: '10.1234/example.2024.001',
      }]
  if (name === 'upstream_ner_record_id') return String(tool.payload?.upstream_ner_record_id || 'NER-20260816-001')
  if (name === 'identified_entities') return [{ text: '阿司匹林', type: 'DRUG' }, { text: '血小板聚集', type: 'BIOLOGICAL_PROCESS' }]
  if (name === 'dependency_parse_result') return { tokens: [], dependencies: [] }
  if (name === 'cluster_phrase_sets') return Array.isArray(tool.payload?.cluster_phrase_sets) && tool.payload.cluster_phrase_sets.length
    ? (clusterTaskOptions[0]?.phraseSets || tool.payload.cluster_phrase_sets).map((item: any) => ({
        cluster_id: item.cluster_id || item.clusterId,
        phrases: item.phrases || [],
      }))
    : [
        { cluster_id: 'CLUSTER_001', phrases: ['多尺度特征融合', '工业表面缺陷检测', '注意力增强'] },
        { cluster_id: 'CLUSTER_002', phrases: ['联邦学习', '隐私保护', '跨机构协同训练'] },
      ]
  if (name === 'label_length_limit') return 12
  if (name === 'language_type') return 'auto'
  if (name === 'distinctiveness_threshold') return 0.75
  if (name === 'project_name') return String(tool.payload?.project_name || 'TiAl合金中氢原子团簇的第一性原理计算及实验研究')
  if (name === 'document_title') {
    const title = String(tool.payload?.document_title || '科技文献题目')
    if (mode === 'batch-text') {
      const batch = Array.isArray((tool as any).demoBatchTexts) ? (tool as any).demoBatchTexts : []
      return batch.length
        ? batch.map((item: any, index: number) => item?.title || `文本 ${index + 1}`)
        : [title, '第二篇科技文献题目']
    }
    return title
  }
  if (name === 'professional_domain') return String(tool.payload?.professional_domain || '生物医学信息学')
  if (name === 'text_format_requirement') return '章节结构文本'
  if (name === 'domain_terminology_dictionary') return {
    use_mode: 'custom',
    source: 'user_input',
    resource_id: null,
    dictionary_name: '智能制造领域术语词典',
    weight_boost: 0.08,
    terms: ['工业表面缺陷', '多尺度特征融合', '在线质量检测'],
    file: null,
  }
  if (primary && mode === 'text') return String((tool as any).demoText || '待处理科技文本……')
  if (primary && mode === 'batch-text') {
    const batch = Array.isArray((tool as any).demoBatchTexts) ? (tool as any).demoBatchTexts : []
    if (batch.length) return batch.map((item: any, index: number) => ({
      id: item?.id || `TEXT${String(index + 1).padStart(3, '0')}`,
      ...(item?.project_name ? { project_name: item.project_name } : {}),
      ...(item?.title ? { title: item.title } : {}),
      text: typeof item === 'string' ? item : String(item?.text || ''),
    }))
    return [
      { id: 'TEXT001', text: String((tool as any).demoText || '待处理科技文本一……') },
      { id: 'TEXT002', text: '待处理科技文本二……' },
    ]
  }
  if (name.includes('format')) return 'JSON'
  if (name.includes('full_text') || name.includes('fragment') || name.includes('abstract') || name.includes('document_text')) {
    if (mode === 'batch-text') return [{ id: 'TEXT001', text: String((tool as any).demoText || '待处理科技文本……') }]
    return String((tool as any).demoText || '待处理科技文本……')
  }
  if (type.includes('resource')) {
    const resource = (databaseResourceCatalog[name] || []).find(item => (item.status || 'current') === 'current')
    return { source: 'database', resource_id: resource?.id || `SELECTED_${name.toUpperCase()}`, file: null }
  }
  if (type.includes('object[]')) return []
  if (type.includes('object')) return {}
  if (type.includes('integer')) return 1
  if (type.includes('number')) return 0.75
  return ''
}

function strictRequirementPayload(tool: ToolDefinition, mode: InputMode) {
  const contract = tool.requirementKey ? requirementContracts[tool.requirementKey] : undefined
  if (!contract) return null
  // citation-* 文件/批量文件模式：上传原始 PDF，引用句结构化数据由后端解析组装。
  // 主字段 citation_sentence_and_context 是 object[]，不能承载文件，模板改用通用
  // 上传字段 file/files（后端 /file 端点按 fallback 字段名接收并内置解析链路）。
  if (String(tool.documentType || '').startsWith('citation-') && (mode === 'file' || mode === 'batch')) {
    const structuredFields = new Set(['document_title', 'scientific_document_full_text', 'reference_entries', 'citation_sentence_and_context', 'citation_metadata'])
    const configOnly = Object.fromEntries(contract.inputs
      .filter(row => !structuredFields.has(row[0]))
      .map(row => [row[0], requirementExampleValue(row[0], row[1], mode, tool, false)]))
    return mode === 'file'
      ? { ...configOnly, file: '@paper.pdf' }
      : { ...configOnly, files: ['@paper_01.pdf', '@paper_02.pdf'] }
  }
  const inputs = contract.inputs.filter(row => row[0] !== 'document_title' || mode === 'text' || mode === 'batch-text')
  return Object.fromEntries(inputs.map((row, index) => [row[0], requirementExampleValue(row[0], row[1], mode, tool, index === 0)]))
}

/**
 * 自构造的简短 batch 输入（<8000 字符），用于 payloadFor 默认结构跑不通的工具：
 * ① citation 的 batch 后端要求 citation_sentence_and_context + citation_metadata，
 *    默认 payloadFor 只传 citations/全文，会缺字段或超 8000 字符；
 * ② domain-classify 的 batch 需要 domain_scientific_literature_data 批量结构。
 * 这些输入与采集脚本（collect-real-responses.mjs）共用，保证调用示例输入 ↔
 * 响应示例输出自洽，甲方可复现。
 */
export const CUSTOM_BATCH_PAYLOADS: Record<string, Record<string, unknown>> = {
  '/api/v1/citation-sentiment/text': {
    input_type: 'texts',
    document_title: ['文献A', '文献B'],
    citation_sentence_and_context: [
      { id: 'CIT001', citation_sentence: '已有研究表明该方法在小样本场景下泛化能力不足[1]。', previous_context: '针对图像分类任务，', next_context: '因此本文提出新的数据增强策略。', citation_marker: '[1]' },
      { id: 'CIT002', citation_sentence: 'Smith等人[2]的工作证实了注意力机制能提升检测精度。', previous_context: '在目标检测领域，', next_context: '受此启发，我们设计了多尺度注意力模块。', citation_marker: '[2]' },
    ],
    citation_metadata: [
      { citation_marker: '[1]', authors: '张三', work_name: '图像分类方法研究', publication_year: '2024' },
      { citation_marker: '[2]', authors: 'Smith J', work_name: 'Attention for detection', publication_year: '2023' },
    ],
  },
  '/api/v1/citation-intent/text': {
    input_type: 'texts',
    document_title: ['文献A', '文献B'],
    citation_sentence_and_context: [
      { id: 'CIT001', citation_sentence: '已有研究表明该方法在小样本场景下泛化能力不足[1]。', previous_context: '针对图像分类任务，', next_context: '因此本文提出新的数据增强策略。', citation_marker: '[1]' },
      { id: 'CIT002', citation_sentence: 'Smith等人[2]的工作证实了注意力机制能提升检测精度。', previous_context: '在目标检测领域，', next_context: '受此启发，我们设计了多尺度注意力模块。', citation_marker: '[2]' },
    ],
    citation_metadata: [
      { citation_marker: '[1]', authors: '张三', work_name: '图像分类方法研究', publication_year: '2024' },
      { citation_marker: '[2]', authors: 'Smith J', work_name: 'Attention for detection', publication_year: '2023' },
    ],
    preprocessed_training_set: { source: 'database', resource_id: 'RES-BUNDLED-CITATION-INTENT' },
  },
  '/api/v1/classify/domain/text': {
    input_type: 'texts',
    document_title: ['糖尿病肾病基因研究', '工业表面缺陷检测'],
    domain_scientific_literature_data: [
      { id: 'DOC1', text: '研究从GEO数据库获取糖尿病肾病转录组数据，利用WGCNA构建共表达网络，整合113种机器学习算法筛选特征基因，鉴定出VWF等关键基因。' },
      { id: 'DOC2', text: '提出融合轻量级卷积网络和动态注意力机制的缺陷检测模型，通过多尺度特征聚合增强缺陷表征，在工业缺陷数据集上提高检测精度。' },
    ],
    professional_domain: 'biomedical_informatics',
    domain_classification_rules: { source: 'database', resource_id: 'RES-BUNDLED-DOMAIN-RULE' },
    manually_labeled_training_data: { source: 'database', resource_id: 'RES-BUNDLED-DOMAIN-GOLD' },
  },
}

export function payloadFor(tool: ToolDefinition, mode: InputMode): Record<string, unknown> {
  const base = typeof tool.payload === 'object' && tool.payload ? { ...tool.payload } : {}
  const configuration = Object.fromEntries(Object.entries(base).filter(([key]) => !['input_type', 'text', 'texts', 'title', 'abstract', 'keywords', 'documents', 'file', 'files', 'collection_id', 'cluster_task_id', 'citation_sentence', 'previous_context', 'next_context', 'citations'].includes(key)))
  if (tool.documentType === 'structured-review') {
    const common = {
      topic_or_keywords: base.topic_or_keywords || '',
      document_metadata: base.document_metadata || [],
    }
    if (mode === 'batch-text') return { document_set: base.document_set || [], ...common }
    if (mode === 'batch') return { document_set: ['@paper_01.pdf', '@paper_02.docx'], ...common }
    return {
      document_set: { source: 'database', collection_id: documentCollectionOptions[0]?.id || 'COLL-202608-VLM-01' },
      topic_or_keywords: common.topic_or_keywords,
      document_metadata: { source: 'collection', collection_id: documentCollectionOptions[0]?.id || 'COLL-202608-VLM-01' },
    }
  }
  if (tool.documentType === 'cluster-label') return {
    cluster_task_id: base.cluster_task_id || null,
    cluster_phrase_sets: base.cluster_phrase_sets || [],
    label_length_limit: base.label_length_limit ?? 12,
    language_type: base.language_type || 'auto',
    distinctiveness_threshold: base.distinctiveness_threshold ?? 0.75,
  }
  if (tool.documentType === 'deep-cluster') {
    if (mode === 'batch') return {
      scientific_document_texts: ['@paper_01.pdf', '@paper_02.docx'],
      document_metadata: base.document_metadata || [
        { document_id: 'DOC001', publication_date: '2025-03-18', title: '工业表面缺陷检测研究' },
        { document_id: 'DOC002', publication_date: '2025-06-09', title: '复杂场景视觉识别方法' },
      ],
      cluster_dimension: base.cluster_dimension || 'technology',
      clustering_algorithm_type: base.clustering_algorithm_type || base.algorithm || 'auto',
      cluster_count: base.cluster_count ?? null,
      output_format: base.output_format || 'JSON',
      // 锚点资源可选字段必须在模板中声明：requestPayloadFor 按模板白名单过滤，
      // 漏声明会导致 OnlineTester 设置的资源选择被静默丢弃（用户类目不生效的根因）
      training_samples: base.training_samples ?? { source: 'database', resource_id: null },
      manually_labeled_category_data: base.manually_labeled_category_data ?? { source: 'database', resource_id: null },
    }
    const rawDocuments = (base.scientific_document_texts || base.documents || []) as Array<Record<string, unknown>>
    const documents = rawDocuments.map((item, index) => ({
      document_id: item.document_id || item.id || `DOC${String(index + 1).padStart(3, '0')}`,
      text: item.text || '',
    }))
    const documentMetadata = base.document_metadata || rawDocuments.map((item, index) => ({
      document_id: item.document_id || item.id || `DOC${String(index + 1).padStart(3, '0')}`,
      publication_date: item.publication_date || '',
      title: item.title || '',
      authors: item.authors || [],
      source: item.source || '',
      keywords: item.keywords || [],
    }))
    return {
      scientific_document_texts: documents,
      document_metadata: documentMetadata,
      cluster_dimension: base.cluster_dimension || 'technology',
      clustering_algorithm_type: base.clustering_algorithm_type || base.algorithm || 'auto',
      cluster_count: base.cluster_count ?? null,
      output_format: base.output_format || 'JSON',
      // 同上：锚点资源可选字段必须进入模板白名单，否则被 requestPayloadFor 过滤
      training_samples: base.training_samples ?? { source: 'database', resource_id: null },
      manually_labeled_category_data: base.manually_labeled_category_data ?? { source: 'database', resource_id: null },
    }
  }
  if (tool.documentType === 'fund') {
    const demoProjectName = String(tool.payload?.project_name || 'TiAl合金中氢原子团簇的第一性原理计算及实验研究')
    if (mode === 'text') return {
      project_name: demoProjectName,
      project_document_text: String((tool as any).demoText || '请输入中文基金项目文本'),
    }
    if (mode === 'batch-text') return {
      project_document_text: ((tool as any).demoBatchTexts || []).map((item: any, index: number) => ({
        project_name: item.project_name || `基金项目 ${index + 1}`,
        text: item.text || '',
      })),
    }
    if (mode === 'file') return { project_document_text: '@fund_project.pdf' }
    if (mode === 'batch') return { project_document_text: ['@fund_project_01.pdf', '@fund_project_02.docx'] }
  }
  // 自构造的简短 batch 输入优先（与响应示例采集同源，保证可复现）；
  // 必须在 strictRequirementPayload 之前，否则会被其提前返回的占位结构覆盖。
  if (mode === 'batch-text') {
    const customBatch = CUSTOM_BATCH_PAYLOADS[String(tool.textEndpoint || '')]
    if (customBatch) return { ...customBatch }
  }
  const strictPayload = strictRequirementPayload(tool, mode)
  if (strictPayload) return strictPayload
  if (mode === 'text') {
    if (String(tool.documentType || '').startsWith('citation-')) return {
      ...configuration,
      input_type: 'text',
      citation_sentence: base.citation_sentence || '请输入包含引文标记的引用句',
      previous_context: base.previous_context || '',
      next_context: base.next_context || '',
    }
    if ('text' in base || 'abstract' in base || 'title' in base) return { ...base, input_type: 'text' }
    return { ...configuration, input_type: 'text', text: String((tool as any).demoText || '请输入需要分析的科技文本') }
  }
  if (mode === 'batch-text') {
    if (String(tool.documentType || '').startsWith('citation-')) return {
      ...configuration,
      input_type: 'texts',
      citations: Array.isArray(base.citations) ? base.citations : [{
        id: 'CIT001',
        citation_sentence: base.citation_sentence || '引用句……[1]。',
        previous_context: base.previous_context || '',
        next_context: base.next_context || '',
      }],
    }
    return { ...configuration, input_type: 'texts', texts: (tool as any).demoBatchTexts || [{ id: 'text1', text: '科技文本一……' }, { id: 'text2', text: '科技文本二……' }] }
  }
  if (mode === 'file') return { ...configuration, input_type: 'file', file: '@paper.pdf' }
  if (mode === 'batch') return { ...configuration, input_type: 'files', files: ['@paper_01.pdf', '@paper_02.docx'] }
  if (mode === 'existing-result') return { ...configuration, input_type: 'existing_result', cluster_task_id: clusterTaskOptions[0]?.id || 'DCL-20260815-001', label_length_limit: 12, language_type: 'auto', distinctiveness_threshold: 0.75 }
  return { ...configuration, input_type: 'collection', collection_id: documentCollectionOptions[0]?.id || 'COLL-202608-VLM-01' }
}

/**
 * 在线测试、API 与 SDK 共用的请求构造入口。
 * `payloadFor` 负责给出当前功能/输入方式允许提交的字段集合；在线测试
 * 只能替换这些字段的值，不能临时增加接口未声明的参数。
 */
export function requestPayloadFor(
  tool: ToolDefinition,
  mode: InputMode,
  values: Record<string, unknown> = {},
) {
  const template = payloadFor(tool, mode)
  // ``payloadFor`` contains documentation examples. Online execution must
  // never silently submit those examples when the user left a field empty.
  return Object.fromEntries(Object.keys(template).flatMap(key =>
    Object.prototype.hasOwnProperty.call(values, key) ? [[key, values[key]]] : [],
  ))
}

const nestedParameterDescriptions: Record<string, string> = {
  id: '批量文本条目编号',
  text: '用户输入的文本内容',
  document_id: '文献编号，用于关联文本与元数据',
  project_name: '基金项目名称',
  document_title: '文献题目',
  citation_sentence: '引用句文本',
  previous_context: '引用句上文',
  next_context: '引用句下文',
  citation_sub_span: '句内多引用拆分后该条引用对应的局部子片段',
  raw_reference: '用户粘贴或上传的参考文献原始条目',
  citation_marker: '引文标记',
  publication_year: '被引文献发表年份',
  authors: '作者列表',
  work_name: '被引文献题名',
  venue: '期刊或会议名称',
  doi: '被引文献 DOI',
  source: '资源来源或文献来源',
  resource_id: '数据库资源编号',
  use_mode: '词典使用方式',
  dictionary_name: '用户词典名称',
  weight_boost: '词典命中权重增量',
  terms: '用户输入的词典术语',
  title: '文献题名',
  institutions: '研究团队或机构',
  publication_date: '发表时间',
  keywords: '文献关键词',
  collection_id: '数据库中的指定文献集编号',
  file: '用户选择上传资源时提交的文件',
}

const nestedParameterTypes: Record<string, string> = {
  id: 'string',
  text: 'string',
  document_id: 'string',
  project_name: 'string',
  document_title: 'string',
  citation_sentence: 'string',
  previous_context: 'string',
  next_context: 'string',
  citation_sub_span: 'string',
  raw_reference: 'string',
  citation_marker: 'string',
  publication_year: 'string',
  authors: 'string[]',
  work_name: 'string',
  venue: 'string',
  doi: 'string',
  source: 'string',
  resource_id: 'string',
  use_mode: 'string',
  dictionary_name: 'string',
  weight_boost: 'number',
  terms: 'string[]',
  title: 'string',
  institutions: 'string[]',
  publication_date: 'string',
  keywords: 'string[]',
  collection_id: 'string',
  file: 'file',
}

function parameterValueType(value: unknown) {
  if (Array.isArray(value)) {
    if (!value.length) return 'string[]'
    if (typeof value[0] === 'object') return 'object[]'
    if (typeof value[0] === 'string') return 'string[]'
    return 'array'
  }
  if (value === null) return 'null'
  if (typeof value === 'number') return Number.isInteger(value) ? 'integer' : 'number'
  if (typeof value === 'object') {
    // 文件上传占位(File 对象或 @文件名 字符串标记)
    const v = value as Record<string, unknown>
    if (v instanceof File || (v.file instanceof File) || (typeof v.file === 'string' && v.file.startsWith('@'))) return 'file'
    return 'object'
  }
  if (typeof value === 'string' && value.startsWith('@')) return 'file'
  return typeof value
}

function nestedParameterRows(
  value: unknown,
  path: string,
  status: string,
  toolId: string,
): Array<[string, string, string, string]> {
  const sample = Array.isArray(value) ? value.find(item => item && typeof item === 'object') : value
  if (!sample || typeof sample !== 'object' || Array.isArray(sample)) return []
  const prefix = Array.isArray(value) ? `${path}[]` : path
  return Object.entries(sample as Record<string, unknown>).flatMap(([key, child]) => {
    const childPath = `${prefix}.${key}`
    let childStatus = status
    if (['resource_id', 'file', 'dictionary_name', 'weight_boost', 'terms', 'raw_reference', 'project_name', 'document_title'].includes(key)) childStatus = 'conditional'
    if (['doi', 'title', 'authors', 'institutions', 'venue', 'work_name', 'publication_year', 'keywords'].includes(key)) childStatus = 'optional'
    if (key === 'title' && ['deep-cluster', 'structured-review'].includes(toolId)) childStatus = 'required' // 题名在这两个工具为必填
    if (key === 'source' && path.includes('document_metadata')) childStatus = 'optional'
    if (key === 'publication_date') childStatus = toolId === 'deep-cluster' ? 'required' : 'optional'
    if (key === 'id') childStatus = ['deep-cluster', 'structured-review'].includes(toolId) ? 'required' : 'optional'
    if (key === 'document_id' || key === 'text' || key === 'citation_sentence' || key === 'previous_context' || key === 'next_context' || key === 'citation_marker') childStatus = 'required'
    const row: [string, string, string, string] = [
      childPath,
      nestedParameterTypes[key] || parameterValueType(child),
      childStatus,
      nestedParameterDescriptions[key] || `${key} 子字段`,
    ]
    return [row, ...nestedParameterRows(child, childPath, childStatus, toolId)]
  })
}

/** 当前输入方式下，API 示例与在线测试共同使用的完整参数清单。 */
export function requestParameterRowsFor(tool: ToolDefinition, mode: InputMode) {
  const payload = payloadFor(tool, mode)
  const declared = new Map((tool.params || []).map(row => [row[0], row]))
  return Object.entries(payload).flatMap(([key, value]) => {
    const declared_row = declared.get(key) || [key, parameterValueType(value), 'optional', key]
    // 联合类型按当前模式的实际载荷收窄:文本模式只显示 string,批量显示 string[],
    // 文件模式显示 file——各模式各写各的,不把其他模式的类型混进来
    const actualType = parameterValueType(value)
    let top = declared_row
    if (declared_row[1] && declared_row[1].includes('|') && actualType && !actualType.includes('|')) {
      top = [declared_row[0], actualType, declared_row[2], declared_row[3]]
    }
    return [top, ...nestedParameterRows(value, key, top[2], tool.requirementKey || '')]
  }) as Array<[string, string, string, string]>
}

export function responseFor(tool: ToolDefinition, mode: InputMode) {
  // 调用文档与在线测试/可视化弹窗必须使用同一份分输入方式响应。
  // 这里不再单独选择旧的 API fixture，避免文本位置、文件章节、
  // 批量条数和数据库记录与弹窗不一致。
  const demo = demoResponseForMode(tool.requirementKey || '', tool, mode)
  return filterDemoByWhitelist(tool.requirementKey || '', demo)
}

/** 响应示例按弹窗渲染器白名单过滤 data 顶层字段（与后端 public_viz_result 同源） */
function filterDemoByWhitelist(toolId: string, response: any): any {
  const allowed = (vizWhitelist as Record<string, string[]>)[toolId]
  if (!allowed || !response || typeof response !== 'object' || !response.data || typeof response.data !== 'object') {
    return response
  }
  const allowSet = new Set(allowed)
  return { ...response, data: Object.fromEntries(Object.entries(response.data).filter(([key]) => allowSet.has(key))) }
}

export function buildCallCode(tool: ToolDefinition, mode: InputMode, callType: CallType) {
  const endpoint = endpointFor(tool, mode)
  const payload = payloadFor(tool, mode)
  if (tool.documentType === 'structured-review' && callType === 'api' && mode === 'batch') {
    return `import json
import mimetypes
import os
import requests

url = "https://api.example.com${endpoint}"
headers = {"Authorization": "Bearer YOUR_API_KEY"}
file_paths = ["paper_01.pdf", "paper_02.docx"]
metadata = json.loads(r'''${JSON.stringify((payload as any).document_metadata, null, 2)}''')
streams = []
files = []
try:
    for path in file_paths:
        stream = open(path, "rb")
        streams.append(stream)
        mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
        files.append(("document_set", (os.path.basename(path), stream, mime)))
    data = {
        "topic_or_keywords": ${JSON.stringify((payload as any).topic_or_keywords)},
        "document_metadata": json.dumps(metadata, ensure_ascii=False)
    }
    response = requests.post(url, headers=headers, files=files, data=data, timeout=300)
    print(response.json())
finally:
    for stream in streams:
        stream.close()`
  }
  if (tool.documentType === 'deep-cluster' && callType === 'api') {
    if (mode === 'batch-text') return `import json
import requests

# 语言检测、章节定位、阈值、模型策略和返回控制由服务内部自适应完成
url = "https://api.example.com${endpoint}"
headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer YOUR_API_KEY"
}
payload = json.loads(r'''${JSON.stringify(payload, null, 2)}''')

response = requests.post(url, headers=headers, json=payload, timeout=180)
print(response.json())`
  }
  const fileEntry = Object.entries(payload).find(([, value]) => typeof value === 'string' && value.startsWith('@') || Array.isArray(value) && value.some(item => typeof item === 'string' && item.startsWith('@')))
  if (callType === 'sdk') {
    const method = mode === 'file' ? 'invoke_file' : mode === 'batch' ? 'invoke_files' : mode === 'batch-text' ? 'invoke_texts' : mode === 'existing-result' ? 'invoke_history' : mode === 'collection' ? 'invoke_collection' : 'invoke_text'
    const sdkPayload = fileEntry ? Object.fromEntries(Object.entries(payload).filter(([key]) => key !== fileEntry[0])) : payload
    const fileArgument = fileEntry
      ? `${mode === 'batch' ? 'file_paths' : 'file_path'}=${JSON.stringify(Array.isArray(fileEntry[1]) ? fileEntry[1].map(value => String(value).replace(/^@/, '')) : String(fileEntry[1]).replace(/^@/, ''))},\n    `
      : ''
    return `import json
from semantic_toolkit_sdk import SemanticToolkitClient

client = SemanticToolkitClient(
    base_url="https://api.example.com",
    api_key="YOUR_API_KEY"
)

# SDK 与 API 提交相同的业务字段，由 SDK 封装 HTTP 请求和文件上传。
payload = json.loads(r'''${JSON.stringify(sdkPayload, null, 2)}''')

result = client.${method}(
    endpoint="${endpoint}",
    ${fileArgument}payload=payload
)

print(result)`
  }
  if (fileEntry) {
    const field = fileEntry[0]
    const values = Array.isArray(fileEntry[1]) ? fileEntry[1] : [fileEntry[1]]
    const paths = JSON.stringify(values.map(value => String(value).replace(/^@/, '')))
    const formData = Object.fromEntries(Object.entries(payload).filter(([key]) => key !== field))
    return `import json\nimport mimetypes\nimport os\nimport requests\n\nurl = "https://api.example.com${endpoint}"\nheaders = {"Authorization": "Bearer YOUR_API_KEY"}\nfile_paths = ${paths}\nstreams = []\nfiles = []\ntry:\n    for path in file_paths:\n        stream = open(path, "rb")\n        streams.append(stream)\n        mime = mimetypes.guess_type(path)[0] or "application/octet-stream"\n        files.append(("${field}", (os.path.basename(path), stream, mime)))\n    form_values = json.loads(r'''${JSON.stringify(formData, null, 2)}''')\n    data = {\n        key: json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value\n        for key, value in form_values.items()\n    }\n    response = requests.post(url, headers=headers, files=files, data=data, timeout=300)\n    print(response.json())\nfinally:\n    for stream in streams:\n        stream.close()`
  }
  return `import json\nimport requests\n\nurl = "https://api.example.com${endpoint}"\nheaders = {\n    "Content-Type": "application/json",\n    "Authorization": "Bearer YOUR_API_KEY"\n}\npayload = json.loads(r'''${JSON.stringify(payload, null, 2)}''')\n\nresponse = requests.post(url, headers=headers, json=payload, timeout=300)\nprint(response.json())`
}

export const deepClusterEvaluationParameters: Array<[string, string, string, string]> = [
  ['training_samples', 'resource|file', 'required', '独立模型评测使用的训练样本资源'],
  ['manually_labeled_category_data', 'resource|file', 'required', '用于计算 ARI、NMI、纯度等指标的人工标注答案'],
]

export function buildDeepClusterEvaluationCallCode(callType: CallType) {
  const payload = {
    training_samples: { source: 'database', resource_id: 'TRAINING_SAMPLE_CURRENT', file: null },
    manually_labeled_category_data: { source: 'database', resource_id: 'CLUSTER_GOLD_CURRENT', file: null },
  }
  if (callType === 'sdk') return `from semantic_toolkit_sdk import SemanticToolkitClient

client = SemanticToolkitClient(
    base_url="https://api.example.com",
    api_key="YOUR_API_KEY"
)

result = client.evaluate_deep_cluster(
    payload=${JSON.stringify(payload, null, 4).replace(/\n/g, '\n    ')}
)

print(result)`
  return `import requests

url = "https://api.example.com/api/v1/cluster/deep/evaluate"
headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer YOUR_API_KEY"
}
payload = ${JSON.stringify(payload, null, 2)}

response = requests.post(url, headers=headers, json=payload, timeout=300)
print(response.json())`
}

export const pretty = (value: unknown) => JSON.stringify(value, null, 2)
