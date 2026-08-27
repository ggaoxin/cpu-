import type { InputMode, ToolDefinition } from '../types'
import { clusterLabelRuntimeResponses, deepClusterRuntime, requirements as generatedRequirements, structuredReviewRuntime, tools as generatedTools } from './prototype.generated.js'
import { requirementContracts } from './requirement-contracts.ts'
import { demoData } from './demo-data.generated.ts'
import { pureBatchTextByTool, pureSingleTextByTool } from './pure-text-demo.ts'
import {
  alignDemoSemanticResponseForMode,
  demoApiPayloadForTool,
  demoClusterLabelPayload,
  demoDeepClusterPayload,
  demoReviewPayload,
} from './demo-semantic-consistency.ts'

const fourModes: InputMode[] = ['text', 'batch-text', 'file', 'batch']
const deepCollectionResult = JSON.parse(JSON.stringify((deepClusterRuntime as ToolDefinition).response)) as Record<string, any>
deepCollectionResult.data.input_type = 'collection'
deepCollectionResult.data.input_summary.collection_id = 'COLLECTION_TECH_2026'
deepCollectionResult.data.input_summary.collection_name = '跨领域科技文献演示集合'

function cloneResult(value: unknown) {
  if (value === undefined || value === null) return {}
  return JSON.parse(JSON.stringify(value)) as Record<string, any>
}

const chapterPositionToolIds = new Set([
  'fund-move', 'zh-keyword', 'en-keyword', 'rq-detect', 'citation-sentiment',
  'citation-intent', 'definition-detect', 'general-ner', 'research-ner',
  'domain-ner', 'structured-review',
])

const previewChapterPaths = [
  ['（一）立项依据', '1．研究背景与动机'],
  ['（一）立项依据', '2．研究意义'],
  ['（一）立项依据', '3．国内外研究现状', '3.4 当前研究存在的不足'],
  ['（二）研究内容', '1．研究目标', '1.2 核心技术问题'],
  ['（三）研究方案', '2．技术路线', '2.3 模型设计与实验验证'],
]

type PositionPreviewMode = 'text' | 'file'

function enrichPositionPreview(value: unknown, mode: PositionPreviewMode) {
  const result = cloneResult(value)
  let cursor = 0
  const nextPath = () => [...previewChapterPaths[cursor++ % previewChapterPaths.length]]
  const nextCharacterPosition = () => {
    const current = cursor++
    const start = 72 + current * 47
    return { start, end: start + 26 + current % 4 * 7 }
  }
  const nextPosition = () => mode === 'text' ? nextCharacterPosition() : { chapter_path: nextPath() }
  const nextPositionText = () => mode === 'text'
    ? (() => { const position = nextCharacterPosition(); return `字符 ${position.start}—${position.end}` })()
    : nextPath().join(' > ')

  const data = result?.data && typeof result.data === 'object' ? result.data : result
  if (data && typeof data === 'object') data.input_type = mode === 'text' ? 'text' : 'file'

  const visit = (node: any, parentKey = '') => {
    if (Array.isArray(node)) {
      node.forEach(item => visit(item, parentKey))
      return
    }
    if (!node || typeof node !== 'object') return
    if (mode === 'text') {
      delete node.file_name
      delete node.file_type
      delete node.page_count
      delete node.parse_status
    }

    const handled = new Set<string>()
    if (typeof node.input_type === 'string') node.input_type = mode === 'text' ? 'text' : 'file'
    for (const obsoleteKey of ['source_pages', 'page_number', 'page_index', 'paragraph_index']) {
      if (obsoleteKey in node) delete node[obsoleteKey]
    }
    for (const key of ['source_position', 'position', 'text_position', 'entity_position']) {
      if (node[key] && typeof node[key] === 'object') {
        if (mode === 'text' && node[key].__demo_exact === true) {
          delete node[key].__demo_exact
        } else {
          node[key] = nextPosition()
        }
        handled.add(key)
      }
    }
    if (Array.isArray(node.source_sections) && node.source_sections.length) {
      if (mode === 'text') {
        delete node.source_sections
        if (!node.source_position && !node.position) node.position = nextCharacterPosition()
      } else {
        node.source_sections = [nextPath().join(' > ')]
        handled.add('source_sections')
      }
    }
    if (typeof node.source_section === 'string' && node.source_section.trim()) {
      if (mode === 'text') {
        delete node.source_section
        if (!node.source_position && !node.position) node.position = nextCharacterPosition()
      } else {
        node.source_section = nextPath().join(' > ')
        handled.add('source_section')
      }
    }
    if (typeof node.section === 'string' && ('count' in node || 'percentage' in node || 'ratio' in node)) {
      node.section = nextPositionText()
      handled.add('section')
    }
    if (node.triple_id && !node.source_position && !node.position) {
      node.position = nextPosition()
      handled.add('position')
    }
    if (['research_question_sentences', 'research_question_phrases', 'structured_research_questions'].includes(parentKey)
      && !node.source_position && !node.position && !node.source_sections) {
      if (mode === 'text') {
        node.position = nextCharacterPosition()
        handled.add('position')
      } else {
        node.source_sections = [nextPath().join(' > ')]
        handled.add('source_sections')
      }
    }

    Object.entries(node).forEach(([key, child]) => {
      if (!handled.has(key)) visit(child, key)
    })
  }

  visit(result)
  return result
}

function positionModeForResult(key: string, tool: ToolDefinition): PositionPreviewMode {
  if (['demoTextResult', 'demoBatchTextResult'].includes(key)) return 'text'
  if (['demoFileResult', 'demoBatchFileResult', 'apiFileResult', 'apiBatchFileResult', 'demoHistoryResult', 'demoCollectionResult'].includes(key)) return 'file'
  const firstMode = tool.inputModes?.[0]
  return firstMode === 'text' || firstMode === 'batch-text' ? 'text' : 'file'
}

function normalizeDomainClassificationResult(value: unknown) {
  const result = cloneResult(value)

  const pathOf = (item: any) => {
    if (Array.isArray(item?.classification_path) && item.classification_path.length) return item.classification_path.filter(Boolean)
    return [item?.level_1, item?.level_2, item?.level_3].filter(Boolean)
  }

  const visit = (node: any) => {
    if (Array.isArray(node)) {
      node.forEach(visit)
      return
    }
    if (!node || typeof node !== 'object') return

    const sourceResults = Array.isArray(node.multilevel_classification_results)
      ? node.multilevel_classification_results
      : Array.isArray(node.classifications)
        ? node.classifications
        : []

    if (sourceResults.length) {
      const primarySource = sourceResults.find((item: any) => ['main', 'primary'].includes(String(item?.role || '').toLowerCase())) || sourceResults[0]
      const primary = { ...primarySource, order: 1, role: 'main', classification_path: pathOf(primarySource) }
      const existingCandidates = Array.isArray(node.candidate_classifications) ? node.candidate_classifications : []
      const candidateSources = [primarySource, ...existingCandidates, ...sourceResults]
      const seen = new Set<string>()
      node.candidate_classifications = candidateSources.flatMap((item: any, index: number) => {
        const classificationPath = pathOf(item)
        const key = classificationPath.join(' > ') || String(item?.candidate_id || item?.label || index)
        if (!key || seen.has(key)) return []
        seen.add(key)
        const { role: _role, order: _order, ...candidate } = item
        return [{
          ...candidate,
          candidate_id: item?.candidate_id || `domain_candidate_${seen.size}`,
          candidate_rank: seen.size,
          classification_path: classificationPath,
        }]
      })
      node.multilevel_classification_results = [primary]
      if (Array.isArray(node.classifications)) node.classifications = [primary]
      if (node.data_distribution_report && typeof node.data_distribution_report === 'object') {
        const report = node.data_distribution_report
        report.classification_assignment_count = 1
        report.by_level_1 = primary.level_1 ? [{ category: primary.level_1, document_count: 1, percentage: 100 }] : []
        report.by_level_2 = primary.level_2 ? [{ category: primary.level_2, assignment_count: 1 }] : []
        report.by_level_3 = primary.level_3 ? [{ category: primary.level_3, assignment_count: 1 }] : []
      }
    }

    Object.values(node).forEach(visit)
  }

  visit(result)
  return result
}

function enrichLiteratureClassificationCandidates(value: unknown, language: 'zh' | 'en') {
  const result = cloneResult(value)

  const codeOf = (item: any) => String(item?.clc_code || item?.code || '').trim()
  const combinationKey = (main: any, secondary: any) => `${codeOf(main)}>${codeOf(secondary)}`
  const alternativeCatalog = [
    { clc_code: 'P315.9', label: '地震工程', path: '天文学、地球科学 > 地球物理学 > 地震学 > 地震工程' },
    { clc_code: 'TU311.3', label: '结构抗震分析', path: '工业技术 > 建筑科学 > 建筑结构 > 结构抗震分析' },
    { clc_code: 'TP18', label: '人工智能', path: '工业技术 > 自动化技术、计算机技术 > 人工智能' },
    { clc_code: 'TP391.41', label: '图像处理与计算机视觉', path: '工业技术 > 自动化技术、计算机技术 > 计算机视觉' },
    { clc_code: 'TP391.4', label: '模式识别与智能系统', path: '工业技术 > 自动化技术、计算机技术 > 计算技术、计算机技术 > 模式识别与智能系统' },
    { clc_code: 'TP274.2', label: '数据采集与处理', path: '工业技术 > 自动化技术、计算机技术 > 自动化技术及设备 > 数据处理' },
    { clc_code: 'TH17', label: '机械制造工艺', path: '工业技术 > 机械、仪表工业 > 机械制造工艺' },
    { clc_code: 'R587.1', label: '糖尿病', path: '医药、卫生 > 内科学 > 内分泌腺疾病及代谢病 > 糖尿病' },
    { clc_code: 'Q811.4', label: '生物信息论', path: '生物科学 > 生物工程学 > 生物工程基础理论 > 生物信息论' },
    { clc_code: 'R319', label: '医学信息学', path: '医药、卫生 > 医学研究方法 > 医学信息学' },
  ]
  const relevantAlternatives = (codes: Set<string>) => {
    const preferredCodes = codes.has('P315.9') || codes.has('TU311.3')
      ? ['TP18', 'TP391.4', 'P315.9', 'TU311.3']
      : codes.has('R587.1') || codes.has('Q811.4') || codes.has('R319')
        ? ['R319', 'Q811.4', 'TP18', 'R587.1']
        : codes.has('TH17') || codes.has('TP391.41')
          ? ['TP18', 'TP391.4', 'TH17', 'TP391.41']
          : codes.has('TP274.2')
            ? ['TP18', 'TP391.4', 'TP274.2']
            : codes.has('TP18')
              ? ['TP391.41', 'TP391.4', 'TP274.2']
              : alternativeCatalog.map(item => item.clc_code)
    return preferredCodes
      .map(code => alternativeCatalog.find(item => item.clc_code === code))
      .filter(Boolean) as typeof alternativeCatalog
  }
  const withCandidateDefaults = (item: any, confidence: number) => ({
    ...item,
    confidence: Number(item?.confidence ?? confidence),
    evidence: Array.isArray(item?.evidence) && item.evidence.length
      ? item.evidence
      : [language === 'zh' ? '根据文献内容与中图分类语义相关性形成候选。' : '根据英文文献内容的跨语言语义映射形成候选。'],
  })

  const visit = (node: any) => {
    if (Array.isArray(node)) {
      node.forEach(visit)
      return
    }
    if (!node || typeof node !== 'object') return

    const classifications = Array.isArray(node.classifications) ? node.classifications : []
    if (!classifications.length || typeof node.is_interdisciplinary !== 'boolean') {
      Object.values(node).forEach(visit)
      return
    }
    const isInterdisciplinary = node.is_interdisciplinary === true
    const main = classifications.find((item: any) => String(item?.role).toLowerCase() === 'main') || classifications[0]
    const secondary = classifications.find((item: any) => String(item?.role).toLowerCase() === 'secondary') || classifications[1]

    if (isInterdisciplinary && main && secondary) {
      const officialMain = { ...main, order: 1, role: 'main' }
      const officialSecondary = { ...secondary, order: 2, role: 'secondary' }
      node.classifications = [officialMain, officialSecondary]
      node.classification_count = 2
      const currentKey = combinationKey(main, secondary)
      const existing = (Array.isArray(node.candidate_classifications) ? node.candidate_classifications : []).filter((candidate: any) => {
        const candidateMain = candidate?.main_classification
        const candidateSecondary = candidate?.secondary_classification
        return candidateMain && candidateSecondary && combinationKey(candidateMain, candidateSecondary) !== currentKey
      })
      const excludedCodes = new Set([codeOf(main), codeOf(secondary)])
      const alternatives = relevantAlternatives(excludedCodes).filter(item => !excludedCodes.has(codeOf(item)))
      const preferredAlternative = [codeOf(main), codeOf(secondary)].includes('Q811.4')
        ? alternativeCatalog.find(item => item.clc_code === 'R319') || alternatives[0]
        : alternatives[0]
      const secondAlternative = alternatives.find(item => codeOf(item) !== codeOf(preferredAlternative)) || alternatives[1] || preferredAlternative
      const fallbackCandidates = preferredAlternative ? [
        {
          candidate_id: `${language}_interdisciplinary_candidate_1`,
          role: 'combination',
          main_classification: withCandidateDefaults({ ...officialMain }, 0.86),
          secondary_classification: withCandidateDefaults({ ...preferredAlternative, order: 2, role: 'secondary' }, 0.84),
          combination_confidence: Math.max(0, Math.min(Number(main.confidence) || 0.9, 0.86)),
          difference_from_current: '保留当前主分类，使用另一相关学科作为次分类。',
        },
        {
          candidate_id: `${language}_interdisciplinary_candidate_2`,
          role: 'combination',
          main_classification: withCandidateDefaults({ ...preferredAlternative, order: 1, role: 'main' }, 0.82),
          secondary_classification: withCandidateDefaults({ ...secondAlternative, order: 2, role: 'secondary' }, 0.8),
          combination_confidence: Math.max(0, Math.min(Number(secondary.confidence) || 0.84, 0.82)),
          difference_from_current: '使用另一组完整的主分类与次分类关系，供人工复核。',
        },
      ].filter(candidate => combinationKey(candidate.main_classification, candidate.secondary_classification) !== currentKey) : []

      const candidates = existing.length ? existing : fallbackCandidates
      node.candidate_classifications = candidates.map((candidate: any, index: number) => ({
        ...candidate,
        candidate_id: candidate.candidate_id || `${language}_interdisciplinary_candidate_${index + 1}`,
        candidate_rank: index + 1,
      }))
    } else if (main) {
      const officialMain = { ...main, order: 1, role: 'main' }
      const officialCode = codeOf(officialMain)
      node.classifications = [officialMain]
      node.classification_count = 1

      const responseCandidates = Array.isArray(node.candidate_classifications) ? node.candidate_classifications : []
      const candidateSources = [...responseCandidates, ...classifications.slice(1)]
      const seenCodes = new Set<string>([officialCode])
      const candidates = candidateSources.flatMap((candidate: any) => {
        if (candidate?.main_classification || candidate?.secondary_classification) return []
        const code = codeOf(candidate)
        if (!code || seenCodes.has(code)) return []
        seenCodes.add(code)
        return [candidate]
      })
      const fallbackCandidates = relevantAlternatives(seenCodes).filter(item => !seenCodes.has(codeOf(item))).slice(0, 2)
      node.candidate_classifications = (candidates.length ? candidates : fallbackCandidates).map((candidate: any, index: number) => ({
        ...withCandidateDefaults(candidate, Math.max(0.72, 0.88 - index * 0.06)),
        candidate_id: candidate.candidate_id || `${language}_single_candidate_${index + 1}`,
        candidate_rank: index + 1,
      }))
    }

    Object.values(node).forEach(visit)
  }

  visit(result)
  return result
}

function enrichClusterLabelResult(value: unknown) {
  const result = cloneResult(value)
  const data = result.data || result
  const labels = Array.isArray(data.labels) ? data.labels : []
  data.label_generation_process_report = {
    stages: [
      { order: 1, name: '读取类簇结果', status: 'completed', output: `${data.cluster_count || labels.length} 个类簇` },
      { order: 2, name: '汇总代表特征', status: 'completed', output: '关键词、命名实体和中心句' },
      { order: 3, name: '生成候选标签', status: 'completed', output: `${labels.reduce((sum: number, item: any) => sum + (item.candidate_labels?.length || 0), 0)} 个候选标签` },
      { order: 4, name: '差异化筛选', status: 'completed', output: `阈值 ${data.parameters?.distinctiveness_threshold ?? 0.75}` },
      { order: 5, name: '输出推荐标签', status: 'completed', output: `${data.generated_label_count || labels.length} 个标签` },
    ],
    strategy: data.generation_strategy || 'adaptive_label_generation',
    parameters: data.parameters || {},
  }
  data.label_distinctiveness_optimization_result = {
    threshold: data.parameters?.distinctiveness_threshold ?? 0.75,
    duplicate_candidate_count: data.statistics?.duplicate_candidate_count ?? 0,
    filtered_candidate_count: data.statistics?.filtered_candidate_count ?? 0,
    clusters: labels.map((item: any) => ({
      cluster_id: item.cluster_id,
      recommended_label: item.recommended_label,
      distinctiveness: item.distinctiveness,
      difference_explanation: item.difference_explanation,
      optimization_status: item.distinctiveness >= (data.parameters?.distinctiveness_threshold ?? 0.75) ? 'passed' : 'needs_review',
    })),
  }
  const strictOutput = {
    cluster_labels: labels,
    label_generation_process_report: data.label_generation_process_report,
    label_distinctiveness_optimization_result: data.label_distinctiveness_optimization_result,
  }
  if (result.data) result.data = strictOutput
  else Object.assign(result, strictOutput)
  delete result.meta
  return result
}

function enrichStructuredReviewResult(value: unknown) {
  const result = cloneResult(value)
  const source = result.data || result
  const evidenceIndex = Array.isArray(source.evidence_index) ? source.evidence_index : []
  const tree = (Array.isArray(source.tree) ? source.tree : []).map((question: any) => ({
    ...question,
    methods: (Array.isArray(question.methods) ? question.methods : []).map((method: any) => ({
      ...method,
      progress: (Array.isArray(method.progress) ? method.progress : []).map((progress: any) => ({
        ...progress,
        source_evidence: evidenceIndex.filter((evidence: any) => (progress.source_ids || []).includes(evidence.document_id)),
      })),
    })),
  }))
  const returnedClusterReport = source.cluster_induction_results || {}
  const returnedClusters = Array.isArray(returnedClusterReport.clusters)
    ? returnedClusterReport.clusters
    : Array.isArray(source.problem_clusters) ? source.problem_clusters : []
  const clusterInductionResults = {
    ...returnedClusterReport,
    cluster_count: returnedClusterReport.cluster_count ?? returnedClusters.length,
    clusters: returnedClusters,
    induction_basis: returnedClusterReport.induction_basis || '研究问题语义相似度、研究方法共现和来源证据一致性',
  }
  const strictOutput = {
    topic: source.topic,
    document_count: source.document_count,
    tree,
    cluster_induction_results: clusterInductionResults,
    structured_report: source.structured_report || { overview: '', sections: [] },
    trend_hotspot_distribution: {
      ...source.trend_hotspot_distribution,
      time_range: source.trend_hotspot_distribution?.time_range || source.statistics?.time_range || '未提供',
      hotspots: source.trend_hotspot_distribution?.hotspots || source.trends?.hotspots || [],
    },
    evidence_index: evidenceIndex,
    statistics: source.statistics || {},
  }
  if (result.data) result.data = strictOutput
  else Object.assign(result, strictOutput)
  delete result.meta
  return result
}

const clusterLabelBatchTextResult = enrichClusterLabelResult((clusterLabelRuntimeResponses as any).batchText)
const clusterLabelBatchFileResult = enrichClusterLabelResult((clusterLabelRuntimeResponses as any).batchFile)
const clusterLabelHistoryResult = enrichClusterLabelResult((clusterLabelRuntimeResponses as any).history)
const structuredReviewBatchTextResult = enrichStructuredReviewResult((structuredReviewRuntime as any).batchText)
const structuredReviewBatchFileResult = enrichStructuredReviewResult((structuredReviewRuntime as any).batchFile)
const structuredReviewCollectionResult = enrichStructuredReviewResult((structuredReviewRuntime as any).collection)

function responsePayloads(response: Record<string, any>) {
  const data = response?.data ?? response
  if (!Array.isArray(data?.results)) return data ? [data] : []
  return data.results.map((item: any) => item?.result?.data ?? item?.result ?? item?.data?.data ?? item?.data ?? item).filter(Boolean)
}

const enKeywordMappings = [
  { system: 'CLC', code: 'Q811.4', label: '生物信息论', confidence: 0.96 },
  { system: 'CLC', code: 'TP181', label: '自动识别与检测', confidence: 0.94 },
  { system: 'CLC', code: 'R318', label: '生物医学工程', confidence: 0.93 },
  { system: 'CLC', code: 'Q811.4', label: '生物信息论', confidence: 0.92 },
  { system: 'CLC', code: 'Q78', label: '分子生物学', confidence: 0.91 },
  { system: 'CLC', code: 'Q78', label: '分子生物学', confidence: 0.90 },
  { system: 'CLC', code: 'Q811.4', label: '生物信息论', confidence: 0.89 },
]
function enrichEnKeywordPreview(value: unknown) {
  const result = cloneResult(value)
  for (const payload of responsePayloads(result)) {
    for (const [index, item] of (payload.keywords_or_topic_phrases || []).entries()) {
      item.terminology_source = { type: 'external', library_name: '生物医学英文术语库' }
      item.classification_mapping = enKeywordMappings[index % enKeywordMappings.length]
    }
  }
  return result
}
const generatedEnKeyword = (generatedTools as Record<string, ToolDefinition>)['en-keyword'] as any
const generatedZhKeyword = (generatedTools as Record<string, ToolDefinition>)['zh-keyword'] as any
const enKeywordPreviewResponse = enrichEnKeywordPreview(generatedEnKeyword.response)
const enKeywordDemoTextResult = enrichEnKeywordPreview(generatedEnKeyword.demoTextResult)
const enKeywordDemoBatchTextResult = enrichEnKeywordPreview(generatedEnKeyword.demoBatchTextResult)
const enKeywordDemoFileResult = enrichEnKeywordPreview(generatedEnKeyword.demoFileResult)
const enKeywordDemoBatchFileResult = enrichEnKeywordPreview(generatedEnKeyword.demoBatchFileResult)

const definitionResponse = cloneResult((generatedTools as Record<string, ToolDefinition>)['definition-detect'].response)
definitionResponse.data.definitions = [
  {
    definition_id: 'DEF-001',
    concept: '多模态学习',
    definition_sentence: '多模态学习是指联合建模两种及以上模态信息的机器学习方法。',
    definition_content: '联合建模两种及以上模态信息的机器学习方法',
    position: { chapter_path: ['（一）理论基础', '1．核心概念', '1.1 多模态学习'] },
    confidence: 0.98,
    review_status: '已确认',
  },
  {
    definition_id: 'DEF-002',
    concept: '跨模态对齐',
    definition_sentence: '跨模态对齐是通过共享语义空间建立不同模态表达对应关系的过程。',
    definition_content: '通过共享语义空间建立不同模态表达对应关系的过程',
    position: { chapter_path: ['（二）方法设计', '2．跨模态建模', '2.2 跨模态对齐机制'] },
    confidence: 0.95,
    review_status: '已确认',
  },
]
definitionResponse.data.concept_definition_mappings = definitionResponse.data.definitions.map((item: any) => ({
  concept: item.concept,
  definition: item.definition_content,
  source: item.position.chapter_path.join(' > '),
  confidence: item.confidence,
}))
definitionResponse.data.summary = {
  definition_sentence_count: definitionResponse.data.definitions.length,
  concept_count: definitionResponse.data.definitions.length,
  mapping_count: definitionResponse.data.concept_definition_mappings.length,
  average_confidence: 0.965,
  pending_review_count: 0,
}
definitionResponse.data.statistical_analysis_report = {
  definition_sentence_count: definitionResponse.data.definitions?.length || 0,
  concept_count: new Set((definitionResponse.data.definitions || []).map((item: any) => item.concept)).size,
  mapping_count: (definitionResponse.data.concept_definition_mappings || []).length,
  pending_review_count: (definitionResponse.data.definitions || []).filter((item: any) => item.review_status === '待复核').length,
  section_distribution: [
    { section: '理论基础', count: 1, percentage: 50 },
    { section: '方法设计', count: 1, percentage: 50 },
  ],
}

const generalNerPreviewResponse = {
  code: 200,
  message: 'success',
  data: {
    summary: { entity_count: 3, person_count: 0, location_count: 0, organization_count: 2, event_count: 1 },
    entities: [
      { entity_id: 'GNER-001', text: '燕山大学', type: 'ORGANIZATION', language: 'zh', position: { chapter_path: ['（三）合作研究', '1．合作机构', '1.1 国内合作单位'] }, context: '燕山大学与 University of Cambridge 开展联合研究。', canonical_entity_id: 'ORG-CN-00128', confidence: 0.99 },
      { entity_id: 'GNER-002', text: 'University of Cambridge', type: 'ORGANIZATION', language: 'en', position: { chapter_path: ['（三）合作研究', '1．合作机构', '1.2 国外合作单位'] }, context: '燕山大学与 University of Cambridge 开展联合研究。', canonical_entity_id: 'ORG-GB-00001', confidence: 0.99 },
      { entity_id: 'GNER-003', text: '联合研究', type: 'EVENT', language: 'zh', position: { chapter_path: ['（三）合作研究', '2．合作方式', '2.1 联合研究计划'] }, context: '燕山大学与 University of Cambridge 开展联合研究。', canonical_entity_id: 'EVENT-RESEARCH-COLLABORATION', confidence: 0.93 },
    ],
    entity_mappings: [
      { canonical_entity_id: 'ORG-CN-00128', canonical_names: { zh: '燕山大学', en: 'Yanshan University' }, abbreviations: ['YSU'], aliases: { zh: ['燕大'], en: ['Yanshan Univ.'] }, observed_mentions: [{ text: '燕山大学' }], type: 'ORGANIZATION', occurrence_count: 1 },
      { canonical_entity_id: 'ORG-GB-00001', canonical_names: { zh: '剑桥大学', en: 'University of Cambridge' }, abbreviations: ['Cambridge'], aliases: { zh: ['剑桥'], en: ['Cambridge University'] }, observed_mentions: [{ text: 'University of Cambridge' }], type: 'ORGANIZATION', occurrence_count: 1 },
      { canonical_entity_id: 'EVENT-RESEARCH-COLLABORATION', canonical_names: { zh: '科研合作', en: 'Research Collaboration' }, abbreviations: ['RC'], aliases: { zh: ['联合研究'], en: ['Joint Research'] }, observed_mentions: [{ text: '联合研究' }], type: 'EVENT', occurrence_count: 1 },
    ],
  },
}

const researchNerPreviewResponse = {
  code: 200,
  message: 'success',
  data: {
    summary: { entity_count: 5, method_count: 1, data_resource_count: 1, instrument_count: 1, theory_principle_count: 1, research_problem_count: 1 },
    entities: [
      { research_entity_id: 'RNER-001', text: 'Transformer模型', type: '科研方法', language: 'zh', position: { chapter_path: ['（三）研究方案', '2．技术路线', '2.1 模型设计'] }, context: '本文采用Transformer模型建模长距离依赖。', standard_term_id: 'STD-METHOD-001', standard_names: { zh: 'Transformer模型', en: 'Transformer Model' }, confidence: 0.98 },
      { research_entity_id: 'RNER-002', text: 'ETTh1数据集', type: '数据资料', language: 'zh', position: { chapter_path: ['（三）研究方案', '3．实验设计', '3.1 实验数据'] }, context: '实验在ETTh1数据集上完成。', standard_term_id: 'STD-DATA-014', standard_names: { zh: 'ETTh1数据集', en: 'ETTh1 Dataset' }, confidence: 0.97 },
      { research_entity_id: 'RNER-003', text: 'GPU服务器', type: '仪器设备', language: 'zh', position: { chapter_path: ['（三）研究方案', '3．实验设计', '3.2 实验环境'] }, context: '模型训练运行于GPU服务器。', standard_term_id: 'STD-DEVICE-008', standard_names: { zh: 'GPU服务器', en: 'GPU Server' }, confidence: 0.94 },
      { research_entity_id: 'RNER-004', text: '自注意力机制', type: '理论原理', language: 'zh', position: { chapter_path: ['（二）研究内容', '2．模型原理', '2.2 自注意力机制'] }, context: '网络通过自注意力机制计算变量间依赖。', standard_term_id: 'STD-THEORY-021', standard_names: { zh: '自注意力机制', en: 'Self-attention Mechanism' }, confidence: 0.96 },
      { research_entity_id: 'RNER-005', text: '长距离依赖建模', type: '研究问题', language: 'zh', position: { chapter_path: ['（二）研究内容', '1．研究问题', '1.3 长距离依赖建模'] }, context: '研究重点是提高长距离依赖建模能力。', standard_term_id: 'STD-PROBLEM-031', standard_names: { zh: '长距离依赖建模', en: 'Long-range Dependency Modeling' }, confidence: 0.92 },
    ],
    standard_term_mappings: [
      { standard_term_id: 'STD-METHOD-001', standard_names: { zh: 'Transformer模型', en: 'Transformer Model' }, abbreviations: ['Transformer'], other_aliases: ['变换器模型'], observed_mentions: [{ text: 'Transformer模型' }], type: '科研方法', mapping_status: '已映射', mapping_confidence: 0.99 },
      { standard_term_id: 'STD-DATA-014', standard_names: { zh: 'ETTh1数据集', en: 'ETTh1 Dataset' }, abbreviations: ['ETTh1'], other_aliases: ['电力变压器温度数据集'], observed_mentions: [{ text: 'ETTh1数据集' }], type: '数据资料', mapping_status: '已映射', mapping_confidence: 0.98 },
      { standard_term_id: 'STD-DEVICE-008', standard_names: { zh: 'GPU服务器', en: 'GPU Server' }, abbreviations: ['GPU'], other_aliases: ['图形处理器服务器'], observed_mentions: [{ text: 'GPU服务器' }], type: '仪器设备', mapping_status: '已映射', mapping_confidence: 0.96 },
      { standard_term_id: 'STD-THEORY-021', standard_names: { zh: '自注意力机制', en: 'Self-attention Mechanism' }, abbreviations: ['Self-Attention'], other_aliases: ['自注意机制'], observed_mentions: [{ text: '自注意力机制' }], type: '理论原理', mapping_status: '已映射', mapping_confidence: 0.98 },
      { standard_term_id: 'STD-PROBLEM-031', standard_names: { zh: '长距离依赖建模', en: 'Long-range Dependency Modeling' }, abbreviations: ['LRDM'], other_aliases: ['长期依赖建模'], observed_mentions: [{ text: '长距离依赖建模' }], type: '研究问题', mapping_status: '已映射', mapping_confidence: 0.95 },
    ],
  },
}

// “预览可视化弹窗”使用的完整审核数据。在线测试仍由真实接口响应覆盖，
// 此处只保证原型预览中的统计、实体详情和本体映射均可被完整检查。
const domainNerPreviewResponse = {
  code: 200,
  message: 'success',
  data: {
    selected_domain: 'medicine',
    summary: {
      entity_count: 4,
      drug_count: 1,
      disease_count: 1,
      treatment_count: 1,
      mapped_count: 3,
      pending_review_count: 1,
    },
    entities: [
      {
        entity_id: 'DNER-001',
        text: '阿司匹林',
        domain_name: '医学',
        type: '药物',
        position: { chapter_path: ['（二）研究内容', '1．药物干预', '1.1 阿司匹林作用机制'] },
        context: '阿司匹林可用于缓解轻度疼痛并抑制血小板聚集。',
        standard_kb_id: 'MESH:D001241',
        confidence: 0.98,
      },
      {
        entity_id: 'DNER-002',
        text: '疼痛',
        domain_name: '医学',
        type: '疾病或症状',
        position: { chapter_path: ['（二）研究内容', '1．药物干预', '1.1 阿司匹林作用机制'] },
        context: '阿司匹林可用于缓解轻度疼痛并抑制血小板聚集。',
        standard_kb_id: 'MESH:D010146',
        confidence: 0.94,
      },
      {
        entity_id: 'DNER-003',
        text: '血小板聚集',
        domain_name: '医学',
        type: '生物过程',
        position: { chapter_path: ['（二）研究内容', '1．药物干预', '1.2 血小板聚集抑制'] },
        context: '阿司匹林可用于缓解轻度疼痛并抑制血小板聚集。',
        standard_kb_id: 'MESH:D010978',
        confidence: 0.96,
      },
      {
        entity_id: 'DNER-004',
        text: '低剂量抗血小板治疗',
        domain_name: '医学',
        type: '治疗方法',
        position: { chapter_path: ['（四）研究结论', '2．临床建议', '2.1 低剂量治疗评估'] },
        context: '低剂量抗血小板治疗仍需结合患者风险进行评估。',
        standard_kb_id: '未映射',
        confidence: 0.86,
      },
    ],
    ontology_mappings: [
      {
        standard_kb_id: 'MESH:D001241',
        domain_name: '医学',
        type: '药物',
        standard_names: { zh: '阿司匹林', en: 'Aspirin' },
        ontology_path: '医学实体 / 药物 / 非甾体抗炎药',
        aliases: ['乙酰水杨酸'],
        observed_mentions: [{ text: '阿司匹林' }],
        mapping_status: '已映射',
        mapping_confidence: 0.99,
      },
      {
        standard_kb_id: 'MESH:D010146',
        domain_name: '医学',
        type: '疾病或症状',
        standard_names: { zh: '疼痛', en: 'Pain' },
        ontology_path: '医学实体 / 临床表现 / 症状',
        aliases: ['痛觉'],
        observed_mentions: [{ text: '疼痛' }],
        mapping_status: '已映射',
        mapping_confidence: 0.96,
      },
      {
        standard_kb_id: 'MESH:D010978',
        domain_name: '医学',
        type: '生物过程',
        standard_names: { zh: '血小板聚集', en: 'Platelet Aggregation' },
        ontology_path: '医学实体 / 生物过程 / 凝血过程',
        aliases: ['血小板凝集'],
        observed_mentions: [{ text: '血小板聚集' }],
        mapping_status: '已映射',
        mapping_confidence: 0.98,
      },
      {
        standard_kb_id: '未映射',
        domain_name: '医学',
        type: '治疗方法',
        standard_names: { zh: '低剂量抗血小板治疗', en: 'Low-dose antiplatelet therapy' },
        ontology_path: '医学实体 / 治疗方法 / 待复核',
        aliases: ['低剂量抗血小板疗法'],
        observed_mentions: [{ text: '低剂量抗血小板治疗' }],
        mapping_status: '待复核',
        mapping_confidence: 0.71,
      },
    ],
  },
}

const reviewerSupplementParams: Record<string, ToolDefinition['params']> = {
  'zh-classify': [
    ['clc_labeled_data', 'resource', 'required', '标准中图分类号标注数据，可选择数据库当前资源或上传新资源'],
  ],
  'en-classify': [
    ['clc_standard_resource', 'resource', 'required', '中图分类标准数据及版本'],
    ['cross_language_mapping_rules', 'resource', 'required', '英文科研术语到中图分类体系的映射规则'],
  ],
  'domain-classify': [
    ['domain_scientific_literature_data', 'resource', 'required', '领域专业科技文献数据'],
    ['domain_classification_rules', 'resource', 'required', '专业领域一级、二级、三级分类规则'],
    ['manually_labeled_training_data', 'resource', 'required', '专业领域人工标注训练数据'],
  ],
  'en-keyword': [
    ['domain_terminology_library', 'resource', 'optional', '英文领域术语库，用于缩写识别、消歧和术语规范化'],
    ['classification_mapping_table', 'resource', 'optional', '英文关键词到科研分类标签的映射表'],
  ],
  'rq-detect': [
    ['text_format', 'string', 'required', '文本格式：auto、plain_text、sectioned_text 或 structured_json'],
    ['document_scope', 'string', 'optional', '分析范围：full_document、abstract_and_introduction 或 selected_sections'],
  ],
  'citation-sentiment': [
    ['citation_sentence', 'string', 'conditional', '单文本模式：包含引文标记的引用句'],
    ['previous_context', 'string', 'optional', '引用句上文'],
    ['next_context', 'string', 'optional', '引用句下文'],
    ['citations', 'object[]', 'conditional', '批量文本模式：多条引用句及其上下文'],
    ['citation_metadata', 'object[]|file', 'conditional', '文本模式由用户填写或上传；文件模式默认从参考文献列表自动解析，解析失败时补充或上传'],
  ],
  'citation-intent': [
    ['citation_sentence', 'string', 'conditional', '单文本模式：包含引文标记的引用句'],
    ['previous_context', 'string', 'optional', '引用句上文'],
    ['next_context', 'string', 'optional', '引用句下文'],
    ['citations', 'object[]', 'conditional', '批量文本模式：多条引用句及其上下文'],
    ['citation_metadata', 'object[]|file', 'conditional', '文本模式由用户填写或上传；文件模式默认从参考文献列表自动解析，解析失败时补充或上传'],
    ['preprocessed_training_set', 'resource', 'required', '已完成清洗、标签统一和类别平衡的引用意图训练集'],
  ],
  'general-ner': [
    ['general_annotated_corpus', 'resource', 'required', '通用领域标注语料'],
  ],
  'research-ner': [
    ['multi_domain_research_corpus', 'resource', 'required', '多领域科研语料'],
    ['research_labeled_data', 'resource', 'required', '科研实体人工标注数据'],
  ],
  'domain-ner': [
    ['ontology_classification_system', 'resource', 'required', '专业领域本体分类体系'],
    ['domain_labeled_training_data', 'resource', 'required', '专业领域实体标注训练数据'],
  ],
  'relation-extract': [
    ['upstream_ner_record_id', 'string', 'required', '数据库中已完成的命名实体识别历史记录编号'],
  ],
}

const reviewerPayloadSupplements: Record<string, Record<string, unknown>> = {
  'zh-classify': { clc_labeled_data: { source: 'system', resource_id: 'SELECTED_CLC_LABELED_DATA' } },
  'en-classify': {
    clc_standard_resource: { source: 'system', resource_id: 'SELECTED_CLC_STANDARD' },
    cross_language_mapping_rules: { source: 'system', resource_id: 'SELECTED_EN_CLC_MAPPING_RULES' },
  },
  'domain-classify': {
    domain_scientific_literature_data: { source: 'system', resource_id: 'SELECTED_DOMAIN_LITERATURE_DATA' },
    domain_classification_rules: { source: 'system', resource_id: 'SELECTED_DOMAIN_RULES' },
    manually_labeled_training_data: { source: 'system', resource_id: 'SELECTED_LABELED_TRAINING_DATA' },
  },
  'en-keyword': {
    domain_terminology_library: { source: 'system', resource_id: 'SELECTED_TERMINOLOGY_LIBRARY' },
    classification_mapping_table: { source: 'system', resource_id: 'SELECTED_CLASSIFICATION_MAPPING' },
  },
  'rq-detect': { text_format: 'auto', document_scope: 'full_document' },
  'citation-sentiment': {
    documentType: 'citation-sentiment',
    citation_sentence: 'Previous work has demonstrated strong performance in this task [12].',
    previous_context: 'The task has received increasing attention in recent years.',
    next_context: 'However, generalization under domain shift remains unresolved.',
    citation_metadata: [{ reference_id: 'REF12', citation_marker: '[12]', authors: ['Author A'], work_name: 'Referenced work' }],
  },
  'citation-intent': {
    documentType: 'citation-intent',
    citation_sentence: '本文采用已有研究提出的图卷积建模策略[12]。',
    previous_context: '为增强用户关系结构表示，本文引入图结构编码。',
    next_context: '编码结果随后与文本语义特征进行融合。',
    citation_metadata: [{ reference_id: 'REF12', citation_marker: '[12]', authors: ['作者甲'], work_name: '图卷积建模研究' }],
    preprocessed_training_set: { source: 'system', resource_id: 'SELECTED_CITATION_INTENT_TRAINING_SET' },
  },
  'general-ner': { general_annotated_corpus: { source: 'system', resource_id: 'SELECTED_GENERAL_ANNOTATED_CORPUS' } },
  'research-ner': {
    multi_domain_research_corpus: { source: 'system', resource_id: 'SELECTED_RESEARCH_CORPUS' },
    research_labeled_data: { source: 'system', resource_id: 'SELECTED_RESEARCH_LABELED_DATA' },
  },
  'domain-ner': {
    ontology_classification_system: { source: 'system', resource_id: 'SELECTED_ONTOLOGY' },
    domain_labeled_training_data: { source: 'system', resource_id: 'SELECTED_DOMAIN_NER_TRAINING_DATA' },
  },
  'relation-extract': {
    upstream_ner_record_id: 'NER-20260816-001',
  },
}

function mergeParams(base: ToolDefinition['params'], additions: ToolDefinition['params']) {
  const rows = [...(base || [])]
  const existing = new Set(rows.map(row => row[0]))
  for (const row of additions || []) {
    if (existing.has(row[0])) continue
    rows.push(row)
    existing.add(row[0])
  }
  return rows
}

const tiAlFundProjectText = '项目名称：TiAl合金中氢原子团簇的第一性原理计算及实验研究。\n项目摘要：TiAl合金是一种在汽车及航空航天等领域具有广阔应用前景的轻质高强结构材料。该类合金的本征低温脆性问题已开展了大量研究，但服役环境中氢原子引起的环境脆化仍缺少系统认识。本项目拟采用第一性原理计算和必要的实验方法，系统研究TiAl合金α2相、γ相及α2/γ界面中氢原子团簇行为，结合电子结构分析揭示氢原子团簇及固溶行为对缺陷和界面的影响，辨析TiAl合金中氢脆的微观机理。研究将为TiAl合金设计、制备和服役行为理解提供理论基础。\n关键词：第一性原理计算；氢原子团簇；缺陷；氢脆；TiAl合金。'

const tiAlFundMoves = [
  {
    label: '立项依据',
    text: 'TiAl合金是一种在汽车及航空航天等领域具有广阔应用前景的轻质高强结构材料。该类合金的本征低温脆性问题已开展了大量研究，但服役环境中氢原子引起的环境脆化仍缺少系统认识。',
    source_sections: ['项目摘要', '中文摘要', '研究背景与科学问题'],
    confidence: 0.98,
  },
  {
    label: '研究目标',
    text: '系统研究TiAl合金α2相、γ相及α2/γ界面中氢原子团簇行为，揭示氢原子团簇及固溶行为对缺陷和界面的影响，辨析TiAl合金中氢脆的微观机理。',
    source_sections: ['项目摘要', '中文摘要', '研究目标'],
    confidence: 0.98,
  },
  {
    label: '技术实施方案',
    text: '本项目拟采用第一性原理计算和必要的实验方法，结合电子结构分析，研究TiAl合金不同相及界面中的氢原子团簇、固溶行为与缺陷作用机制。',
    source_sections: ['正文', '（一）结题部分', '1．研究计划执行情况概述'],
    confidence: 0.97,
  },
  {
    label: '预期成果',
    text: '形成TiAl合金中氢原子团簇、缺陷与界面作用关系的系统认识，阐明氢脆的微观机制并建立相应的理论分析基础。',
    source_sections: ['正文', '（一）结题部分', '2．研究工作主要进展、结果和影响'],
    confidence: 0.96,
  },
  {
    label: '应用价值',
    text: '研究将为TiAl合金设计、制备和服役行为理解提供理论基础，并为汽车及航空航天领域轻质高强结构材料的安全应用提供科学支撑。',
    source_sections: ['结题摘要', '中文摘要', '科学意义与应用价值'],
    confidence: 0.97,
  },
]

const tiAlFundLocationSnippets: Record<string, string> = {
  立项依据: 'TiAl合金是一种在汽车及航空航天等领域具有广阔应用前景的轻质高强结构材料。该类合金的本征低温脆性问题已开展了大量研究，但服役环境中氢原子引起的环境脆化仍缺少系统认识。',
  研究目标: '系统研究TiAl合金α2相、γ相及α2/γ界面中氢原子团簇行为，结合电子结构分析揭示氢原子团簇及固溶行为对缺陷和界面的影响，辨析TiAl合金中氢脆的微观机理。',
  技术实施方案: '本项目拟采用第一性原理计算和必要的实验方法，系统研究TiAl合金α2相、γ相及α2/γ界面中氢原子团簇行为，结合电子结构分析揭示氢原子团簇及固溶行为对缺陷和界面的影响',
  预期成果: '辨析TiAl合金中氢脆的微观机理。研究将为TiAl合金设计、制备和服役行为理解提供理论基础。',
  应用价值: '研究将为TiAl合金设计、制备和服役行为理解提供理论基础。',
}

const tiAlFundChapterPaths: Record<string, string[]> = Object.fromEntries(
  tiAlFundMoves.map(item => [item.label, item.source_sections]),
)

function alignTiAlFundLocations(value: unknown, mode: PositionPreviewMode) {
  const result = cloneResult(value)
  const visit = (node: any) => {
    if (Array.isArray(node)) {
      node.forEach(visit)
      return
    }
    if (!node || typeof node !== 'object') return
    const isTiAlDocument = String(node.document?.title || '').startsWith('TiAl合金中氢原子团簇')
    if (isTiAlDocument && Array.isArray(node.moves)) {
      if (mode === 'file') {
        node.document.file_name = 'project1.pdf'
        node.document.file_type = 'PDF'
        node.document.page_count = 49
        node.document.parse_status = 'success'
      }
      node.moves.forEach((move: any) => {
        const snippet = tiAlFundLocationSnippets[move.label]
        const path = tiAlFundChapterPaths[move.label]
        if (mode === 'text' && snippet) {
          const index = tiAlFundProjectText.indexOf(snippet)
          if (index >= 0) move.position = { start: index + 1, end: index + snippet.length }
          delete move.source_sections
        } else if (mode === 'file' && path) {
          delete move.position
          delete move.source_position
          move.source_sections = [path.join(' > ')]
        }
      })
    }
    Object.values(node).forEach(visit)
  }
  visit(result)
  return result
}

const tiAlFundSingleResult = {
  code: 200,
  message: 'success',
  data: {
    tool: '中文基金项目语步识别',
    document: {
      title: 'TiAl合金中氢原子团簇的第一性原理计算及实验研究',
      file_name: 'project1.pdf',
      file_type: 'PDF',
      page_count: 49,
      language: 'zh',
      document_type: '中文基金项目结题/成果报告',
      parse_status: 'success',
    },
    moves: tiAlFundMoves,
    move_count: tiAlFundMoves.length,
  },
  meta: { request_id: 'req_fund_tial_demo_20260817001', elapsed_ms: 1386 },
}

const finiteElementFundMoves = [
  { label: '立项依据', text: '复杂大规模实际工程同时存在材料非线性与几何非线性，现有商业软件在自主可控、扩展接口和高阶非线性求解方面仍存在限制。', source_sections: ['结题摘要', '中文摘要', '研究背景'], confidence: 0.97 },
  { label: '研究目标', text: '研发具有自主版权的大规模通用隐式非线性有限元分析软件，形成统一的求解器、单元、本构与二次开发体系。', source_sections: ['结题摘要', '中文摘要', '研究目标'], confidence: 0.98 },
  { label: '技术实施方案', text: '采用迭代控制、数值算法与数据模型协同设计，研究线搜索、自动增量步长、共旋单元、非线性本构模型和用户单元接口。', source_sections: ['正文', '（一）结题部分', '2．主要研究内容'], confidence: 0.97 },
  { label: '预期成果', text: '形成隐式静动力求解器、非线性单元与材料模型、统一开发接口及工程算例验证体系。', source_sections: ['正文', '（一）结题部分', '3．主要研究结果'], confidence: 0.96 },
  { label: '应用价值', text: '为复杂工程结构非线性分析提供自主可控的软件工具，支撑高端工程软件国产化与实际工程应用。', source_sections: ['结题摘要', '中文摘要', '应用价值'], confidence: 0.96 },
]

const tiAlFundBatchResult = {
  code: 200,
  message: 'batch_completed',
  data: {
    batch_id: 'batch_fund_demo_20260817001', input_type: 'files', total: 2, success_count: 2, failed_count: 0,
    results: [
      { index: 1, file_name: 'project1.pdf', status: 'success', code: 200, result: tiAlFundSingleResult.data },
      {
        index: 2, file_name: 'project2.pdf', status: 'success', code: 200,
        result: {
          tool: '中文基金项目语步识别',
          document: { title: '大规模通用隐式非线性有限元分析软件研发', file_name: 'project2.pdf', file_type: 'PDF', page_count: 36, language: 'zh', document_type: '中文基金项目结题/成果报告', parse_status: 'success' },
          moves: finiteElementFundMoves,
          move_count: finiteElementFundMoves.length,
        },
      },
    ],
  },
  meta: { max_concurrency: 2, elapsed_ms: 2764 },
}

const finalOverrides: Record<string, Partial<ToolDefinition>> = {
  'zh-keyword': {
    response: generatedZhKeyword.response,
    demoTextResult: generatedZhKeyword.demoTextResult,
    demoBatchTextResult: generatedZhKeyword.demoBatchTextResult,
    demoFileResult: generatedZhKeyword.demoFileResult,
    demoBatchFileResult: generatedZhKeyword.demoBatchFileResult,
  },
  'fund-move': {
    description: '识别基金申请书、立项书或科研项目管理文件中的立项依据、研究目标、技术实施方案、预期成果和应用价值，支持单文本、批量文本、单文件和批量文件。',
    features: '章节结构识别、基金语步分类、文本位置或章节路径溯源、同类内容聚合、单文本、批量文本、单文件、批量文件',
    inputModes: fourModes,
    modeLabels: { text: '单文本', 'batch-text': '批量文本', file: '单文件', batch: '批量文件' },
    textEndpoint: '/api/v1/move/fund/zh/text',
    batchTextEndpoint: '/api/v1/move/fund/zh/texts',
    fileEndpoint: '/api/v1/move/fund/zh/file',
    batchFileEndpoint: '/api/v1/move/fund/zh/files',
    maxBatchTexts: 20,
    demoText: tiAlFundProjectText,
    demoBatchTexts: [
      { id: 'FUND_TEXT_001', project_name: '复杂制造环境设备健康管理关键技术研究', text: '本项目面向复杂制造环境下的设备健康管理需求，研究多源传感数据融合、故障机理建模与智能诊断方法，形成可解释的故障预警技术体系。' },
      { id: 'FUND_TEXT_002', project_name: '低碳园区多能协同优化与智能调度研究', text: '本项目围绕低碳园区多能协同优化问题，构建源网荷储联合调度模型，预期形成智能调度平台并开展示范应用。' },
    ],
    demoTextResult: tiAlFundSingleResult,
    demoFileResult: tiAlFundSingleResult,
    demoBatchTextResult: tiAlFundBatchResult,
    demoBatchFileResult: tiAlFundBatchResult,
    response: tiAlFundBatchResult,
  },
  'en-keyword': {
    response: enKeywordPreviewResponse,
    demoTextResult: enKeywordDemoTextResult,
    demoBatchTextResult: enKeywordDemoBatchTextResult,
    demoFileResult: enKeywordDemoFileResult,
    demoBatchFileResult: enKeywordDemoBatchFileResult,
  },
  'domain-classify': {
    features: '专业领域必选、领域匹配校验、一级二级三级分类、分类置信度计算、领域标签生成、批量文本处理、二级类别统计、三级类别统计、单文本与批量文本、单文件与批量文件',
  },
  'rq-detect': {
    inputModes: fourModes,
    textEndpoint: '/api/v1/research-question/text',
    batchTextEndpoint: '/api/v1/research-question/texts',
    fileEndpoint: '/api/v1/research-question/file',
    batchFileEndpoint: '/api/v1/research-question/files'
  },
  'citation-sentiment': {
    inputModes: fourModes,
    textEndpoint: '/api/v1/citation-sentiment/text',
    batchTextEndpoint: '/api/v1/citation-sentiment/texts',
    fileEndpoint: '/api/v1/citation-sentiment/file',
    batchFileEndpoint: '/api/v1/citation-sentiment/files',
  },
  'citation-intent': {
    inputModes: fourModes,
    textEndpoint: '/api/v1/citation-intent/text',
    batchTextEndpoint: '/api/v1/citation-intent/texts',
    fileEndpoint: '/api/v1/citation-intent/file',
    batchFileEndpoint: '/api/v1/citation-intent/files',
  },
  'definition-detect': {
    documentType: 'definition',
    inputModes: fourModes,
    textEndpoint: '/api/v1/concept-definition/text',
    batchTextEndpoint: '/api/v1/concept-definition/texts',
    fileEndpoint: '/api/v1/concept-definition/file',
    batchFileEndpoint: '/api/v1/concept-definition/files',
    response: definitionResponse,
  },
  'general-ner': {
    documentType: 'general-ner', inputModes: fourModes,
    textEndpoint: '/api/v1/ner/general/text', batchTextEndpoint: '/api/v1/ner/general/texts',
    fileEndpoint: '/api/v1/ner/general/file', batchFileEndpoint: '/api/v1/ner/general/files',
    response: generalNerPreviewResponse,
  },
  'research-ner': {
    documentType: 'research-ner', inputModes: fourModes,
    textEndpoint: '/api/v1/ner/research/text', batchTextEndpoint: '/api/v1/ner/research/texts',
    fileEndpoint: '/api/v1/ner/research/file', batchFileEndpoint: '/api/v1/ner/research/files',
    response: researchNerPreviewResponse,
  },
  'domain-ner': {
    documentType: 'domain-ner', inputModes: fourModes,
    textEndpoint: '/api/v1/ner/domain/text', batchTextEndpoint: '/api/v1/ner/domain/texts',
    fileEndpoint: '/api/v1/ner/domain/file', batchFileEndpoint: '/api/v1/ner/domain/files',
    response: domainNerPreviewResponse,
  },
  'relation-extract': {
    documentType: 'relation', inputModes: ['existing-result'],
    endpoint: '/api/v1/relation/from-ner-record',
    historyTaskEndpoint: '/api/v1/relation/from-ner-record',
    modeLabels: { 'existing-result': '命名实体识别历史记录' },
    payload: { upstream_ner_record_id: 'NER-20260816-001' },
    response: {
      code: 200,
      message: 'success',
      data: {
        upstream_ner_record_id: 'NER-20260816-001',
        original_sentence: '阿司匹林能够抑制血小板聚集。',
        dependency_parse_executed_internally: true,
        dependency_parse: [
          { sentence_id: 'SENT-018', head: '抑制', relation: '主语', dependent: '阿司匹林' },
          { sentence_id: 'SENT-018', head: '抑制', relation: '状语', dependent: '能够' },
          { sentence_id: 'SENT-018', head: '抑制', relation: '宾语', dependent: '血小板聚集' }
        ],
        dependency_paths: [
          { triple_id: 'TRIPLE_001', path: '阿司匹林 ←[主语]— 抑制 —[宾语]→ 血小板聚集' }
        ],
        relation_triples: [{ triple_id: 'TRIPLE_001', subject: '阿司匹林', relation: { code: 'INHIBITS', label: '抑制', trigger: '抑制' }, object: '血小板聚集', sentence_id: 'SENT-018', context: '阿司匹林能够抑制血小板聚集。', dependency_path: '阿司匹林 ←[主语]— 抑制 —[宾语]→ 血小板聚集', confidence: 0.96 }],
        context_fragments: [{ sentence_id: 'SENT-018', text: '阿司匹林能够抑制血小板聚集。' }],
        rdf_representation: '<http://example.org/entity/阿司匹林> <http://example.org/relation/抑制> <http://example.org/entity/血小板聚集> .'
      }
    }
  },
  'deep-cluster': {
    documentType: 'deep-cluster', inputModes: ['batch-text', 'batch'],
    description: '对用户上传的多篇科技文献文本进行标准化处理、句子级语义编码和相似度聚类，输出聚类结果类簇、类簇特征统计和主题趋势分析结果。',
    features: '文献去重清洗、句子级语义编码、语义相似度聚类、类簇特征统计、主题趋势分析',
    scenarios: '科技文献主题发现、技术路线梳理、应用场景聚合、研究热点与趋势分析',
    modeLabels: { 'batch-text': '多篇科技文献文本', batch: '批量文献文件' },
    batchTextEndpoint: '/api/v1/cluster/deep/texts', batchFileEndpoint: '/api/v1/cluster/deep/files',
    collectionEndpoint: '/api/v1/cluster/deep/collection',
    payload: demoDeepClusterPayload,
    demoBatchTextResult: (deepClusterRuntime as ToolDefinition).demoBatchTextResult,
    demoBatchFileResult: (deepClusterRuntime as ToolDefinition).demoBatchFileResult,
    demoCollectionResult: deepCollectionResult,
    params: [
      ['input_type', 'string', 'required', '输入方式：texts、files 或 collection'],
      ['documents', 'object[]', 'conditional', '批量文本；每个对象同时包含 text 和对应的文献编号、发表时间、题名、作者、来源、关键词等元数据'],
      ['files', 'file[]', 'conditional', '批量上传 PDF、DOCX 或 TXT 文件；每个文件同时提交对应文献元数据'],
      ['collection_id', 'string', 'conditional', '已有文献集合编号'],
      ['cluster_dimension', 'string', 'required', '聚类维度：technology（技术路线）或 application_scenario（应用场景）'],
      ['algorithm', 'string', 'optional', '聚类算法，默认自动选择'],
      ['cluster_count', 'integer', 'optional', '目标类簇数量，留空时自动估计'],
      ['minimum_cluster_size', 'integer', 'optional', '最小类簇规模'],
      ['similarity_metric', 'string', 'optional', '语义相似度度量方式']
    ],
    response: (deepClusterRuntime as ToolDefinition).response as Record<string, unknown>
  },
  'cluster-label': {
    documentType: 'cluster-label', inputModes: ['batch-text'],
    description: '接收深度聚类模型输出的类簇短语集合，为每个类簇生成具有概括性、代表性和区分度的简短标签。',
    features: '类簇短语清洗、词形还原、特征过滤、候选标签生成、标签长度控制、多语言输出、差异化优化',
    scenarios: '科研主题命名、文献类簇标注、主题结构展示和聚类结果解释',
    modeLabels: { 'batch-text': '类簇短语集合' },
    endpoint: '/api/v1/cluster-labels/generate', batchTextEndpoint: '/api/v1/cluster-labels/generate',
    payload: demoClusterLabelPayload,
    params: [
      ['input_type', 'string', 'required', '输入方式：texts、files 或 existing_result'],
      ['cluster_phrase_sets', 'object[]', 'conditional', '类簇代表短语集合，或由批量文本/文件在功能内部先聚类生成'],
      ['cluster_task_id', 'string', 'conditional', '数据库中已完成的深度聚类历史任务编号'],
      ['label_length_limit', 'integer', 'optional', '标签最大长度'],
      ['language_type', 'string', 'optional', '输出语言：自动、中文或英文'],
      ['distinctiveness_threshold', 'number', 'optional', '类簇间差异阈值，范围 0—1']
    ],
    demoBatchTextResult: clusterLabelBatchTextResult,
    demoBatchFileResult: clusterLabelBatchFileResult,
    demoHistoryResult: clusterLabelHistoryResult,
    response: clusterLabelBatchTextResult
  },
  'structured-review': {
    documentType: 'structured-review', inputModes: ['batch-text', 'batch', 'collection'],
    description: '对科技文献检索结果集或指定文献集进行自动化综合分析，以“研究问题—研究方法—研究进展”三层树形结构揭示研究脉络与知识骨架，并支持溯源询证。',
    features: '研究问题识别与聚类、研究方法匹配、研究进展与结论归纳、三层树形展示、趋势热点分析、溯源询证',
    scenarios: '领域文献综述编写、技术趋势分析、科研证据检索',
    modeLabels: { 'batch-text': '文献集（批量文本）', batch: '文献集（批量文件）', collection: '指定文献集' },
    batchTextEndpoint: '/api/v1/review/structured/texts', batchFileEndpoint: '/api/v1/review/structured/files',
    collectionEndpoint: '/api/v1/review/structured/collections',
    payload: demoReviewPayload,
    params: [
      ['document_set', 'object[]|file[]|resource', 'required', '科技文献检索结果集或指定文献集；批量文本中每篇文献统一使用 document_id 与 text'],
      ['topic_or_keywords', 'string|string[]', 'required', '研究主题或关键词'],
      ['document_metadata', 'object[]|resource', 'required', '与文献逐篇对应的元数据；文献编号用于关联，题名、作者、年份、来源和关键词等字段可按实际数据提供']
    ],
    demoBatchTextResult: structuredReviewBatchTextResult,
    demoBatchFileResult: structuredReviewBatchFileResult,
    demoCollectionResult: structuredReviewCollectionResult,
    response: structuredReviewBatchTextResult
  }
}

export const tools = Object.fromEntries(
  Object.entries(generatedTools as Record<string, ToolDefinition>).map(([id, tool]) => {
    const override = finalOverrides[id] || {}
    const requirement = (generatedRequirements as Record<string, { params?: ToolDefinition['params'] }>)[id]
    const baseParams = id === 'structured-review' ? override.params : requirement?.params || override.params || tool.params
    const strictContract = requirementContracts[id]
    const mergedTool: ToolDefinition = {
      ...tool,
      ...override,
      payload: {
        ...(typeof tool.payload === 'object' && tool.payload ? tool.payload : {}),
        ...(typeof override.payload === 'object' && override.payload ? override.payload : {}),
        ...(reviewerPayloadSupplements[id] || {}),
      },
      // The reviewed requirement table is the single source of truth for
      // request and response fields shown by the Vue client.
      params: strictContract?.inputs || mergeParams(baseParams, reviewerSupplementParams[id]),
      requirementOutputs: strictContract?.outputs || [],
      requirementKey: id,
    }

    const consistentApiPayload = demoApiPayloadForTool(id)
    if (consistentApiPayload) mergedTool.payload = consistentApiPayload
    const consistentDemoText = pureSingleTextByTool[id] || (demoData.singleTextByTool as Record<string, string>)[id]
    if (consistentDemoText) mergedTool.demoText = consistentDemoText
    const consistentBatchTexts = pureBatchTextByTool[id] || (demoData.batchTextByTool as Record<string, readonly any[]>)[id]
    if (Array.isArray(consistentBatchTexts) && consistentBatchTexts.length) {
      mergedTool.demoBatchTexts = consistentBatchTexts.map((item: any, index) => ({
        id: `DEMO_${index + 1}`,
        project_name: typeof item === 'string' ? '' : item.project_name || item.projectName || '',
        title: typeof item === 'string' ? '' : item.title || '',
        text: typeof item === 'string' ? item : item.text || '',
      }))
    }

    const previewResultKeys = ['response', 'demoTextResult', 'demoBatchTextResult', 'demoFileResult', 'demoBatchFileResult', 'apiFileResult', 'apiBatchFileResult', 'demoHistoryResult', 'demoCollectionResult']

    for (const key of previewResultKeys) {
      const preview = mergedTool[key]
      if (preview && typeof preview === 'object') mergedTool[key] = alignDemoSemanticResponseForMode(id, preview, positionModeForResult(key, mergedTool))
    }

    if (id === 'zh-classify' || id === 'en-classify') {
      for (const key of previewResultKeys) {
        const preview = mergedTool[key]
        if (preview && typeof preview === 'object') {
          mergedTool[key] = enrichLiteratureClassificationCandidates(preview, id === 'zh-classify' ? 'zh' : 'en')
        }
      }
    }

    if (id === 'domain-classify') {
      for (const key of previewResultKeys) {
        const preview = mergedTool[key]
        if (preview && typeof preview === 'object') mergedTool[key] = normalizeDomainClassificationResult(preview)
      }
    }

    if (chapterPositionToolIds.has(id)) {
      const firstMode = mergedTool.inputModes?.[0]
      if ((firstMode === 'text' || firstMode === 'batch-text') && !mergedTool.demoTextResult) {
        const textPreviewSource = mergedTool.response || mergedTool.apiFileResult || mergedTool.demoFileResult
        if (textPreviewSource && typeof textPreviewSource === 'object') {
          mergedTool.demoTextResult = enrichPositionPreview(textPreviewSource, 'text')
        }
      }
      for (const key of previewResultKeys) {
        const preview = mergedTool[key]
        if (preview && typeof preview === 'object') {
          const positionMode = positionModeForResult(key, mergedTool)
          const positioned = enrichPositionPreview(preview, positionMode)
          mergedTool[key] = id === 'fund-move' ? alignTiAlFundLocations(positioned, positionMode) : positioned
        }
      }
    }

    return [id, mergedTool]
  })
) as Record<string, ToolDefinition>

// Standalone HTML demo only: the same response schema is reused for every
// input mode, while every location-bearing field is converted at runtime.
// Text inputs use character offsets; uploaded files use structured headings.
export function demoResponseForMode(toolId: string, tool: ToolDefinition, mode: InputMode) {
  const candidates: Record<InputMode, string[]> = {
    text: ['demoTextResult', 'apiFileResult', 'response'],
    'batch-text': ['demoBatchTextResult', 'response'],
    file: ['demoFileResult', 'apiFileResult', 'response'],
    batch: ['demoBatchFileResult', 'apiBatchFileResult', 'response'],
    'existing-result': ['demoHistoryResult', 'response'],
    collection: ['demoCollectionResult', 'response'],
  }
  // The fund-move demo has deliberately different single/batch fixtures.
  // Resolve them here instead of trusting an older prototype response that may
  // still be present on the incoming tool object.
  let response: unknown = toolId === 'fund-move'
    ? (mode === 'batch-text' || mode === 'batch' ? tiAlFundBatchResult : tiAlFundSingleResult)
    : tool.response || { code: 200, message: 'success', data: {} }
  if (toolId === 'fund-move') {
    response = alignDemoSemanticResponseForMode(toolId, response, mode)
    const positionMode: PositionPreviewMode = mode === 'text' || mode === 'batch-text' ? 'text' : 'file'
    return alignTiAlFundLocations(enrichPositionPreview(response, positionMode), positionMode)
  }
  for (const key of candidates[mode]) {
    if (tool[key] && typeof tool[key] === 'object') {
      response = tool[key]
      break
    }
  }
  response = alignDemoSemanticResponseForMode(toolId, response, mode)
  if (toolId === 'zh-classify') return enrichLiteratureClassificationCandidates(response, 'zh')
  if (toolId === 'en-classify') return enrichLiteratureClassificationCandidates(response, 'en')
  if (toolId === 'domain-classify') return normalizeDomainClassificationResult(response)
  if (!chapterPositionToolIds.has(toolId)) return cloneResult(response)
  const positionMode: PositionPreviewMode = mode === 'text' || mode === 'batch-text' ? 'text' : 'file'
  const positioned = enrichPositionPreview(response, positionMode)
  return toolId === 'fund-move' ? alignTiAlFundLocations(positioned, positionMode) : positioned
}
