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
      // 与主字段模板同源（demoBatchTexts）保证数量一致——此前 title 与主字段
      // 模板各自取数导致 3 题目对 1 文本的错位示例（2026-09-16 用户反馈）
      const batch = Array.isArray((tool as any).demoBatchTexts) ? (tool as any).demoBatchTexts : []
      return batch.length
        ? batch.map((item: any, index: number) => String(item?.title || '').trim() || `第 ${index + 1} 篇文献题目`)
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
    if (mode === 'batch-text') {
      // 与 document_title 模板同源（demoBatchTexts）：条数对齐且内嵌 title——
      // 与在线测试批量提交的真实结构一致（每条 {id, title, text}）
      const batch = Array.isArray((tool as any).demoBatchTexts) ? (tool as any).demoBatchTexts : []
      return batch.length
        ? batch.map((item: any, index: number) => ({
            id: item?.id || `TEXT${String(index + 1).padStart(3, '0')}`,
            ...(String(item?.title || '').trim() ? { title: String(item.title).trim() } : {}),
            text: typeof item === 'string' ? item : String(item?.text || ''),
          }))
        : [{ id: 'TEXT001', text: String((tool as any).demoText || '待处理科技文本……') }]
    }
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
  // 过滤预声明的嵌套行（xxx[].yyy）：它们是文档说明行，不是独立载荷键——此前
  // 被当普通键塞进 payload，与父键的动态展开叠加导致参数表同参数出现 2~3 次
  // （2026-10-11 全工具清查：citation-sentiment 单文本 15 行重复）。
  const inputs = contract.inputs
    .filter(row => !row[0].includes('[]'))
    .filter(row => row[0] !== 'document_title' || mode === 'text' || mode === 'batch-text')
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
  return alignDemoPayloadWithApi(tool, mode, stripEmptyResourceDescriptors(payloadForImpl(tool, mode)))
}

/** 调用示例载荷与在线测试实际提交严格对齐（2026-10-15 用户定稿）。演示载荷是
 *  采集脚本快照，与在线测试构建逻辑平行实现、会无声漂移，统一在此收敛（调用
 *  示例与参数表同源于 payloadFor，一处收敛两处生效）：
 *  ① 剔除 input_type——后端按路由自行判定，前端在线测试不发送；
 *  ② citation 批量文本：citation_metadata 实为"每篇一组"的嵌套数组（在线测试
 *     按篇构建），旧示例是平铺多条；citation_sentence_and_context 剔除 id 键；
 *  ③ 通用工具批量文本：主字段对象数组逐条补 title（在线测试每条含 title，
 *     与 document_title 数组按序对应，fund-move 的 project_name 同理在对象内）；
 *  ④ 输入↔输出自洽（2026-10-16 用户反馈）：载荷文本与响应文本是两份独立快照
 *     会漂移（如 zh-abstract 载荷是"智慧体育"文、响应 abstract 是另一篇）——
 *     响应示例回显的 document.abstract 是权威输入，主文本字段/题目与之同步 */
function alignDemoPayloadWithApi(tool: ToolDefinition, mode: InputMode, payload: Record<string, unknown>) {
  const toolId = tool.requirementKey || ''
  const out: Record<string, unknown> = { ...payload }
  delete out.input_type
  if (mode === 'batch-text') {
    if (toolId === 'citation-sentiment' || toolId === 'citation-intent') {
      if (Array.isArray(out.citation_metadata) && out.citation_metadata.length
          && !Array.isArray((out.citation_metadata as unknown[])[0])) {
        out.citation_metadata = (out.citation_metadata as unknown[]).map(item => [item])
      }
      if (Array.isArray(out.citation_sentence_and_context)) {
        out.citation_sentence_and_context = (out.citation_sentence_and_context as Array<Record<string, unknown>>)
          .map(item => { if (item && typeof item === 'object' && 'id' in item) { const { id: _id, ...rest } = item; return rest } return item })
      }
    } else {
      const titles = Array.isArray(out.document_title) ? out.document_title as unknown[] : []
      for (const [key, value] of Object.entries(out)) {
        if (Array.isArray(value) && value.length && typeof value[0] === 'object' && value[0] !== null) {
          out[key] = value.map((item, i) =>
            item && typeof item === 'object' && !((item as Record<string, unknown>).title) && typeof titles[i] === 'string'
              ? { ...item, title: titles[i] } : item)
        }
      }
    }
  }
  syncCitationCardsWithFullText(toolId, mode, out)
  syncPayloadTextWithResponse(tool, mode, out)
  return out
}

/** citation 文本/批量文本：引用句卡片从全文重建（2026-10-16 修复）。旧演示
 *  载荷的卡片是另一份快照的句子（中文卡片配英文全文，[12] 标记全文里根本没有），
 *  而后端优先消费 citation_sentence_and_context → 响应回显的句子与全文脱节。
 *  在线测试的真实行为是"从粘贴全文自动提取引用句卡片"，示例同款重建：按句
 *  切分，含 [n] 标记的句子生成卡片（上文/下文取相邻句），载荷内部自洽。 */
function syncCitationCardsWithFullText(toolId: string, mode: InputMode, payload: Record<string, unknown>) {
  if (!toolId.startsWith('citation-') || (mode !== 'text' && mode !== 'batch-text')) return
  const fullText = payload.scientific_document_full_text
  if (typeof fullText !== 'string' || !fullText.trim()) return
  const sentences = normalizeCitationLinebreaks(filterNonCitationLines(stripReferenceSection(fullText)))
    .split(/(?<=[。！？!?])\s*|(?<=\.)\s+|\n+/).map(s => s.trim()).filter(Boolean)
  const markerOf = (sentence: string) => sentence.match(/[\[［]\s*\d+(?:\s*[-–,，]\s*\d+)*\s*[\]］]/)?.[0] || ''
  const cards: Array<Record<string, unknown>> = []
  const seen = new Set<string>()
  sentences.forEach((sentence, i) => {
    const marker = markerOf(sentence)
    if (!marker) return
    if (looksLikeNonCitationLine(sentence)) return
    const _dedupeKey = sentence.replace(/\s+/g, '')
    if (seen.has(_dedupeKey)) return
    seen.add(_dedupeKey)
    const subSpan = sentence.replace(/[\[［]\s*\d+(?:\s*[-–,，]\s*\d+)*\s*[\]］]/g, '').replace(/\s+/g, ' ').trim()
    cards.push({
      citation_sentence: sentence,
      previous_context: i > 0 ? sentences[i - 1] : '（文档开头，无上文）',
      next_context: i + 1 < sentences.length ? sentences[i + 1] : '（文档结尾，无下文）',
      citation_marker: marker,
      // 与在线测试实发字段一致（2026-10-18 手动提取口径）：整句去标记的语义片段
      citation_sub_span: subSpan,
    })
  })
  if (cards.length) payload.citation_sentence_and_context = cards
}

/** PDF 断行文本整形（2026-10-18）：双栏/换行 PDF 的纯文本有连字符断词
 *  （"in-\nto"）与行中断句——切句前先合并断词与单换行（空行=段落边界保留），
 *  否则"完整一整句"口径会把半句当整句（实测示例文本 9 卡中 5 张是半句） */
export function normalizeCitationLinebreaks(text: string): string {
  return text
    .replace(/([A-Za-z])-\s*\n\s*/g, '$1')
    .replace(/(?<!\n)\n(?!\n)/g, ' ')
}

/** 引用句提取的文本预处理（2026-10-18 用户实测反馈：参考文献条目被解析成
 *  引用句卡片，如 "[1]刘展志,曾子芮.数字化赋能…[J].运动精品,2025,44(3)."）。
 *  与后端 _extract_citations 同口径的两层确定性过滤：
 *  ① 截断参考文献/致谢/附录章节——其后的内容不产引用句；
 *  ② 参考文献条目句（[n] 开头 + [J]/[M]/[C]/[D]/[N] 类型标记或年卷期格式）与
 *     作者署名行（"张三[1] 李四[2]"式编号列表）剔除 */
export function stripReferenceSection(text: string): string {
  // ① 标题截断（宽松变体：markdown 标题/加粗/字间空格，行锚定）
  const headingRe = /^[ \t]*#{0,4}[ \t]*\**[ \t]*(?:参\s*考\s*文\s*献|R\s*e\s*f\s*e\s*r\s*e\s*n\s*c\s*e\s*s|REFERENCES|致\s*谢|A\s*c\s*k\s*n\s*o\s*w\s*l\s*e\s*d\s*g\S{0,10}|附\s*录|A\s*p\s*p\s*e\s*n\s*d\s*i\s*x)\**[ \t]*[：:．.]?[ \t]*$/m
  const m = text.match(headingRe)
  const cut = m && m.index != null ? text.slice(0, m.index) : text
  // ② 条目序列截断（2026-10-18 用户定稿架构：先去参考文献区再解析引用句）：
  // 标题被解析器吞掉/压行时靠条目形态定位——正文行几乎不以 [n] 开头，
  // 某行以 [n]/［n］ 开头且后续 4 个非空行中还有条目行 → 参考文献区起点，
  // 从该行整段截断
  const lines = cut.split('\n')
  const entryStart = /^\s*[\[［]\d+(?:[-–,，]\d+)*[\]］]/
  for (let i = 0; i < lines.length; i++) {
    if (!entryStart.test(lines[i])) continue
    let checked = 0
    let follow = 0
    for (let j = i + 1; j < lines.length && checked < 4; j++) {
      if (!lines[j].trim()) continue
      checked += 1
      if (entryStart.test(lines[j])) follow += 1
    }
    if (follow >= 1) return lines.slice(0, i).join('\n')
  }
  return cut
}

export function looksLikeNonCitationLine(sentence: string): boolean {
  // 图/表标题句（2026-10-18 用户实测：换行合并后"表 2 强度参数…[30]…"出现在
  // 句首——行级过滤只删行首，句级再兜一层）
  if (/^(表\s*\d+|Table\s*\d+|图\s*\d+|Fig\.?\s*\d+)/i.test(sentence.trim())) return true
  // 参考文献条目：[n] 开头 + 著录特征（类型标记 / 年,卷( / 年,( ）
  if (/^\s*\[\d+(?:[-–,，]\d+)*\]\s*.+(?:\[[JMCDN]\]|\d{4}\s*[,，]\s*\d+\s*\(|\d{4}\s*[,，]\s*\()/.test(sentence)) return true
  // 英文参考文献条目（2026-10-18 用户实测漏网）：无 [J]/年卷期特征的西文条目。
  // 统一"作者块"判定：[n] 开头 + 两个名字单元（各 1-5 个大写开头词，涵盖全名
  // "Jiang Xiaoxiang"、缩写 "Smith J"、多缩写 "Tang P M"）由逗号/and/& 连接。
  // 位置信号：正文引用句标记在句中/句尾，条目标记在句首——不误伤
  if (/^\s*\[\d+(?:[-–,，]\d+)*\]\s*(?:[A-ZÀ-Þ][\wÀ-ÿ.]*\s+){0,4}[A-ZÀ-Þ][\wÀ-ÿ.]*\s*(?:,\s*|\sand\s+|&\s+)(?:[A-ZÀ-Þ][\wÀ-ÿ.]*\s+){0,4}[A-ZÀ-Þ][\wÀ-ÿ.]*/.test(sentence)) return true
  // 英文条目年份收尾特征：句中以 ". 2023." / ", 2023." 等年份标点收束
  if (/^\s*\[\d+(?:[-–,，]\d+)*\]\s*.*[.,;]\s*(?:19|20)\d{2}[a-z]?\s*[.,;:]?\s*$/.test(sentence) && !/[。！？]/.test(sentence)) return true
  // 作者署名行：名字[编号组] 以逗号/分号连接、无陈述动词（后端同款判据）
  if (/^(?:[一-鿿]{2,4}|[A-ZÀ-Þ][\wÀ-ÿ]*(?:\s+[A-ZÀ-Þ][\wÀ-ÿ]*)*)\s*\[\d[^]]*\]\s*(?:[,，;；]\s*(?:[一-鿿]{2,4}|[A-ZÀ-Þ][\wÀ-ÿ]*(?:\s+[A-ZÀ-Þ][\wÀ-ÿ]*)*)\s*\[\d[^]]*\]\s*)+[,。.;；]?$/.test(sentence.trim())) return true
  return false
}

/** 切句前的行级过滤（2026-10-18 用户实测：表格标题行"表 2 所选地震动强度参数
 *  …[30]…"被当引用句）——与后端 _extract_citations 的行清理同口径：markdown
 *  表格行（含 |）、图/表标题行、mineru 图片行剔除，公式碎片行（无 CJK/字母
 *  主导内容）一并去掉 */
export function filterNonCitationLines(text: string): string {
  return text.split('\n')
    .filter(line => {
      const s = line.trim()
      if (!s) return true
      if (s.includes('|')) return false                        // markdown 表格行
      if (/^(表\s*\d+|Table\s*\d+|图\s*\d+|Fig\.?\s*\d+)/i.test(s)) return false  // 图/表标题行
      if (/^!?\[.*\]\(images\/.*\)\s*$/.test(s)) return false  // mineru 图片行
      // 公式碎片行：CJK+字母+数字之外的字符占比过高（LaTeX/符号汤）
      const meaningful = (s.match(/[一-鿿A-Za-z0-9]/g) || []).length
      if (meaningful < s.length * 0.3) return false
      return true
    })
    .join('\n')
}

/** 主文本字段探测：载荷中最长的字符串值（≥40 字，排除题目/参数类短字段） */
function demoMainTextField(payload: Record<string, unknown>): string | null {
  let mainKey: string | null = null
  let mainLen = 39
  for (const [key, value] of Object.entries(payload)) {
    if (typeof value !== 'string' || value.length <= mainLen) continue
    mainKey = key
    mainLen = value.length
  }
  return mainKey
}

const isPlainEchoText = (value: unknown): value is string =>
  typeof value === 'string' && value.trim().length >= 40 && !/^\s*[[{]/.test(value)

function syncPayloadTextWithResponse(tool: ToolDefinition, mode: InputMode, payload: Record<string, unknown>) {
  let data: any
  try { data = (demoResponseForMode(tool.requirementKey || '', tool, mode) as any)?.data } catch { return }
  if (!data || typeof data !== 'object') return
  const titleKeys = ['document_title', 'project_name']
  if (mode === 'batch-text' && Array.isArray(data.results)) {
    // 批量：逐条与 results[i].result 回显文本对齐（回显为 JSON 串的旧快照跳过）
    const abstracts = (data.results as Array<Record<string, unknown>>).map(item => {
      const result = (item as any)?.result
      return result?.document?.abstract ?? null
    })
    for (const [key, value] of Object.entries(payload)) {
      if (!Array.isArray(value) || !value.length || typeof value[0] !== 'object') continue
      payload[key] = value.map((item, i) => {
        if (!item || typeof item !== 'object') return item
        const abstract = abstracts[i]
        if (!isPlainEchoText(abstract)) return item
        const text = (item as Record<string, unknown>).text
        return typeof text === 'string' && text !== abstract ? { ...item, text: abstract } : item
      })
    }
    return
  }
  if (Array.isArray(data.results) || Array.isArray(data)) return
  const abstract = data.document?.abstract
  const echoTitle = typeof data.document_title === 'string' && data.document_title.trim()
    ? data.document_title : (typeof data.document?.title === 'string' && data.document.title.trim() ? data.document.title : null)
  if (isPlainEchoText(abstract)) {
    const mainKey = demoMainTextField(payload)
    if (mainKey && payload[mainKey] !== abstract) payload[mainKey] = abstract
  }
  if (echoTitle) {
    for (const key of titleKeys) {
      if (typeof payload[key] === 'string' && payload[key] !== echoTitle) payload[key] = echoTitle
    }
  }
}

function payloadForImpl(tool: ToolDefinition, mode: InputMode): Record<string, unknown> {
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
        // 发表时间为选填：无该字段的文献可不提供（DOC002 即省略示例）
        { document_id: 'DOC002', title: '复杂场景视觉识别方法' },
      ],
      cluster_dimension: base.cluster_dimension || 'technology',
      clustering_algorithm_type: base.clustering_algorithm_type || base.algorithm || 'auto',
      cluster_count: base.cluster_count ?? null,
      output_format: base.output_format || 'JSON',
      // 锚点资源（可选）：上传的 File 对象经此透传到 FormData；内置不写 = 无锚点
      training_samples: base.training_samples ?? null,
      manually_labeled_category_data: base.manually_labeled_category_data ?? null,
    }
    const rawDocuments = (base.scientific_document_texts || base.documents || []) as Array<Record<string, unknown>>
    const documents = rawDocuments.map((item, index) => ({
      document_id: item.document_id || item.id || `DOC${String(index + 1).padStart(3, '0')}`,
      text: item.text || '',
    }))
    const documentMetadata = base.document_metadata || rawDocuments.map((item, index) => {
      const meta: Record<string, unknown> = {
        document_id: item.document_id || item.id || `DOC${String(index + 1).padStart(3, '0')}`,
        title: item.title || '',
        authors: item.authors || [],
        source: item.source || '',
        keywords: item.keywords || [],
      }
      // 发表时间选填：仅有值时写入示例（省略而非空串，体现可选项）
      if (item.publication_date) meta.publication_date = item.publication_date
      return meta
    })
    return {
      scientific_document_texts: documents,
      document_metadata: documentMetadata,
      cluster_dimension: base.cluster_dimension || 'technology',
      clustering_algorithm_type: base.clustering_algorithm_type || base.algorithm || 'auto',
      cluster_count: base.cluster_count ?? null,
      output_format: base.output_format || 'JSON',
      training_samples: base.training_samples ?? null,
      manually_labeled_category_data: base.manually_labeled_category_data ?? null,
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
  if (mode === 'file') return stripEmptyResourceDescriptors({ ...configuration, input_type: 'file', file: '@paper.pdf' })
  if (mode === 'batch') return stripEmptyResourceDescriptors({ ...configuration, input_type: 'files', files: ['@paper_01.pdf', '@paper_02.docx'] })
  if (mode === 'existing-result') return stripEmptyResourceDescriptors({ ...configuration, input_type: 'existing_result', cluster_task_id: clusterTaskOptions[0]?.id || 'DCL-20260815-001', label_length_limit: 12, language_type: 'auto', distinctiveness_threshold: 0.75 })
  return stripEmptyResourceDescriptors({ ...configuration, input_type: 'collection', collection_id: documentCollectionOptions[0]?.id || 'COLL-202608-VLM-01' })
}

/**
 * 剔除空的资源字段占位（资源描述符空壳 {}、{source:'database'} 无 resource_id、
 * 以及空字符串的 X.file 展开键）。
 * 2026-09-06 资源模式改为「内置（不提交字段）/用户上传」后，默认调用示例与
 * 在线测试内置模式一致：不带资源字段——带空描述符会被后端校验拒绝
 * （实测 42201「未选择数据库资源」）。用户上传资源的调用另行通过 multipart 演示。
 */
const RESOURCE_FIELD_NAMES = new Set([
  'clc_labeled_data', 'classification_standard_mapping_table', 'domain_terminology_library',
  'manually_labeled_training_data', 'manually_labeled_data', 'domain_classification_rules',
  'preprocessed_training_set', 'general_domain_annotated_corpus', 'multi_domain_scientific_corpus',
  'ontology_classification_system', 'domain_labeled_training_data',
  'training_samples', 'manually_labeled_category_data',
  'domain_terminology_dictionary',
])
// 元数据键直通（2026-09-15）：部分工具的 params 模板未登记 document_title（如
// NER 系只列 text/file），按模板过滤会把题目键丢弃——弹窗文献列落"当前结果"
const METADATA_FIELD_NAMES = new Set(['document_title', 'project_name'])
// citation 文件模式的引用句卡片直通（2026-10-18 修复）：file 模式文档模板无
// citation_sentence_and_context 键，按模板过滤会把自动提取的卡片静默丢掉
// （实测卡片 5 张、请求不带卡片走后端自动抽取）——在线测试实发字段须直通
const CITATION_CARD_FIELD_NAMES = new Set(['citation_sentence_and_context', 'citation_contexts_by_file', 'citation_metadata_by_file'])
function stripEmptyResourceDescriptors(payload: Record<string, unknown>): Record<string, unknown> {
  const out: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(payload)) {
    if (/\.file$/.test(key) && (value === '' || value === null || value === undefined)) continue
    if (RESOURCE_FIELD_NAMES.has(key)) {
      if (value === null || value === undefined) continue
      if (typeof value === 'object' && !Array.isArray(value)) {
        const record = value as Record<string, unknown>
        const hasUpload = record.source === 'upload' && (record.file || record.file_name || record.storage_uri)
        const hasDatabaseId = record.source === 'database' && record.resource_id
        if (!hasUpload && !hasDatabaseId) continue // {} / {source:'database'} 等空壳：内置=不提交
      }
    }
    out[key] = value
  }
  return out
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
  // 资源字段（2026-09-14 修复）直通：模板按"内置=不提交"剥掉了资源键，
  // 若按模板过滤会把用户上传的资源 File 一并丢弃——请求静默退回内置资源
  return Object.fromEntries(Object.keys(values).flatMap(key =>
    key in template || RESOURCE_FIELD_NAMES.has(key) || METADATA_FIELD_NAMES.has(key)
      || CITATION_CARD_FIELD_NAMES.has(key)
      ? [[key, values[key]]] : [],
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
    if (value[0] instanceof File) return 'file[]'
    if (typeof value[0] === 'object') return 'object[]'
    // 元素是 @文件名 占位（批量文件模式的演示载荷）→ file[]，此前误判 string[]
    // （2026-10-11 测试反馈：批量文件参数表显示 chinese_scientific_abstract string[]）
    if (typeof value[0] === 'string') return value[0].startsWith('@') ? 'file[]' : 'string[]'
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
    if (['doi', 'title', 'authors', 'institutions', 'venue', 'work_name', 'publication_year', 'keywords', 'publication_date'].includes(key)) childStatus = 'optional'
    if (key === 'title' && ['deep-cluster', 'structured-review'].includes(toolId)) childStatus = 'required' // 题名在这两个工具为必填
    if (key === 'source') childStatus = 'optional'
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
/**
 * 必填/选填状态与在线测试请求参数表单对齐（2026-09-11 用户定稿：
 * API/SDK 示例的必填选填 = 表单的红星校验，不再按后端 API 层宽松度标注）：
 * - document_title/project_name 表单红星+提交校验 → required
 * - deep-cluster 批量输入与逐篇元数据必填（文本/文件两模式同）
 * - cluster-label 短语集与任务编号二选一（conditional）
 * - structured-review 文献集必填；批量文本模式元数据逐篇必填
 * - citation 文件/批量模式的上传文件必填
 */
const PARAM_STATUS_OVERRIDES: Record<string, Record<string, string>> = {
  'zh-abstract-move': { document_title: 'required' },
  'en-abstract-move': { document_title: 'required' },
  'fund-move': { project_name: 'required' },
  'zh-classify': { document_title: 'required' },
  'en-classify': { document_title: 'required' },
  'domain-classify': { document_title: 'required' },
  'zh-keyword': { document_title: 'required' },
  'en-keyword': { document_title: 'required' },
  'rq-detect': { document_title: 'required' },
  'citation-sentiment': { document_title: 'required' },
  'citation-intent': { document_title: 'required' },
  'cluster-label': { cluster_task_id: 'conditional' },
}

/** 按模式区分的状态：元数据在批量文本模式逐篇必填，文件/文献集模式为可选补充 */
const MODE_PARAM_STATUS: Record<string, Record<string, Record<string, string>>> = {
  'deep-cluster': {
    'batch-text': { scientific_document_texts: 'required', document_metadata: 'required' },
    batch: { scientific_document_texts: 'required', document_metadata: 'required' },
  },
  'structured-review': {
    'batch-text': { document_set: 'required', document_metadata: 'required' },
    batch: { document_set: 'required', document_metadata: 'conditional' },
    collection: { document_set: 'required', document_metadata: 'conditional' },
  },
}

/** 各工具上传资源字段（内置模式不提交；示例载荷已剔除空占位，参数表仍需展示） */
const OPTIONAL_RESOURCE_PARAMS: Record<string, Array<[string, string] | [string, string, string]>> = {
  'zh-classify': [['clc_labeled_data', '中图分类标注数据（.json）']],
  'en-classify': [
    ['clc_labeled_data', '必填；用户可手动上传。中图分类标准（.json：中图分类号 + 类目名称）', 'required'],
    ['classification_standard_mapping_table', '必填；用户可手动上传。映射规则（.json：英文术语 + 中文术语）', 'required'],
  ],
  'domain-classify': [['domain_classification_rules', '领域分类规则（.json）'], ['manually_labeled_training_data', '人工标注训练数据（.json）']],
  'en-keyword': [['domain_terminology_library', '领域术语库（.json）'], ['classification_standard_mapping_table', '分类标准映射表（.json）']],
  'citation-intent': [['preprocessed_training_set', '引用预处理训练集（.json）']],
  'general-ner': [['general_domain_annotated_corpus', '通用领域标注语料（.json）']],
  'research-ner': [['multi_domain_scientific_corpus', '多领域科研语料（.json）'], ['manually_labeled_data', '科研实体标准词表（.json）']],
  'domain-ner': [['ontology_classification_system', '专业领域本体（.json）'], ['domain_labeled_training_data', '领域标注训练数据（.json）']],
  'deep-cluster': [['training_samples', '训练样本锚点（.json：编号+文本+题名）'], ['manually_labeled_category_data', '人工标注类目标签锚点（.json：编号+人工标注类目标签）']],
}

export function requestParameterRowsFor(tool: ToolDefinition, mode: InputMode) {
  const payload = payloadFor(tool, mode)
  const toolId = tool.requirementKey || ''
  const declared = new Map((tool.params || []).map(row => [row[0], row]))
  const overrides = { ...(PARAM_STATUS_OVERRIDES[toolId] || {}), ...((MODE_PARAM_STATUS[toolId] || {})[mode] || {}) }
  const rows = Object.entries(payload).flatMap(([key, value]) => {
    const declared_row = declared.get(key) || [key, parameterValueType(value), 'optional', key]
    // 联合类型按当前模式的实际载荷收窄:文本模式只显示 string,批量显示 string[],
    // 文件模式显示 file——各模式各写各的,不把其他模式的类型混进来
    const actualType = parameterValueType(value)
    let top = declared_row
    if (declared_row[1] && declared_row[1].includes('|') && actualType && !actualType.includes('|')) {
      // 文件模式描述同步收窄（2026-10-11 用户反馈）：单/批量文件上传的是文献
      // 文件本体（摘要/文本由系统自动提取），说明不应再写"摘要/文本"——
      // "中文科技文献摘要"应显示为"中文科技文献文件（上传后自动解析）"
      let fileDesc = declared_row[3]
      if (actualType === 'file' || actualType === 'file[]') {
        // 去掉描述中的"摘要/文本"与尾部"文件"再补文件说明，避免"摘要(含…)文件"
        // 或"管理文件文件"这类拼接瑕疵
        const base = declared_row[3].replace(/(摘要|文本|全文文本)/, '').replace(/文件$/, '').trim()
        fileDesc = `${base}文件（上传 PDF/DOCX/TXT）`
      }
      top = [declared_row[0], actualType, declared_row[2], fileDesc]
    }
    if (overrides[key]) top = [top[0], top[1], overrides[key], top[3]]
    return [top, ...nestedParameterRows(value, key, overrides[key] || top[2], toolId)]
  }) as Array<[string, string, string, string]>
  // citation 文件/批量模式：上传文件本身必填（载荷里是占位路径，声明行常标 optional）
  if (toolId.startsWith('citation-') && (mode === 'file' || mode === 'batch')) {
    const field = mode === 'file' ? 'file' : 'files'
    const row = rows.find(item => item[0] === field)
    if (row) row[2] = 'required'
  }
  // 上传资源行补回：默认示例按内置模式不带资源字段，但参数表必须让开发者知道可传
  for (const entry of (OPTIONAL_RESOURCE_PARAMS[toolId] || [])) {
    const [field, desc, status] = entry as [string, string, string?]
    if (!rows.some(item => item[0] === field)) {
      rows.push([field, 'file (.json)', status || 'optional', status === 'required'
        ? desc
        : `可选上传资源：${desc}`])
    }
  }
  return rows
}

export function responseFor(tool: ToolDefinition, mode: InputMode) {
  // 调用文档与在线测试/可视化弹窗必须使用同一份分输入方式响应。
  // 这里不再单独选择旧的 API fixture，避免文本位置、文件章节、
  // 批量条数和数据库记录与弹窗不一致。
  const demo = demoResponseForMode(tool.requirementKey || '', tool, mode)
  return cleanExampleText(alignDemoExampleWithApi(tool, mode, filterDemoByWhitelist(tool.requirementKey || '', demo)))
}

/** 演示响应与真实 API 输出严格对齐（2026-10-15 用户定稿：开发者按文档调用
 *  必须得到与在线测试一致的结果）。生成文件（prototype.generated.js 等）由
 *  采集脚本再生，漂移在这里收敛而不是改生成物：
 *  ① 分类三工具剔除后端已下线的候选确认系列字段（2026-09-09 移除人工确认，
 *     实际响应不再返回，演示富化遗留）；
 *  ② document.title 镜像补顶层 document_title（真实响应按白名单带该键标识
 *     当前文献，旧演示缺）；
 *  ③ en-abstract-move 语步标签统一中文五类（后端 2026-10-15 起输出
 *     背景/目的/方法/结果/结论，旧演示是英文标签） */
const DEMO_STALE_CLASSIFY_KEYS = ['candidate_classifications', 'manual_confirmation', 'confirmation_status', 'candidates']
const DEMO_EN_MOVE_LABEL_ZH: Record<string, string> = {
  Background: '背景', Objective: '目的', Methods: '方法', Results: '结果', Conclusion: '结论',
  研究背景: '背景', 研究目的: '目的', 研究方法: '方法', 研究结果: '结果', 研究结论: '结论',
}
/** 文件模式示例载荷里的上传文件名（'@path/file.pdf' 或其数组），供响应示例
 *  document_title 兜底——与后端"解析标题、文件名兜底"同口径 */
function exampleFileNames(tool: ToolDefinition, mode: InputMode): string[] {
  const names: string[] = []
  for (const value of Object.values(payloadFor(tool, mode))) {
    const pick = (v: unknown) => (typeof v === 'string' && v.startsWith('@')
      ? v.replace(/^@+/, '').split('/').pop() || null : null)
    const single = pick(value)
    if (single) { names.push(single); continue }
    if (Array.isArray(value)) {
      const list = value.map(pick).filter((x): x is string => !!x)
      if (list.length) names.push(...list)
    }
  }
  return names
}

function alignDemoExampleWithApi(tool: ToolDefinition, mode: InputMode, response: any) {
  const toolId = tool.requirementKey || ''
  if (!response || typeof response !== 'object' || !response.data || typeof response.data !== 'object') return response
  let data: Record<string, unknown> = { ...response.data }
  if (toolId === 'zh-classify' || toolId === 'en-classify' || toolId === 'domain-classify') {
    for (const key of DEMO_STALE_CLASSIFY_KEYS) delete data[key]
  }
  const allowed = (vizWhitelist as Record<string, string[]>)[toolId] || []
  if (Array.isArray(data.results)) {
    // 批量（批量文本/批量文件）：真实成功响应是 batch_id 信封（batch_id/input_
    // type/total/success_count/failed_count/error_summary + results[]，元素含
    // index/status=succeeded/code/record_id/result）。旧演示只有 results——补齐
    // 信封键；每条 result 内的 document_title 按单篇同口径镜像（信封顶层无题目）
    const payload = payloadFor(tool, mode) as Record<string, unknown>
    const titles = Array.isArray(payload.document_title) ? payload.document_title as unknown[] : []
    const fileNames = exampleFileNames(tool, mode)
    const items = data.results as Array<Record<string, unknown>>
    data.results = items.map((item, i) => {
      if (!item || typeof item !== 'object' || !item.result || typeof item.result !== 'object') return item
      const result = { ...(item.result as Record<string, unknown>) }
      if (allowed.includes('document_title') && result.document_title == null) {
        const title = (result.document as Record<string, unknown> | undefined)?.title
          || (typeof titles[i] === 'string' ? titles[i] : null)
          || fileNames[i]
        if (typeof title === 'string' && title.trim()) result.document_title = title
      }
      return { ...item, result }
    })
    const env: Record<string, unknown> = {
      batch_id: data.batch_id || 'tsk_c25d1f30a9b14d2f9e91ac64ac0d8f7f',
      input_type: mode === 'batch' ? 'files' : 'texts',
      total: typeof data.total === 'number' ? data.total : items.length,
      success_count: typeof data.success_count === 'number' ? data.success_count : items.length,
      failed_count: typeof data.failed_count === 'number' ? data.failed_count : 0,
      error_summary: data.error_summary ?? null,
    }
    // 旧演示可能残留的任务/进度形状键（成功同步响应不带）
    for (const stale of ['task_id', 'tool_id', 'status', 'progress', 'code', 'message']) delete data[stale]
    data = { ...env, results: data.results }
  } else if (allowed.includes('document_title') && data.document_title == null) {
    // 单篇：title 回退链与真实响应同语义——请求带什么 document_title 响应就
    // 标识什么；文件模式下后端用解析标题（文件名兜底），示例取调用示例文件名
    const title = (data.document as Record<string, unknown> | undefined)?.title
      || (payloadFor(tool, mode) as Record<string, unknown>).document_title
      || exampleFileNames(tool, mode)[0]
    if (typeof title === 'string' && title.trim()) data.document_title = title
  }
  if (toolId === 'domain-classify' && data.document == null && typeof data.document_title === 'string' && data.document_title.trim()) {
    // 反向镜像（仅 domain-classify：其真实响应带 document.title，旧演示缺；
    // zh/en-classify 实际响应无 document，不补）
    data.document = { title: data.document_title }
  }
  if (toolId === 'en-abstract-move' && Array.isArray(data.moves)) {
    data.moves = (data.moves as Array<Record<string, unknown>>).map(move =>
      move && typeof move === 'object' && typeof move.label === 'string' && move.label in DEMO_EN_MOVE_LABEL_ZH
        ? { ...move, label: DEMO_EN_MOVE_LABEL_ZH[move.label] } : move)
    if (data.move_statistics && typeof data.move_statistics === 'object') {
      data.move_statistics = Object.fromEntries(Object.entries(data.move_statistics as Record<string, unknown>)
        .map(([key, value]) => [DEMO_EN_MOVE_LABEL_ZH[key] || key, value]))
    }
  }
  return { ...response, data }
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

function cleanExampleText(obj: unknown): unknown {
  if (typeof obj === 'string') {
    return obj.replace(/[\n\r\t]+/g, ' ').replace(/\s{2,}/g, ' ').trim()
  }
  if (Array.isArray(obj)) return obj.map(cleanExampleText)
  if (obj && typeof obj === 'object') {
    const out: Record<string, unknown> = {}
    for (const [k, v] of Object.entries(obj)) out[k] = cleanExampleText(v)
    return out
  }
  return obj
}

export function buildCallCode(tool: ToolDefinition, mode: InputMode, callType: CallType) {
  const endpoint = endpointFor(tool, mode)
  const payload = cleanExampleText(payloadFor(tool, mode)) as Record<string, unknown>
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

export const pretty = (value: unknown) => JSON.stringify(value, null, 2)
