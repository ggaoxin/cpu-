import { resultPositionHeading, resultPositionLabel, fundMoveSourceGroups, buildSourceTree } from './chapterPositions.js'
import katex from 'katex'
import 'katex/dist/katex.min.css'

const array = value => Array.isArray(value) ? value : []
const object = value => value && typeof value === 'object' && !Array.isArray(value) ? value : {}
const dataOf = response => object(response?.data ?? response)
const valueOf = (item, keys, fallback = '—') => {
  for (const key of keys) {
    const value = item?.[key]
    if (value !== undefined && value !== null && value !== '') return value
  }
  return fallback
}
const escapeHtml = value => String(value ?? '').replace(/[&<>'"]/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[char]))

// 语步原文常含 MinerU 解析出的 LaTeX 公式（行内 $...$、块级 $$...$$，如 $^{+}$、\frac{a}{b}），
// 用 KaTeX 渲染成真正的数学公式排版（像 PDF 里那样），非公式部分仍 HTML 转义。
// 渲染失败（非有效 LaTeX，如误匹配的金额 $5）回退为原文转义，避免裸露源码或红色错误框。
export const renderTextWithMath = value => {
  const text = String(value ?? '')
  if (!text) return ''
  const segments = []
  const re = /\$\$([\s\S]+?)\$\$|\$([^$\n]+?)\$/g
  let last = 0
  let m
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) segments.push(['text', text.slice(last, m.index)])
    segments.push(m[1] !== undefined ? ['display', m[1]] : ['inline', m[2]])
    last = re.lastIndex
  }
  if (last < text.length) segments.push(['text', text.slice(last)])
  return segments.map(([type, src]) => {
    if (type === 'text') return escapeHtml(src)
    try {
      return katex.renderToString(src, { throwOnError: true, displayMode: type === 'display', output: 'html' })
    } catch {
      return escapeHtml(type === 'display' ? `$$${src}$$` : `$${src}$`)
    }
  }).join('')
}
const number = (value, fallback = 0) => Number.isFinite(Number(value)) ? Number(value) : fallback
const fixed = (value, digits = 2) => number(value).toFixed(digits)
const confidence = value => value === undefined || value === null || value === '' ? '—' : fixed(value)
const join = (value, separator = '、') => array(value).map(item => typeof item === 'object' ? valueOf(item, ['label', 'name', 'text', 'term'], '') : item).filter(Boolean).join(separator) || '—'
const average = values => {
  const usable = values.map(Number).filter(Number.isFinite)
  return usable.length ? usable.reduce((sum, item) => sum + item, 0) / usable.length : 0
}

function mergedRecordCell(rows, index, record, label, recordKey = 'record') {
  if (index > 0 && rows[index - 1]?.[recordKey] === record) return ''
  let rowspan = 1
  while (rows[index + rowspan]?.[recordKey] === record) rowspan += 1
  return `<td class="viz-merged-source-cell" rowspan="${rowspan}">${renderTextWithMath(label)}</td>`
}

function unwrapResult(item) {
  const candidate = item?.result ?? item?.data ?? item
  return object(candidate?.data ?? candidate)
}

function recordsOf(response) {
  const data = dataOf(response)
  if (Array.isArray(data.results)) {
    return data.results.map((item, index) => {
      const payload = unwrapResult(item)
      const fileName = item?.file_name
      return {
        index,
        record_id: item?.record_id,
        status: item?.status || 'success',
        file_name: fileName,
        name: fileName || payload?.document_title || payload?.document?.title || payload?.project_name || item?.document_title || item?.input_id || `第 ${index + 1} 项`,
        payload,
      }
    })
  }
  // 单文件响应 data 只含 record.result（无 file_name）；后端 _vue_public_response 单文件分支
  // 已把 file_name 放进 meta，故优先从 meta 取（与 record_id 同源）。
  const singleFileName = response?.meta?.file_name || data?.input?.file_name || data?.file_name
  return [{ index: 0, record_id: response?.meta?.record_id || data?.record_id, status: 'success', file_name: singleFileName, name: singleFileName || data?.document_title || data?.document?.title || data?.project_name || '当前结果', payload: data }]
}

const summaryCards = (items, gridClass, cardClass = 'distribution-summary-item', valueClass = 'distribution-summary-value', labelClass = 'distribution-summary-label') => `
  <div class="${gridClass}">${items.map(([label, value]) => `<div class="${cardClass}"><div class="${valueClass}">${escapeHtml(value)}</div><div class="${labelClass}">${escapeHtml(label)}</div></div>`).join('')}</div>`

function positionLabel(item) {
  return resultPositionLabel(item)
}

// fund-move 来源树形展示：后端 _summarize_sources_via_llm 已清理 LaTeX/归并/按文档序排列，
// 前端 buildSourceTree 把完整路径建前缀树——公共前缀节点只写一次，不同分支并列挂下，
// 避免同前缀反复重写；单链合并（父 › 子 › 孙 一行），分叉处嵌套。单文件与批量均走 renderFundMove。
function renderFundMoveSource(item) {
  const tree = buildSourceTree(item.source_sections)
  if (!tree.children.size) return '—'
  return renderSourceTree(tree)
}

// 前缀树渲染：单链合并（父 > 子 > 孙 一行），分叉处嵌套 ul，公共前缀节点只写一次
function renderSourceTree(node) {
  const children = [...node.children.entries()]
  if (!children.length) return ''
  const items = children.map(([seg, child]) => {
    // 合并单链：只有一个子节点且当前非终点，把后续段拼成 父 > 子 > 孙
    let chain = seg
    let cur = child
    while (cur.children.size === 1 && !cur.leaf) {
      const [nextSeg, nextChild] = [...cur.children.entries()][0]
      chain += ' > ' + nextSeg
      cur = nextChild
    }
    const sub = cur.children.size ? renderSourceTree(cur) : ''
    return `<li><span class="fund-move-src-seg">${renderSourcePath(chain)}</span>${sub}</li>`
  }).join('')
  return `<ul class="fund-move-src-tree">${items}</ul>`
}

// 路径分层可视化：把 "父 > 子 > 孙" 的 > 转成淡色 › 分隔符，层级一眼可辨
function renderSourcePath(path) {
  return escapeHtml(path).replace(/&gt;/g, '<span class="fund-move-src-sep"> › </span>')
}

function renderFundMove(response) {
  const records = recordsOf(response)
  const rows = records.flatMap(record => array(record.payload.moves).map(move => ({ ...move, record })))
  const sourceHeading = resultPositionHeading(rows)
  // 统计有来源章节的语步数（fundMoveSourceGroups 非空即该语步有可溯源来源）。
  // 单文件/批量文件共用 renderFundMove，统一按分层结构渲染来源章节。
  const locations = rows.filter(item => fundMoveSourceGroups(item.source_sections).length).length
  const present = new Set(rows.map(item => item.label).filter(Boolean)).size
  const failed = records.filter(item => !['success', 'succeeded'].includes(item.status)).length
  const projectNameLabel = record => record.file_name
    || record.payload?.project_name
    || record.payload?.document?.project_name
    || record.payload?.document?.title
    || '未识别项目名称'
  const resultRows = records.flatMap(record => {
    const moves = array(record.payload.moves)
    return moves.map((item, index) => `<tr class="${index === 0 ? 'fund-move-project-start-v663 ' : ''}fund-move-project-${record.index % 2 === 0 ? 'odd' : 'even'}-v663">${index === 0 ? `<td class="fund-move-project-name-v663" rowspan="${moves.length}">${escapeHtml(projectNameLabel(record))}</td>` : ''}<td><span class="fund-move-label-badge-v663">${escapeHtml(item.label || '—')}</span></td><td class="fund-move-src-cell-v663">${renderFundMoveSource(item)}</td><td>${renderTextWithMath(item.text || item.sentence || '—')}</td><td>${confidence(item.confidence)}</td></tr>`)
  }).join('')
  return `<div class="fund-move-visual-v663">
    ${summaryCards([
      ['输入数量', records.length],
      ['语步类别', `${present}/5`],
      [sourceHeading, locations],
      ['平均置信度', fixed(average(rows.map(item => item.confidence)))],
    ], 'fund-move-summary-grid-v663', 'fund-move-summary-item-v663', 'fund-move-summary-value-v663', 'fund-move-summary-label-v663')}
    <div class="fund-move-visual-card-v663"><div class="fund-move-visual-title-v663">项目语步溯源明细</div><div class="fund-move-result-table-wrap-v663"><table class="fund-move-result-table-v663"><colgroup><col style="width:21%"><col style="width:13%"><col style="width:23%"><col style="width:33%"><col style="width:10%"></colgroup><thead><tr><th>项目名称</th><th>语步类别</th><th>${sourceHeading}</th><th>语步识别结果</th><th>置信度</th></tr></thead><tbody>${resultRows || '<tr><td colspan="5">当前响应未包含有效项目语步。</td></tr>'}</tbody></table></div></div>
    ${failed ? `<div class="fund-move-batch-failure-note-v663">批量任务中有 ${failed} 条输入处理失败，表格仅展示成功结果。</div>` : ''}
  </div>`
}

// 中英文摘要语步识别可视化：复用 fund-move 的语步表格样式（moves 结构兼容），
// 位置列改为句子序号 sentence_indices（摘要无章节路径），题名取 document.title。
function renderAbstractMove(response, english = false) {
  const records = recordsOf(response)
  const rows = records.flatMap(record => array(record.payload.moves).map(move => ({ ...move, record })))
  const present = new Set(rows.map(item => item.label).filter(Boolean)).size
  // 后端 moves 不含 sentence_indices（字段为 move_code/move_name/label/text/confidence），
  // 摘要总句数取 data 顶层 sentence_count（后端统计字段），而非对 moves 的 indices 求和（恒为 0）。
  const sentenceTotal = records.reduce((sum, record) => sum + number(record.payload?.sentence_count), 0)
  const failed = records.filter(item => !['success', 'succeeded'].includes(item.status)).length
  const documentLabel = record => {
    const payload = record.payload
    return record.file_name || payload?.document?.title || payload?.document_title
      || (payload?.document?.abstract ? payload.document.abstract.slice(0, 24) + '…' : '')
      || '当前摘要'
  }
  const charRange = (item, record) => {
    const abstract = record.payload?.document?.abstract || record.payload?.abstract || ''
    const text = item.text || item.sentence || ''
    if (abstract && text) {
      // 1. 精确匹配
      let start = abstract.indexOf(text)
      if (start >= 0) return `字符 ${start}–${start + text.length}`
      // 2. 忽略空白差异匹配（GLM 切分/输出可能增减空格、换行、全角空格）
      const normChars = []
      const mapToOriginal = []
      for (let i = 0; i < abstract.length; i++) {
        if (!/[\s　]/.test(abstract[i])) {
          normChars.push(abstract[i])
          mapToOriginal.push(i)
        }
      }
      const normAbs = normChars.join('')
      const normText = text.replace(/[\s　]/g, '')
      if (normText) {
        let nStart = normAbs.indexOf(normText)
        // 3. 去空白 + 忽略大小写（英文摘要 GLM 可能改大小写）
        if (nStart < 0) nStart = normAbs.toLowerCase().indexOf(normText.toLowerCase())
        if (nStart >= 0) {
          const startIdx = mapToOriginal[nStart]
          const lastIdx = mapToOriginal[Math.min(nStart + normText.length - 1, mapToOriginal.length - 1)]
          return `字符 ${startIdx}–${(lastIdx ?? startIdx) + 1}`
        }
      }
    }
    // 全部匹配失败：降级句子序号
    const indices = array(item.sentence_indices)
    return indices.length ? indices.join('、') : '—'
  }
  const resultRows = records.flatMap(record => {
    const moves = array(record.payload.moves)
    return moves.map((item, index) => `<tr class="${index === 0 ? 'fund-move-project-start-v663 ' : ''}fund-move-project-${record.index % 2 === 0 ? 'odd' : 'even'}-v663">${index === 0 ? `<td class="fund-move-project-name-v663" rowspan="${moves.length}">${renderTextWithMath(documentLabel(record))}</td>` : ''}<td><span class="fund-move-label-badge-v663">${escapeHtml(item.label || '—')}</span></td><td class="fund-move-src-cell-v663">${escapeHtml(charRange(item, record))}</td><td>${renderTextWithMath(item.text || item.sentence || '—')}</td><td>${confidence(item.confidence)}</td></tr>`)
  }).join('')
  return `<div class="fund-move-visual-v663">
    ${summaryCards([
      ['输入数量', records.length],
      ['语步类别', `${present}/5`],
      ['句子总数', sentenceTotal],
      ['平均置信度', fixed(average(rows.map(item => item.confidence)))],
    ], 'fund-move-summary-grid-v663', 'fund-move-summary-item-v663', 'fund-move-summary-value-v663', 'fund-move-summary-label-v663')}
    <div class="fund-move-visual-card-v663"><div class="fund-move-visual-title-v663">${english ? 'Abstract Move Recognition Details' : '摘要语步识别明细'}</div><div class="fund-move-result-table-wrap-v663"><table class="fund-move-result-table-v663"><colgroup><col style="width:21%"><col style="width:13%"><col style="width:10%"><col style="width:46%"><col style="width:10%"></colgroup><thead><tr><th>文献题名</th><th>语步类别</th><th>字符范围</th><th>语步识别结果</th><th>置信度</th></tr></thead><tbody>${resultRows || '<tr><td colspan="5">当前响应未包含有效摘要语步。</td></tr>'}</tbody></table></div></div>
    ${failed ? `<div class="fund-move-batch-failure-note-v663">批量任务中有 ${failed} 条输入处理失败，表格仅展示成功结果。</div>` : ''}
  </div>`
}

function classificationRows(response, english = false) {
  return recordsOf(response).map(record => {
    const payload = record.payload
    const sourceClassifications = array(payload.classifications).length ? payload.classifications : array(payload.multilevel_classification_results)
    const main = sourceClassifications.find(item => String(item?.role || '').toLowerCase() === 'main') || sourceClassifications[0]
    const secondary = sourceClassifications.find(item => String(item?.role || '').toLowerCase() === 'secondary') || sourceClassifications[1]
    const isInterdisciplinary = payload.is_interdisciplinary === true
    const classifications = isInterdisciplinary ? [main, secondary].filter(Boolean) : [main].filter(Boolean)
    const mainConfidence = number(main?.confidence)
    const responseCandidates = array(payload.candidate_classifications)
    const fallbackCandidates = isInterdisciplinary ? [] : sourceClassifications.slice(1)
    // 原始主组合置信度（candidate_classifications 中 rank=1 的组合）作为候选过滤基准；
    // 确认替换主分类后 candidate_classifications 不变，基准保持稳定，候选列表随之稳定、可反复切换
    const rank1Candidate = responseCandidates.find(c => number(c.rank) === 1)
    const originalPrimaryConf = rank1Candidate ? number(rank1Candidate.confidence ?? rank1Candidate.combination_confidence) : mainConfidence
    const candidates = (responseCandidates.length ? responseCandidates : fallbackCandidates).filter(candidate => {
      // rank=1 的主组合始终保留为可选项：确认其他候选后可切回原主分类
      if (number(candidate.rank) === 1) return true
      // 候选规则：置信度严格低于原始主结果且 ≥0.8（低于0.8的候选不进候选区）
      const candConf = number(candidate?.confidence ?? candidate?.combination_confidence)
      if (candConf < 0.8) return false
      if (originalPrimaryConf && candConf >= originalPrimaryConf) return false
      return true
    })
    // 下拉只列候选，不列"当前首选"——当前主/次已在主表展示，下拉重复列无意义且会误导用户确认当前主
    const optionKey = candidate => {
      const candidateMain = object(candidate?.main_classification)
      const candidateSecondary = object(candidate?.secondary_classification)
      if (Object.keys(candidateMain).length && Object.keys(candidateSecondary).length) {
        return `${valueOf(candidateMain, ['clc_code', 'code'], '')}>${valueOf(candidateSecondary, ['clc_code', 'code'], '')}`
      }
      // combo 类候选（candidate_classifications 里的组合）：用 main_code/aux_code 组合 key
      const mainCode = valueOf(candidate, ['main_code'], '')
      const auxCode = valueOf(candidate, ['aux_code'], '')
      if (mainCode && auxCode) return `${mainCode}>${auxCode}`
      return valueOf(candidate, ['clc_code', 'code', 'classification_code'], candidate?.candidate_id || '')
    }
    const currentMainCode = valueOf(main, ['clc_code', 'code'], '')
    const currentSecondaryCode = secondary ? valueOf(secondary, ['clc_code', 'code'], '') : ''
    const currentKey = currentMainCode && currentSecondaryCode ? `${currentMainCode}>${currentSecondaryCode}` : currentMainCode
    const seenOptions = new Set()
    const confirmationOptions = candidates
      .filter(candidate => {
        const key = optionKey(candidate)
        if (!key || key === currentKey || seenOptions.has(key)) return false
        seenOptions.add(key)
        return true
      })
      .sort((left, right) => number(classificationCandidateConfidence(right)) - number(classificationCandidateConfidence(left)))
    return {
      ...record,
      classifications,
      isInterdisciplinary,
      labels: array(payload.domain_labels),
      mapping: object(payload.cross_language_mapping),
      confirmation: object(payload.manual_confirmation),
      candidates,
      confirmationOptions,
    }
  })
}

// 跨语言映射单元格：英文文献分类必然经过跨语言映射（英文→CLC），故分类成功即显示"已映射"，
// 附带源术语（若有）；不再因 cross_language_mapping 字段为空而显示 "—"。
function enMappingCell(mapping, prefix, version) {
  const m = object(mapping)
  const terms = array(m.source_terms).map(t => typeof t === 'object' ? valueOf(t, ['label', 'name', 'text', 'term'], '') : t).filter(Boolean)
  const status = valueOf(m, ['status'], '已映射')
  const termsHtml = terms.length ? `${escapeHtml(terms.join('、'))}<br>` : ''
  return `<td>${termsHtml}<span class="${prefix}-mapping-badge-${version}">${escapeHtml(status)}</span></td>`
}

function classificationPath(item) {
  const raw = item?.classification_path
  // classification_path/path can both be an array or an already joined
  // "A > B > C" string. Keep the full hierarchy in either response shape.
  const fallback = item?.path
  const path = Array.isArray(raw)
    ? raw
    : typeof raw === 'string' && raw.trim()
      ? [raw]
      : Array.isArray(fallback)
        ? fallback
        : typeof fallback === 'string' && fallback.trim()
          ? [fallback]
          : []
  return path.length ? path.join(' > ') : valueOf(item, ['category_name', 'label', 'clc_code', 'code'])
}

function classificationCandidateLabel(candidate) {
  const main = object(candidate?.main_classification)
  const secondary = object(candidate?.secondary_classification)
  if (Object.keys(main).length && Object.keys(secondary).length) {
    const mainLabel = `${valueOf(main, ['clc_code', 'code'])} ${valueOf(main, ['label', 'category_name'])}`.trim()
    const secondaryLabel = `${valueOf(secondary, ['clc_code', 'code'])} ${valueOf(secondary, ['label', 'category_name'])}`.trim()
    return `主分类：${mainLabel}；次分类：${secondaryLabel}`
  }
  // 跨学科结果使用完整主次组合；非跨学科结果使用单项候选分类。
  if (candidate) {
    const code = valueOf(candidate, ['clc_code', 'code'], '')
    const label = valueOf(candidate, ['label', 'category_name'], '')
    if (code || label) return `${code} ${label}`.trim()
  }
  return classificationPath(candidate)
}

function classificationCandidateConfidence(candidate) {
  return candidate?.combination_confidence ?? candidate?.confidence
}

function renderClassification(response, english = false) {
  const records = classificationRows(response, english)
  const prefix = english ? 'en-classify' : 'zh-classify'
  const version = english ? 'v668' : 'v667'
  const rows = records.flatMap(record => record.classifications.map((item, index) => ({ ...item, record, resultIndex: index })))
  const successful = records.filter(item => ['success', 'succeeded'].includes(item.status)).length
  const categories = new Set(rows.map(item => valueOf(item, ['clc_code', 'code'], '')).filter(Boolean)).size
  const pending = records.filter(item => item.confirmation.status !== 'confirmed').length
  const responseData = dataOf(response)
  const distributionReport = english ? object(responseData.literature_distribution_analysis_report) : object(responseData.classification_statistics_table)
  let distributions = english ? array(distributionReport.by_clc_category) : array(distributionReport.rows)
  let domainDistributions = english ? array(distributionReport.by_domain_label) : []
  if (!distributions.length) {
    const counts = new Map()
    rows.forEach(item => {
      const code = valueOf(item, ['clc_code', 'code'], '未分类')
      const current = counts.get(code) || { clc_code: code, category_name: valueOf(item, ['category_name', 'label'], ''), classification_path: classificationPath(item), document_count: 0, confidences: [] }
      current.document_count += 1
      current.confidences.push(number(item.confidence))
      counts.set(code, current)
    })
    distributions = [...counts.values()].map(item => ({ ...item, document_ratio: rows.length ? item.document_count / rows.length : 0, average_confidence: average(item.confidences) }))
  }
  if (english && !domainDistributions.length) {
    const domainCounts = new Map()
    records.forEach(record => {
      record.labels.forEach(label => {
        const name = typeof label === 'object' ? valueOf(label, ['label', 'name'], '') : String(label || '')
        if (!name) return
        const current = domainCounts.get(name) || { label: name, document_count: 0, confidences: [] }
        current.document_count += 1
        if (typeof label === 'object' && label.confidence != null) current.confidences.push(number(label.confidence))
        domainCounts.set(name, current)
      })
    })
    domainDistributions = [...domainCounts.values()].map(item => ({
      ...item,
      document_percentage: records.length ? item.document_count / records.length * 100 : 0,
      average_confidence: average(item.confidences),
    }))
  }
  const actualDomainLabelCount = new Set(records.flatMap(record => record.labels.map(label => typeof label === 'object' ? valueOf(label, ['label', 'name'], '') : String(label || '')).filter(Boolean))).size
  const domainLabelCount = actualDomainLabelCount || number(distributionReport.domain_label_count, domainDistributions.length)
  const colSpan = english ? 7 : 6
  // 只把"有可确认候选"的文献放进候选区：只有一个>0.6分类（无候选可替换）的文献已在主表展示并入库，不在候选区出现空占位
  const confirmableRecords = records.filter(record => record.confirmationOptions.length > 0)
  const confirmationItems = confirmableRecords.map(record => {
    const hasOptions = record.confirmationOptions.length > 0
    const emptyText = record.isInterdisciplinary ? '暂无可确认的跨学科组合' : '暂无可确认的分类'
    const confirmText = record.isInterdisciplinary ? '确认所选组合' : '确认所选分类'
    let candidateIndex = 0
    const optionHtml = record.confirmationOptions.map((candidate, index) => {
      // 下拉只列候选，当前主分类已在主表展示、不再作为选项出现（is_current_primary 分支已废弃）
      const optionTitle = `${record.isInterdisciplinary ? '候选跨学科组合' : '候选分类'} ${++candidateIndex}`
      const candPrimary = valueOf(candidate, ['main_code', 'clc_code', 'code'], '') || (candidate.main_classification ? valueOf(candidate.main_classification, ['clc_code', 'code'], '') : '')
      const candSecondary = valueOf(candidate, ['aux_code'], '') || (candidate.secondary_classification ? valueOf(candidate.secondary_classification, ['clc_code', 'code'], '') : '')
      return `<option value="${escapeHtml(candidate.candidate_id || index)}" data-primary="${escapeHtml(candPrimary)}" data-secondary="${escapeHtml(candSecondary)}">${optionTitle} · ${escapeHtml(classificationCandidateLabel(candidate))}｜${confidence(classificationCandidateConfidence(candidate))}</option>`
    }).join('')
    // 下拉框默认显示"当前首选"（当前主/次分类）作为标识：该 option 不可选（disabled）且在下拉列表中隐藏（hidden），
    // 点开下拉只看到其他候选、不含当前首选——当前首选已是正式结果、无需再选它；确认别的候选后它会自动更新为新首选
    const recordClasses = array(record.classifications)
    const pickMain = recordClasses.find(c => ['main', 'primary'].includes(String(c?.role || '').toLowerCase())) || recordClasses[0] || {}
    const pickSecondary = recordClasses.find(c => String(c?.role || '').toLowerCase() === 'secondary') || recordClasses[1]
    const pickMainText = `${valueOf(pickMain, ['clc_code', 'code'], '')} ${valueOf(pickMain, ['label', 'category_name'], '')}`.trim()
    const pickSecondaryText = pickSecondary ? `${valueOf(pickSecondary, ['clc_code', 'code'], '')} ${valueOf(pickSecondary, ['label', 'category_name'], '')}`.trim() : ''
    const pickMainConf = number(pickMain?.confidence)
    const currentPickText = pickSecondaryText ? `当前首选 · 主：${pickMainText} ／ 次：${pickSecondaryText}｜${confidence(pickMainConf)}` : `当前首选 · ${pickMainText}｜${confidence(pickMainConf)}`
    const placeholderOption = `<option value="" disabled selected hidden>${escapeHtml(currentPickText)}</option>`
    const isConfirmed = record.confirmation.status === 'confirmed'
    const actionsHtml = isConfirmed
      ? `<span class="${prefix}-status-badge-${version}">已确认</span><button type="button" class="${prefix}-confirm-btn-${version}" data-viz-reselect="${record.index}">重新选择</button>`
      : `<button type="button" class="${prefix}-confirm-btn-${version} primary" data-viz-confirm="${record.index}" data-viz-confirm-record="${record.record_id || ''}" data-viz-confirm-label="${confirmText}" ${hasOptions ? '' : 'disabled'}>${confirmText}</button>`
    return `<div class="${prefix}-confirm-item-${version}"><div class="${prefix}-confirm-name-${version}">${renderTextWithMath(record.name)}</div><select class="${prefix}-confirm-select-${version}" data-viz-confirm-select="${record.index}" ${hasOptions ? '' : 'disabled'}>${hasOptions ? (placeholderOption + optionHtml) : `<option>${emptyText}</option>`}</select><div class="${prefix}-confirm-actions-${version}">${actionsHtml}</div></div>`
  }).join('')
  const hasInterdisciplinaryRecord = confirmableRecords.some(record => record.isInterdisciplinary)
  const hasSingleDisciplineRecord = confirmableRecords.some(record => !record.isInterdisciplinary)
  const confirmationNote = [
    hasInterdisciplinaryRecord ? '跨学科文献的下拉只列候选的“主分类＋次分类”组合，当前主/次已在结果明细展示、不再重复列入。' : '',
    hasSingleDisciplineRecord ? '非跨学科文献的下拉只列候选分类，当前主分类已在结果明细展示、不再重复列入。' : '',
    '候选仅列置信度低于原始主结果且高于0.8的分类，按置信度从高到低排列；确认某个候选后由后端同步替换结果并保存审核记录，原主分类会作为候选回到下拉、可反复切换或重新选择。',
  ].filter(Boolean).join(' ')
  return `<div class="${prefix}-visual-${version}" data-viz-confirm-root>
    ${summaryCards([['文献数量', records.length], ['成功分类', successful], ['中图类别', categories], ['跨学科文献', records.filter(item => item.isInterdisciplinary).length]], `${prefix}-summary-grid-${version}`, `${prefix}-summary-item-${version}`, `${prefix}-summary-value-${version}`, `${prefix}-summary-label-${version}`)}
    <div class="${prefix}-result-card-${version}"><div class="${prefix}-result-title-${version}">${english ? '跨语言分类结果明细' : '分类结果明细'}</div><div class="${prefix}-result-table-wrap-${version}"><table class="${prefix}-result-table-${version}"><colgroup>${english ? '<col style="width:13%"><col style="width:8%"><col style="width:10%"><col style="width:30%"><col style="width:10%"><col style="width:16%"><col style="width:13%">' : '<col style="width:14%"><col style="width:9%"><col style="width:11%"><col style="width:36%"><col style="width:11%"><col style="width:19%">'}</colgroup><thead><tr><th>${english ? '英文文献' : '文献'}</th><th>角色</th><th>分类号</th><th>分类名称与路径</th><th>置信度</th>${english ? '<th>跨语言映射</th>' : ''}<th>应用场景领域</th></tr></thead><tbody>${rows.map((item, index) => `<tr>${mergedRecordCell(rows, index, item.record, item.record.name)}<td><span class="${prefix}-role-badge-${version}">${item.role === 'secondary' || item.resultIndex > 0 ? '次分类' : '主分类'}</span></td><td><span class="${prefix}-code-${version}">${escapeHtml(valueOf(item, ['clc_code', 'code']))}</span></td><td><b>${escapeHtml(valueOf(item, ['category_name', 'label']))}</b><br><span>${escapeHtml(classificationPath(item))}</span></td><td>${confidence(item.confidence)}</td>${english ? enMappingCell(item.record.mapping, prefix, version) : ''}<td>${item.resultIndex > 0 ? '—' : (item.record.labels.map(label => `<span class="${prefix}-domain-tag-${version}">${escapeHtml(valueOf(label, ['label', 'name'], label))}</span>`).join(' ') || '未提供领域标签')}</td></tr>`).join('') || `<tr><td colspan="${colSpan}">当前响应未包含可展示的分类结果。</td></tr>`}</tbody></table></div></div>
    <div class="${prefix}-result-card-${version}"><div class="${prefix}-result-title-${version}">${english ? '文献分布分析报告' : '批量分类分布统计'}</div>${english ? `<div class="review-report-summary-strip"><span>文献总数 <b>${distributionReport.document_count ?? records.length}</b></span><span>已分类 <b>${distributionReport.classified_document_count ?? successful}</b></span><span>中图类别 <b>${distributionReport.clc_category_count ?? categories}</b></span><span>领域标签 <b>${domainLabelCount}</b></span></div>` : ''}<div class="${prefix}-result-table-wrap-${version}"><table class="${prefix}-result-table-${version}"><colgroup><col style="width:12%"><col style="width:18%"><col style="width:38%"><col style="width:10%"><col style="width:10%"><col style="width:12%"></colgroup><thead><tr><th>中图分类号</th><th>分类名称</th><th>分类路径</th><th>文献数量</th><th>文献占比</th><th>平均置信度</th></tr></thead><tbody>${distributions.map(item => `<tr><td>${escapeHtml(valueOf(item, ['clc_code', 'code', 'category']))}</td><td>${escapeHtml(valueOf(item, ['category_name', 'label']))}</td><td>${escapeHtml(Array.isArray(item.classification_path) ? item.classification_path.join(' > ') : item.classification_path || '—')}</td><td>${escapeHtml(valueOf(item, ['document_count', 'count'], 0))}</td><td>${item.document_percentage != null ? fixed(item.document_percentage, 1) : fixed(number(item.document_ratio) * 100, 1)}%</td><td>${confidence(item.average_confidence)}</td></tr>`).join('') || '<tr><td colspan="6">暂无批量分类分布数据。</td></tr>'}</tbody></table></div>${english && domainDistributions.length ? `<div class="distribution-subsection-title">应用场景领域分布</div><div class="${prefix}-result-table-wrap-${version}"><table class="${prefix}-result-table-${version}"><thead><tr><th>领域标签</th><th>文献数量</th><th>文献占比</th><th>平均置信度</th></tr></thead><tbody>${domainDistributions.map(item => `<tr><td>${escapeHtml(item.label || '—')}</td><td>${number(item.document_count)}</td><td>${fixed(item.document_percentage, 1)}%</td><td>${confidence(item.average_confidence)}</td></tr>`).join('')}</tbody></table></div>` : ''}</div>
    ${confirmationItems ? `<div class="${prefix}-result-card-${version}"><div class="${prefix}-result-title-${version}">候选分类与人工确认</div><div class="${prefix}-confirm-list-${version}">${confirmationItems}</div><div class="${prefix}-note-${version}">${confirmationNote}</div></div>` : ''}
  </div>`
}

function keywordRecords(response, english) {
  return recordsOf(response).flatMap(record => array(english ? record.payload.keywords_or_topic_phrases : record.payload.keywords).map((item, index) => ({ ...item, record, rank: item.rank || index + 1 })))
}

function renderZhKeyword(response) {
  const records = recordsOf(response)
  const rows = keywordRecords(response, false)
  const unique = new Set(rows.map(item => item.keyword)).size
  const hits = rows.filter(item => item.custom_dictionary_hit || item.adaptive_resource_match).length
  const frequencies = new Map()
  rows.forEach(item => frequencies.set(item.keyword, (frequencies.get(item.keyword) || 0) + 1))
  return `<div class="zh-keyword-visual-v670">
    ${summaryCards([['文献数量', records.length], ['关键词数量', unique], ['用户词典命中', hits], ['平均置信度', fixed(average(rows.map(item => item.confidence)))]], 'zh-keyword-summary-grid-v670', 'zh-keyword-summary-item-v670', 'zh-keyword-summary-value-v670', 'zh-keyword-summary-label-v670')}
    <div class="zh-keyword-result-card-v670"><div class="zh-keyword-result-title-v670">关键词与关键短语明细</div><div class="zh-keyword-result-table-wrap-v670"><table class="zh-keyword-result-table-v670"><thead><tr><th>文献</th><th>排序</th><th>关键词/短语</th><th>置信度</th><th>词典命中</th><th>权重变化</th></tr></thead><tbody>${rows.map((item, index) => `<tr>${mergedRecordCell(rows, index, item.record, item.record.name)}<td>${item.rank}</td><td><span class="zh-keyword-term-v670">${escapeHtml(item.keyword || item.term || '—')}</span></td><td>${confidence(item.confidence)}</td><td><span class="zh-keyword-dict-badge-v670 ${item.custom_dictionary_hit || item.adaptive_resource_match ? 'hit' : ''}">${item.custom_dictionary_hit || item.adaptive_resource_match ? '用户词典命中' : '未命中'}</span></td><td>${number(item.weight_change) > 0 ? `+${fixed(item.weight_change)}` : '0.00'}</td></tr>`).join('') || '<tr><td colspan="6">接口未返回有效关键词或关键短语。</td></tr>'}</tbody></table></div></div>
    ${records.length > 1 ? `<div class="zh-keyword-result-card-v670"><div class="zh-keyword-result-title-v670">关键词汇总</div><div class="zh-keyword-result-table-wrap-v670 zh-keyword-frequency-table-wrap-v670"><table class="zh-keyword-result-table-v670 zh-keyword-frequency-table-v670"><thead><tr><th>序号</th><th>关键词/短语</th><th>出现次数</th></tr></thead><tbody>${[...frequencies.entries()].sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0], 'zh-CN')).map(([term, count], index) => `<tr><td>${index + 1}</td><td><span class="zh-keyword-frequency-term-v670">${escapeHtml(term)}</span></td><td><strong class="zh-keyword-frequency-count-v670">${count} 次</strong></td></tr>`).join('')}</tbody></table></div></div>` : ''}
  </div>`
}

function terminologyLabel(value) {
  const source = object(value)
  if (source.type === 'external') return `外部术语库 · ${source.library_name || '未命名资源'}`
  if (source.type === 'preset') return '系统预置资源'
  return '模型候选'
}

function renderEnKeyword(response) {
  const records = recordsOf(response)
  const rows = keywordRecords(response, true)
  const mapped = rows.filter(item => Object.keys(object(item.classification_mapping)).length).length
  return `<div class="en-keyword-visual-v675">
    ${summaryCards([['文献数量', records.length], ['术语/短语', rows.length], ['已规范化', rows.filter(item => item.normalized_term).length], ['平均置信度', fixed(average(rows.map(item => item.confidence)))]], 'en-keyword-summary-grid-v675', 'en-keyword-summary-item-v675', 'en-keyword-summary-value-v675', 'en-keyword-summary-label-v675')}
    <div class="en-keyword-result-card-v675"><div class="en-keyword-result-title-v675">英文关键词、规范化形式与标签映射明细（已映射 ${mapped} 项）</div><div class="en-keyword-result-table-wrap-v675"><table class="en-keyword-result-table-v675"><colgroup><col style="width:16%"><col style="width:5%"><col style="width:16%"><col style="width:14%"><col style="width:9%"><col style="width:12%"><col style="width:28%"></colgroup><thead><tr><th>文献</th><th>排序</th><th>关键词/主题短语</th><th>规范化形式</th><th>置信度</th><th>术语资源</th><th>科研分类标签</th></tr></thead><tbody>${rows.map((item, index) => { const mapping = object(item.classification_mapping); return `<tr>${mergedRecordCell(rows, index, item.record, item.record.name)}<td>${item.rank}</td><td><span class="en-keyword-term-v675">${escapeHtml(item.term || item.keyword || '—')}</span></td><td>${escapeHtml(item.normalized_term || '—')}</td><td>${confidence(item.confidence)}</td><td>${escapeHtml(terminologyLabel(item.terminology_source))}</td><td>${Object.keys(mapping).length ? `<span class="en-keyword-clc-text-v675">${escapeHtml(mapping.code || '—')} ${escapeHtml(mapping.label || '—')}</span>` : '未映射'}</td></tr>` }).join('') || '<tr><td colspan="7">接口未返回有效英文关键词或主题短语。</td></tr>'}</tbody></table></div></div>
  </div>`
}

function renderResearchQuestions(response) {
  const data = dataOf(response)
  const records = recordsOf(response)
  const sentences = records.flatMap(record => array(record.payload.research_question_sentences ?? record.payload.question_sentences).map(item => ({ ...item, __record: record })))
  const phrases = records.flatMap(record => array(record.payload.research_question_phrases ?? record.payload.question_phrases).map(item => ({ ...item, __record: record })))
  const structured = records.flatMap(record => array(record.payload.structured_research_questions ?? record.payload.research_questions).map(item => ({ ...item, __record: record })))
  const stats = object(data.statistics ?? data.research_question_statistics ?? records[0]?.payload?.research_question_statistics)
  const input = object(data.input_summary)
  const core = structured.filter(item => /核心|main|core/i.test(String(item.role || ''))).length
  const sub = structured.filter(item => /子|sub/i.test(String(item.role || ''))).length
  const expressionBadge = (item) => {
    const raw = String(valueOf(item, ['expression_type', 'type']) || '').toLowerCase()
    if (raw.startsWith('exp')) return { cls: 'explicit', label: '显式' }
    if (raw.startsWith('imp')) return { cls: 'implicit', label: '隐式' }
    return { cls: '', label: '—' }
  }
  const questionTypeLabel = (item) => {
    const raw = String(item.question_type || '').toLowerCase()
    const map = { mechanism: '机理型', objective: '目标型', method: '方法型', validation: '验证型' }
    return map[raw] || item.question_type || '—'
  }
  const batchQuestionTypeRows = [...structured.reduce((counts, item) => {
    const type = questionTypeLabel(item)
    counts.set(type, (counts.get(type) || 0) + 1)
    return counts
  }, new Map()).entries()].map(([type, count]) => ({ type, count, ratio: structured.length ? count / structured.length : 0 }))
  const statisticRows = records.length > 1
    ? batchQuestionTypeRows
    : array(stats.expression_types).length
    ? array(stats.expression_types)
    : array(stats.question_type_distribution).length
      ? array(stats.question_type_distribution).map(item => ({ type: questionTypeLabel(item), count: item.count, ratio: number(item.percentage) / 100 }))
      : [
          { type: '显式问题句', count: sentences.filter(item => expressionBadge(item).label === '显式').length },
          { type: '隐式问题句', count: sentences.filter(item => expressionBadge(item).label === '隐式').length },
        ].map(item => ({ ...item, ratio: sentences.length ? item.count / sentences.length : 0 }))
  const batchDocumentHeader = records.length > 1 ? '<th>文献</th>' : ''
  const batchDocumentCell = (rows, index, item) => records.length > 1 ? mergedRecordCell(rows, index, item.__record, item.__record?.name || `第 ${item.__record?.index + 1} 项`, '__record') : ''
  const sentenceColumns = records.length > 1
    ? '<colgroup><col style="width:16%"><col style="width:7%"><col style="width:56%"><col style="width:11%"><col style="width:10%"></colgroup>'
    : '<colgroup><col style="width:6%"><col style="width:66%"><col style="width:12%"><col style="width:16%"></colgroup>'
  const phraseColumns = records.length > 1
    ? '<colgroup><col style="width:16%"><col style="width:7%"><col style="width:8%"><col style="width:23%"><col style="width:38%"><col style="width:8%"></colgroup>'
    : '<colgroup><col style="width:8%"><col style="width:10%"><col style="width:25%"><col style="width:47%"><col style="width:10%"></colgroup>'
  const structuredColumns = records.length > 1
    ? '<colgroup><col style="width:16%"><col style="width:7%"><col style="width:8%"><col style="width:22%"><col style="width:11%"><col style="width:10%"><col style="width:18%"><col style="width:8%"></colgroup>'
    : '<colgroup><col style="width:6%"><col style="width:11%"><col style="width:32%"><col style="width:9%"><col style="width:14%"><col style="width:20%"><col style="width:8%"></colgroup>'
  return `<div class="rq-result-root" data-viz-group>
    ${summaryCards([['分析文献', records.length > 1 ? records.length : input.document_count || records.length], ['问题句数', sentences.length], ['问题短语数', phrases.length], ['结构化问题', structured.length], ['核心问题', core], ['子问题', sub]], 'rq-summary-grid')}
    <div class="rq-tabs"><button class="rq-tab-btn active" data-viz-tab="sentences">研究问题句</button><button class="rq-tab-btn" data-viz-tab="phrases">研究问题短语</button><button class="rq-tab-btn" data-viz-tab="structured">结构化研究问题</button><button class="rq-tab-btn" data-viz-tab="statistics">统计摘要</button></div>
    <div class="rq-tab-panel" data-viz-panel="sentences"><div class="distribution-table-wrap"><table class="distribution-table rq-table rq-sentence-table ${records.length > 1 ? 'rq-batch-table' : ''}">${sentenceColumns}<thead><tr>${batchDocumentHeader}<th>编号</th><th>研究问题句</th><th>表达方式</th><th>置信度</th></tr></thead><tbody>${sentences.map((item, index) => `<tr>${batchDocumentCell(sentences, index, item)}<td>${escapeHtml(valueOf(item, ['sentence_id', 'id'], index + 1))}</td><td>${renderTextWithMath(valueOf(item, ['sentence', 'text']))}</td><td><span class="rq-expression-badge ${expressionBadge(item).cls}">${escapeHtml(expressionBadge(item).label)}</span></td><td>${confidence(item.confidence)}</td></tr>`).join('') || `<tr><td colspan="${records.length > 1 ? 5 : 4}">未识别到研究问题句。</td></tr>`}</tbody></table></div></div>
    <div class="rq-tab-panel" data-viz-panel="phrases" hidden><div class="distribution-table-wrap"><table class="distribution-table rq-table rq-phrase-table ${records.length > 1 ? 'rq-batch-table' : ''}">${phraseColumns}<thead><tr>${batchDocumentHeader}<th>编号</th><th>来源句</th><th>研究问题短语</th><th>规范化问题</th><th>置信度</th></tr></thead><tbody>${phrases.map((item, index) => `<tr>${batchDocumentCell(phrases, index, item)}<td>${escapeHtml(valueOf(item, ['phrase_id', 'id'], index + 1))}</td><td>${escapeHtml(item.sentence_id || '—')}</td><td>${renderTextWithMath(valueOf(item, ['phrase', 'text']))}</td><td>${renderTextWithMath(valueOf(item, ['normalized_question', 'question']))}</td><td>${confidence(item.confidence)}</td></tr>`).join('') || `<tr><td colspan="${records.length > 1 ? 6 : 5}">未识别到研究问题短语。</td></tr>`}</tbody></table></div></div>
    <div class="rq-tab-panel" data-viz-panel="structured" hidden><div class="distribution-table-wrap"><table class="distribution-table rq-table rq-structured-table ${records.length > 1 ? 'rq-batch-table' : ''}">${structuredColumns}<thead><tr>${batchDocumentHeader}<th>编号</th><th>主次关系</th><th>规范化研究问题</th><th>问题类型</th><th>研究对象</th><th>约束条件</th><th>置信度</th></tr></thead><tbody>${structured.map((item, index) => `<tr>${batchDocumentCell(structured, index, item)}<td>${escapeHtml(valueOf(item, ['research_question_id', 'id'], `RQ${index + 1}`))}</td><td><span class="rq-role-badge ${item.role === 'sub' ? 'rq-role-sub' : 'rq-role-main'}">${escapeHtml(item.role === 'sub' ? `子问题${item.parent_id ? '（属 ' + item.parent_id + '）' : ''}` : (item.role === 'main' ? '主问题' : '研究问题'))}</span></td><td style="${item.role === 'sub' ? 'padding-left:24px' : ''}">${renderTextWithMath(valueOf(item, ['normalized_question', 'question']))}</td><td>${escapeHtml(questionTypeLabel(item))}</td><td>${renderTextWithMath(item.research_object || '—')}</td><td>${renderTextWithMath(join(item.constraints))}</td><td>${confidence(item.confidence)}</td></tr>`).join('') || `<tr><td colspan="${records.length > 1 ? 8 : 7}">未形成结构化研究问题。</td></tr>`}</tbody></table></div></div>
    <div class="rq-tab-panel" data-viz-panel="statistics" hidden><div class="distribution-table-wrap"><table class="distribution-table"><thead><tr><th>研究问题类型</th><th>数量</th><th>占比</th></tr></thead><tbody>${statisticRows.map(item => `<tr><td>${escapeHtml(item.type)}</td><td>${number(item.count)}</td><td>${fixed(number(item.ratio) * 100, 1)}%</td></tr>`).join('')}</tbody></table></div></div>
  </div>`
}

function renderCitation(response, intent = false) {
  const records = recordsOf(response)
  const items = records.flatMap(record => {
    const values = array(intent ? record.payload.citation_intent_results : record.payload.citation_sentiment_results)
    return (values.length ? values : array(record.payload.citations)).map(item => ({ ...item, __record: record }))
  })
  const prefix = intent ? 'citation-intent' : 'citation'
  const markerText = item => {
    const ms = array(item.citation_markers || item.citation_marker)
    const t = ms.filter(Boolean).join(' ').trim()
    // 引用句文本本身常已含 [n]/作者+年份 等标记，末尾再追加会重复 → 只在句中无该标记时补
    const sent = valueOf(item, ['citation_sentence', 'sentence', 'text']) || ''
    return t && !sent.includes(t) ? ` <span style="font-size:inherit;vertical-align:baseline">${escapeHtml(t)}</span>` : ''
  }
  const counts = label => items.filter(item => valueOf(item, intent ? ['intent', 'intent_code'] : ['sentiment', 'sentiment_code'], '') === label).length
  const cards = intent
    ? [['引用句', items.length], ['背景介绍', counts('背景介绍') + counts('用于背景介绍')], ['方法引入', counts('方法引入') + counts('用于引入研究方法')], ['结果比较', counts('结果比较') + counts('用于结果比较')], ['平均置信度', fixed(average(items.map(item => item.confidence)))]]
    : [['引用句总数', items.length], ['支持', counts('支持')], ['中立', counts('中立')], ['有局限性', counts('有局限性') + counts('局限性')], ['平均置信度', fixed(average(items.map(item => item.confidence)))]]
  const tabResult = intent ? '引用意图结果' : '引用情感结果'
  return `<div class="${prefix}-result-root" data-viz-group>
    ${summaryCards(cards, `${prefix}-summary-grid`)}
    <div class="${prefix}-tabs"><button class="${prefix}-tab-btn active" data-viz-tab="result">${tabResult}</button><button class="${prefix}-tab-btn" data-viz-tab="context">上下文片段</button></div>
    <div class="${prefix}-tab-panel" data-viz-panel="result"><div class="distribution-table-wrap"><table class="distribution-table ${prefix}-results-table"><colgroup><col style="width:18%"><col style="width:45%"><col style="width:14%"><col style="width:23%"></colgroup><thead><tr><th class="citation-doc-cell">文献</th><th class="citation-sentence-cell">引用句</th><th class="citation-label-cell">${intent ? '引用意图' : '情感'}</th><th class="citation-confidence-cell">置信度</th></tr></thead><tbody>${items.map((item, index) => `<tr>${mergedRecordCell(items, index, item.__record, item.__record?.name || valueOf(item, ['file_name'], `第 ${index + 1} 条`), '__record')}<td class="citation-sentence-cell">${renderTextWithMath(valueOf(item, ['citation_sentence', 'sentence', 'text']))}${markerText(item)}</td><td class="citation-label-cell"><span class="${prefix}-label-badge">${escapeHtml(valueOf(item, intent ? ['intent', 'intent_code'] : ['sentiment', 'sentiment_code']))}</span></td><td class="citation-confidence-cell">${confidence(item.confidence)}</td></tr>`).join('') || '<tr><td colspan="4">未返回引用识别结果。</td></tr>'}</tbody></table></div></div>
    <div class="${prefix}-tab-panel" data-viz-panel="context" hidden><div class="${prefix}-context-list">${items.map((item, index) => { const ctx = object(item.context); return`<article class="${prefix}-context-card"><h4>${escapeHtml(valueOf(item, ['citation_id'], `引用 ${index + 1}`))} · ${escapeHtml(valueOf(item, intent ? ['intent'] : ['sentiment']))}</h4><dl><dt>前文</dt><dd>${renderTextWithMath(valueOf(ctx, ['previous_sentence', 'before']))}</dd><dt>引用句</dt><dd class="current">${renderTextWithMath(valueOf(ctx, ['current_sentence'], item.citation_sentence || '—'))}</dd><dt>后文</dt><dd>${renderTextWithMath(valueOf(ctx, ['next_sentence', 'after']))}</dd></dl></article>` }).join('') || `<div class="${prefix}-context-empty">暂无上下文片段。</div>`}</div></div>
  </div>`
}

function renderDefinitions(response) {
  const data = dataOf(response)
  const records = recordsOf(response)
  const definitions = records.flatMap(record => array(record.payload.definitions ?? record.payload.definition_results).map(item => ({ ...item, __record: record })))
  const mappings = records.flatMap(record => array(record.payload.concept_definition_mappings ?? record.payload.mappings).map(item => ({ ...item, __record: record })))
  const summary = object(data.summary ?? records[0]?.payload?.summary)
  const report = object(data.statistical_analysis_report ?? records[0]?.payload?.statistical_analysis_report)
  const sectionCounts = new Map()
  definitions.forEach((item, index) => {
    const section = positionLabel(item)
    const id = valueOf(item, ['definition_id', 'id'], `D${index + 1}`)
    const batchLabel = records.length > 1 ? `${item.__record.index + 1}` : ''
    const key = `${batchLabel}\u0000${section}`
    const current = sectionCounts.get(key) || { batchLabel, section, ids: [], count: 0 }
    current.ids.push(id)
    current.count += 1
    sectionCounts.set(key, current)
  })
  const sectionRows = records.length === 1 && array(report.section_distribution).length
    ? array(report.section_distribution)
    : [...sectionCounts.values()].map(item => ({ ...item, ratio: definitions.length ? item.count / definitions.length : 0 }))
  const definitionSourceHeading = resultPositionHeading(definitions)
  const definitionDistributionTitle = definitionSourceHeading === '来源位置' ? '来源位置分布' : '来源章节分布'
  const coverageLabel = definitionSourceHeading === '来源位置' ? '覆盖位置数量' : '覆盖章节数量'
  const definitionCount = records.length > 1 ? definitions.length : summary.definition_sentence_count ?? definitions.length
  const conceptCount = records.length > 1 ? new Set(definitions.map(item => item.concept)).size : summary.concept_count ?? new Set(definitions.map(item => item.concept)).size
  const mappingCount = records.length > 1 ? mappings.length : summary.mapping_count ?? mappings.length
  const averageConfidence = records.length > 1 ? average(definitions.map(item => item.confidence)) : summary.average_confidence ?? average(definitions.map(item => item.confidence))
  const pendingCount = records.length > 1 ? definitions.filter(item => item.review_status === '待复核').length : summary.pending_review_count ?? definitions.filter(item => item.review_status === '待复核').length
  const mappingCoverage = conceptCount ? mappingCount / conceptCount * 100 : 0
  const pendingRatio = definitionCount ? pendingCount / definitionCount * 100 : 0
  const reportConclusion = `本次共识别 ${definitionCount} 条概念定义句，提取 ${conceptCount} 个概念词并形成 ${mappingCount} 组结构化映射，平均置信度为 ${fixed(averageConfidence)}。${definitionDistributionTitle}与待复核数量均依据当前响应结果汇总。`
  const reviewRecommendation = pendingCount
    ? `建议优先复核 ${pendingCount} 条待确认结果，并结合${definitionSourceHeading}核对概念边界与定义完整性。`
    : `当前没有待复核结果，建议抽样检查高频概念及不同${definitionSourceHeading}的重复定义，确认映射表达保持一致。`
  return `<div class="definition-result-root" data-viz-group>
    ${summaryCards([['定义句', definitionCount], ['概念词', conceptCount], ['映射', mappingCount], ['平均置信度', fixed(averageConfidence)], ['待复核', pendingCount]], 'definition-summary-grid')}
    <div class="definition-result-header"><div class="definition-tabs"><button class="definition-tab-btn active" data-viz-tab="results">概念定义句结果</button><button class="definition-tab-btn" data-viz-tab="mapping">概念—定义映射</button><button class="definition-tab-btn" data-viz-tab="statistics">识别统计分析报告</button></div><div class="definition-export-actions"><button class="definition-export-btn" data-viz-export="json">导出 JSON</button><button class="definition-export-btn" data-viz-export="csv">导出 CSV</button></div></div>
    <div class="definition-tab-panel" data-viz-panel="results"><div class="distribution-table-wrap"><table class="distribution-table definition-result-table"><thead><tr><th>编号</th><th>概念词</th><th>概念定义句</th><th>来源</th><th>置信度</th><th>操作</th></tr></thead><tbody>${definitions.map((item, index) => `<tr><td>${escapeHtml(valueOf(item, ['definition_id', 'id'], `D${index + 1}`))}</td><td><span class="definition-concept-badge">${renderTextWithMath(valueOf(item, ['concept', 'term']))}</span></td><td>${renderTextWithMath(valueOf(item, ['definition_sentence', 'definition', 'sentence']))}</td><td>${escapeHtml(positionLabel(item))}</td><td>${confidence(item.confidence)}</td><td><button class="definition-detail-btn" data-viz-detail="definition-${index}">查看详情</button></td></tr><tr id="definition-${index}" class="definition-detail-row" hidden><td colspan="6"><div class="definition-detail-content"><div class="definition-detail-label">概念词</div><div>${renderTextWithMath(valueOf(item, ['concept', 'term']))}</div><div class="definition-detail-label">完整定义句</div><div>${renderTextWithMath(valueOf(item, ['definition_sentence', 'definition', 'sentence']))}</div><div class="definition-detail-label">抽取的定义内容</div><div>${renderTextWithMath(valueOf(item, ['definition_content', 'definition']))}</div><div class="definition-detail-label">来源</div><div>${escapeHtml(positionLabel(item))}</div></div></td></tr>`).join('') || '<tr><td colspan="6">未识别到概念定义句。</td></tr>'}</tbody></table></div></div>
    <div class="definition-tab-panel" data-viz-panel="mapping" hidden><section class="definition-mapping-board"><header class="definition-mapping-board-head"><div><span>结构化映射结果</span><h3>概念—定义结构化映射</h3><p>按“概念词—定义内容”呈现当前响应中的结构化对应关系。</p></div><div class="definition-mapping-total"><b>${mappingCount}</b><span>组有效映射</span></div></header><div class="definition-mapping-list">${mappings.map((item, index) => `<article class="definition-mapping-card"><div class="definition-mapping-index">${String(index + 1).padStart(2, '0')}</div><div class="definition-mapping-concept"><strong>${renderTextWithMath(item.concept || '—')}</strong></div><div class="definition-mapping-arrow"><span>对应定义</span><i>→</i></div><div class="definition-mapping-text"><small>定义内容</small><p>${renderTextWithMath(item.definition || '—')}</p></div></article>`).join('') || '<div class="definition-mapping-empty">暂无概念—定义映射。</div>'}</div></section></div>
    <div class="definition-tab-panel" data-viz-panel="statistics" hidden><article class="definition-analysis-report"><header class="definition-report-cover"><div><h3>识别统计分析报告</h3><p>汇总当前概念定义识别的任务规模、识别质量、位置分布和复核情况。</p></div></header><section class="definition-report-section"><h4><i>一</i>任务概况</h4><div class="definition-report-summary"><span><b>${definitionCount}</b><small>识别定义句</small></span><span><b>${conceptCount}</b><small>提取概念词</small></span><span><b>${mappingCount}</b><small>结构化映射</small></span><span><b>${pendingCount}</b><small>待人工复核</small></span></div></section><div class="definition-report-columns"><section class="definition-report-section"><h4><i>二</i>识别质量分析</h4><dl class="definition-report-definition"><div><dt>平均置信度</dt><dd>${fixed(averageConfidence)}</dd></div><div><dt>概念映射覆盖率</dt><dd>${fixed(mappingCoverage, 1)}%</dd></div><div><dt>待复核占比</dt><dd>${fixed(pendingRatio, 1)}%</dd></div><div><dt>${coverageLabel}</dt><dd>${sectionRows.length}</dd></div></dl></section><section class="definition-report-section"><h4><i>三</i>${definitionDistributionTitle}</h4><div class="distribution-table-wrap"><table class="distribution-table definition-report-table"><thead><tr>${records.length > 1 ? '<th>编号</th>' : ''}<th>${definitionSourceHeading}</th><th>定义句数量</th><th>占比</th></tr></thead><tbody>${sectionRows.map(item => `<tr>${records.length > 1 ? `<td>${escapeHtml((item.ids || []).join('、') || '—')}</td>` : ''}<td>${escapeHtml(item.section || item.name || '未返回位置')}</td><td>${number(item.count)}</td><td>${fixed(item.percentage != null ? item.percentage : number(item.ratio) * 100, 1)}%</td></tr>`).join('') || `<tr><td colspan="${records.length > 1 ? 4 : 3}">暂无位置分布统计。</td></tr>`}</tbody></table></div></section></div><section class="definition-report-section definition-report-conclusion"><h4><i>四</i>分析结论与复核建议</h4><p>${renderTextWithMath(reportConclusion)}</p><div><b>复核建议</b><span>${renderTextWithMath(reviewRecommendation)}</span></div></section><footer class="definition-report-footer">本报告仅汇总当前接口返回的真实识别结果，不补造未返回的统计字段。</footer></article></div>
  </div>`
}

function nerPosition(item) {
  return positionLabel(item)
}

function renderNer(response, variant) {
  const data = dataOf(response)
  const general = variant === 'general'
  const research = variant === 'research'
  const prefix = general ? 'ner' : research ? 'research-ner' : 'domain-research'
  const records = recordsOf(response)
  const entities = records.flatMap(record => array(record.payload.entities ?? record.payload.entity_results).map(item => ({ ...item, __record: record })))
  const mappings = records.flatMap(record => array(general ? record.payload.entity_mappings ?? record.payload.mappings : research ? record.payload.standard_term_mappings ?? record.payload.mappings : record.payload.ontology_mappings ?? record.payload.mappings))
  const summary = object(data.summary ?? records[0]?.payload?.summary)
  const selectedDomain = data.selected_domain || records[0]?.payload?.selected_domain || 'all'
  const typeValue = item => valueOf(item, ['entity_type_name', 'entity_type', 'type', 'label'])
  const cards = general
    ? [['实体总数', summary.entity_count ?? entities.length], ['人名', summary.person_count ?? entities.filter(item => ['PERSON', '人名'].includes(item.entity_type || item.type)).length], ['地名', summary.location_count ?? entities.filter(item => ['LOCATION', '地名'].includes(item.entity_type || item.type)).length], ['机构名称', summary.organization_count ?? entities.filter(item => ['ORGANIZATION', 'ORG', '机构名称'].includes(item.entity_type || item.type)).length], ['事件', summary.event_count ?? entities.filter(item => ['EVENT', '事件'].includes(item.entity_type || item.type)).length]]
    : research
      ? [['科研实体总数', entities.length], ['科研方法', entities.filter(item => typeValue(item) === '科研方法').length], ['数据资料', entities.filter(item => typeValue(item) === '数据资料').length], ['仪器设备', entities.filter(item => typeValue(item) === '仪器设备').length], ['理论原理', entities.filter(item => typeValue(item) === '理论原理').length], ['研究问题', entities.filter(item => typeValue(item) === '研究问题').length]]
      : [['专业实体总数', entities.length], ['体育科学', entities.filter(item => item.domain_name === '体育科学').length], ['地震工程', entities.filter(item => item.domain_name === '地震工程').length], ['医学', entities.filter(item => item.domain_name === '医学').length], ['已映射', entities.filter(item => item.standard_kb_id).length]]
  const summaryClass = general ? 'ner-summary-grid' : research ? 'research-ner-summary-grid' : 'domain-research-summary-grid'
  const tabClass = general ? 'ner' : research ? 'research-ner' : 'domain-research'
  const entityTitle = general ? '实体识别结果' : research ? '科研实体识别结果' : '专业实体识别结果'
  const mappingTitle = general ? '实体规范化与别名映射' : research ? '标准词表映射' : '专业本体映射'
  const idValue = (item, index) => valueOf(item, general ? ['entity_id', 'id'] : research ? ['research_entity_id', 'entity_id', 'id'] : ['entity_id', 'id'], `E${(index ?? 0) + 1}`)
  const textValue = item => valueOf(item, ['entity_text', 'text', 'entity', 'name'])
  const mappedValue = item => general ? valueOf(item, ['normalized_name', 'canonical_name']) : research ? valueOf(item.standard_names, ['zh', 'en'], item.standard_term_id || '未映射') : valueOf(item, ['standard_kb_id', 'kb_id'], '未映射')
  if (general) {
    const generalTypeLabel = item => ({ PERSON: '人名', LOCATION: '地名', ORGANIZATION: '机构名称', ORG: '机构名称', EVENT: '事件' }[typeValue(item)] || typeValue(item))
    const generalCards = [
      ['实体总数', entities.length],
      ['人名', entities.filter(item => ['PERSON', '人名'].includes(item.entity_type || item.type)).length],
      ['地名', entities.filter(item => ['LOCATION', '地名'].includes(item.entity_type || item.type)).length],
      ['机构名称', entities.filter(item => ['ORGANIZATION', 'ORG', '机构名称'].includes(item.entity_type || item.type)).length],
      ['事件', entities.filter(item => ['EVENT', '事件'].includes(item.entity_type || item.type)).length],
    ]
    return `<div class="ner-result-root" data-viz-group>
      ${summaryCards(generalCards, 'ner-summary-grid')}
      <div class="ner-tab-panel"><div class="distribution-table-wrap"><table class="distribution-table ner-results-table"><colgroup><col style="width:10%"><col style="width:14%"><col style="width:11%"><col style="width:14%"><col style="width:41%"><col style="width:10%"></colgroup><thead><tr><th>编号</th><th>实体名称</th><th>实体类别</th><th>实体位置</th><th>语境片段</th><th>置信度</th></tr></thead><tbody>${entities.map((item, index) => `<tr class="ner-main-row"><td><span class="distribution-level-tag">${escapeHtml(idValue(item, index))}</span></td><td><div class="ner-entity-text">${renderTextWithMath(textValue(item))}</div></td><td><span class="ner-type-badge">${escapeHtml(generalTypeLabel(item))}</span></td><td>${escapeHtml(nerPosition(item))}</td><td>${renderTextWithMath(item.context || '—')}</td><td>${confidence(item.confidence)}</td></tr>`).join('') || '<tr><td colspan="6">未识别到实体。</td></tr>'}</tbody></table></div></div>
    </div>`
  }
  if (!research) {
    const domainHeaders = ['编号', '专业实体', '领域标签', '实体类型', '句子位置', '知识库ID', '置信度', '操作']
    const domainEntityRows = entities.map((item, index) => `<tr class="domain-research-main-row"><td><span class="distribution-level-tag">${escapeHtml(idValue(item, index))}</span></td><td><div class="domain-research-entity-text">${renderTextWithMath(textValue(item))}</div></td><td><span class="domain-research-domain-badge">${escapeHtml(item.domain_name || item.domain || '—')}</span></td><td><span class="domain-research-type-badge">${escapeHtml(typeValue(item))}</span></td><td>${escapeHtml(nerPosition(item))}</td><td><span class="domain-kb-id">${escapeHtml(item.standard_kb_id || '内置知识库')}</span><br><span class="domain-mapping-status">${escapeHtml(item.mapping_status || '已映射')}</span></td><td>${confidence(item.confidence)}</td><td><button class="domain-research-detail-btn" data-viz-detail="domain-research-detail-${index}">查看详情</button></td></tr><tr id="domain-research-detail-${index}" class="domain-research-detail-row" hidden><td class="domain-research-detail-cell" colspan="8"><div class="domain-research-detail-content"><div class="domain-research-detail-label">专业实体</div><div class="domain-research-detail-value">${renderTextWithMath(textValue(item))}</div><div class="domain-research-detail-label">领域标签</div><div class="domain-research-detail-value">${escapeHtml(item.domain_name || item.domain || '—')}</div><div class="domain-research-detail-label">实体类型</div><div class="domain-research-detail-value">${escapeHtml(typeValue(item))}</div><div class="domain-research-detail-label">来源位置</div><div class="domain-research-detail-value">${escapeHtml(nerPosition(item))}</div><div class="domain-research-detail-label">关联上下文</div><div class="domain-research-detail-value">${renderTextWithMath(item.context || '—')}</div><div class="domain-research-detail-label">标准知识库ID</div><div class="domain-research-detail-value">${escapeHtml(item.standard_kb_id || '未映射')}</div></div></td></tr>`).join('')
    const domainMappingRows = mappings.map((item, index) => `<tr><td><span class="domain-kb-id">${escapeHtml(idValue(item, index) || '—')}</span></td><td>${renderTextWithMath(textValue(item))}</td><td>${escapeHtml(item.domain_name || item.domain || '—')}</td><td>${escapeHtml(typeValue(item))}</td><td style="white-space:nowrap"><span class="domain-mapping-status">${escapeHtml(item.mapping_status || '已映射')}</span><span style="margin-left:8px">${confidence(item.mapping_confidence)}</span></td></tr>`).join('')
    return `<div class="domain-research-result-root" data-viz-group>
      ${summaryCards(cards, summaryClass)}
      <div class="domain-research-result-header"><div class="domain-research-tabs"><button class="domain-research-tab-btn active" data-viz-tab="entities">${entityTitle}</button><button class="domain-research-tab-btn" data-viz-tab="mapping">${mappingTitle}</button></div><div class="domain-research-export-actions"><button class="domain-research-export-btn" data-viz-export="json">导出 JSON</button><button class="domain-research-export-btn" data-viz-export="csv">导出 CSV</button></div></div>
      <div class="domain-research-tab-panel" data-viz-panel="entities"><div class="distribution-table-wrap"><table class="distribution-table domain-research-results-table"><thead><tr>${domainHeaders.map(item => `<th>${item}</th>`).join('')}</tr></thead><tbody>${domainEntityRows || '<tr><td colspan="8">未识别到达到阈值的实体。</td></tr>'}</tbody></table></div></div>
      <div class="domain-research-tab-panel" data-viz-panel="mapping" hidden><div class="distribution-table-wrap"><table class="distribution-table domain-research-mapping-table"><thead><tr><th>编号</th><th>当前识别表达</th><th>领域标签</th><th>实体类型</th><th>映射状态/置信度</th></tr></thead><tbody>${domainMappingRows || '<tr><td colspan="5">暂无映射结果。</td></tr>'}</tbody></table></div></div>
    </div>`
  }
  const headers = general
    ? ['编号', '实体名称', '实体类别', '语言', '来源位置', '置信度', '操作']
    : research
      ? ['编号', '科研实体', '实体类型', '句子位置', '映射标准词', '置信度', '操作']
      : ['编号', '专业实体', '领域标签', '实体类型', '句子位置', '知识库ID', '置信度', '操作']
  return `<div class="${prefix}-result-root" data-viz-group>
    ${summaryCards(cards, summaryClass)}
    <div class="${tabClass}-result-header"><div class="${tabClass}-tabs"><button class="${tabClass}-tab-btn active" data-viz-tab="entities">${entityTitle}</button><button class="${tabClass}-tab-btn" data-viz-tab="mapping">${mappingTitle}</button></div><div class="${tabClass}-export-actions"><button class="${tabClass}-export-btn" data-viz-export="json">导出 JSON</button><button class="${tabClass}-export-btn" data-viz-export="csv">导出 CSV</button></div></div>
    <div class="${tabClass}-tab-panel" data-viz-panel="entities"><div class="distribution-table-wrap"><table class="distribution-table ${prefix}-results-table">${research ? '<colgroup><col style="width:10%"><col style="width:22%"><col style="width:12%"><col style="width:16%"><col style="width:22%"><col style="width:8%"><col style="width:10%"></colgroup>' : ''}<thead><tr>${headers.map(item => `<th>${item}</th>`).join('')}</tr></thead><tbody>${entities.map((item, index) => `<tr class="${prefix}-main-row"><td><span class="distribution-level-tag">${escapeHtml(idValue(item, index))}</span></td><td><div class="${prefix}-entity-text">${renderTextWithMath(textValue(item))}</div></td>${general ? `<td><span class="ner-type-badge">${escapeHtml(typeValue(item))}</span></td><td>${escapeHtml(item.language || '—')}</td><td>${escapeHtml(nerPosition(item))}</td>` : research ? `<td><span class="research-ner-type-badge">${escapeHtml(typeValue(item))}</span></td><td>${escapeHtml(nerPosition(item))}</td><td>${escapeHtml(mappedValue(item))}</td>` : `<td><span class="domain-research-domain-badge">${escapeHtml(item.domain_name || item.domain || '—')}</span></td><td><span class="domain-research-type-badge">${escapeHtml(typeValue(item))}</span></td><td>${escapeHtml(nerPosition(item))}</td><td><span class="domain-kb-id">${escapeHtml(item.standard_kb_id || '内置知识库')}</span><br><span class="domain-mapping-status">${escapeHtml(item.mapping_status || '已映射')}</span></td>`}<td>${confidence(item.confidence)}</td><td><button class="${prefix}-detail-btn" data-viz-detail="${prefix}-detail-${index}">查看详情</button></td></tr><tr id="${prefix}-detail-${index}" class="${prefix}-detail-row" hidden><td class="${prefix}-detail-cell" colspan="${headers.length}"><div class="${prefix}-detail-content"><div class="${prefix}-detail-label">${general ? '实体名称' : research ? '科研实体' : '专业实体'}</div><div class="${prefix}-detail-value">${renderTextWithMath(textValue(item))}</div><div class="${prefix}-detail-label">实体类型</div><div class="${prefix}-detail-value">${escapeHtml(typeValue(item))}</div><div class="${prefix}-detail-label">来源位置</div><div class="${prefix}-detail-value">${escapeHtml(nerPosition(item))}</div><div class="${prefix}-detail-label">关联上下文</div><div class="${prefix}-detail-value">${renderTextWithMath(item.context || '—')}</div><div class="${prefix}-detail-label">${general ? '规范实体编码' : research ? '实体编号' : '标准知识库ID'}</div><div class="${prefix}-detail-value">${escapeHtml(general ? item.canonical_entity_id || '未启用' : research ? idValue(item, index) || '未映射' : item.standard_kb_id || '未映射')}</div></div></td></tr>`).join('') || `<tr><td colspan="${headers.length}">未识别到达到阈值的实体。</td></tr>`}</tbody></table></div></div>
    <div class="${tabClass}-tab-panel" data-viz-panel="mapping" hidden><div class="distribution-table-wrap"><table class="distribution-table ${prefix}-mapping-table">${research ? '<colgroup><col style="width:18%"><col style="width:23%"><col style="width:27%"><col style="width:14%"><col style="width:18%"></colgroup>' : ''}<thead><tr>${general ? '<th>规范实体编码</th><th>中文规范名</th><th>英文规范名</th><th>缩写</th><th>其他别名</th><th>当前文本出现形式</th><th>实体类别</th><th>出现次数</th>' : research ? '<th>实体编号</th><th>中文标准词</th><th>英文标准词</th><th>实体类型</th><th>映射状态/置信度</th>' : '<th>标准知识库ID</th><th>领域/实体类型</th><th>标准名称</th><th>本体分类路径</th><th>别名</th><th>当前识别表达</th><th>映射状态/置信度</th>'}</tr></thead><tbody>${mappings.map((item, index) => general ? `<tr><td><span class="ner-code">${escapeHtml(item.canonical_entity_id || '—')}</span></td><td>${escapeHtml(item.canonical_names?.zh || '—')}</td><td>${escapeHtml(item.canonical_names?.en || '—')}</td><td>${escapeHtml(join(item.abbreviations))}</td><td>${escapeHtml(join([...(item.aliases?.zh || []), ...(item.aliases?.en || [])]))}</td><td>${renderTextWithMath(join(array(item.observed_mentions).map(x => x.text)))}</td><td>${escapeHtml(typeValue(item))}</td><td>${number(item.occurrence_count, array(item.observed_mentions).length)}</td></tr>` : research ? `<tr><td><span class="research-standard-id">${escapeHtml(idValue(item, index) || '—')}</span></td><td>${escapeHtml(item.standard_names?.zh || '—')}</td><td>${escapeHtml(item.standard_names?.en || '—')}</td><td>${escapeHtml(typeValue(item))}</td><td style="white-space:nowrap"><span class="research-mapping-status">${escapeHtml(item.mapping_status || '已映射')}</span><span style="margin-left:8px">${confidence(item.mapping_confidence)}</span></td></tr>` : `<tr><td><span class="domain-kb-id">${escapeHtml(item.standard_kb_id || '—')}</span></td><td>${escapeHtml(item.domain_name || item.domain || '—')}<br>${escapeHtml(typeValue(item))}</td><td>${escapeHtml(item.standard_names?.zh || '—')}<br>${escapeHtml(item.standard_names?.en || '—')}</td><td>${escapeHtml(item.ontology_path || '—')}</td><td>${escapeHtml(join(item.aliases))}</td><td>${renderTextWithMath(join(array(item.observed_mentions).map(x => x.text)))}</td><td><span class="domain-mapping-status">${escapeHtml(item.mapping_status || '已映射')}</span><br>${confidence(item.mapping_confidence)}</td></tr>`).join('') || `<tr><td colspan="${general ? 8 : research ? 5 : 7}">暂无映射结果。</td></tr>`}</tbody></table></div></div>
  </div>`
}

function entityPart(value) {
  return typeof value === 'object' ? valueOf(value, ['text', 'name', 'entity']) : value || '—'
}

function renderNetwork(data) {
  const network = object(data.knowledge_network ?? data.network)
  const nodes = array(network.nodes)
  const edges = array(network.edges)
  if (!nodes.length) return '<div class="relation-network-wrap"><div class="relation-network-head"><div class="relation-network-title">科研实体知识网络</div></div><div class="relation-network-empty">暂无可展示的知识网络。</div></div>'
  const width = 760
  const coords = nodes.map((node, index) => ({ ...node, x: 110 + (index % 3) * 270, y: 95 + Math.floor(index / 3) * 135 }))
  const byName = name => coords.find(item => item.name === name || item.id === name)
  return `<div class="relation-network-wrap"><div class="relation-network-head"><div><div class="relation-network-title">科研实体知识网络</div><div class="relation-network-meta">连通分量分区 · 分层防碰撞布局 · 曲线有向边</div></div><div class="relation-network-meta">${nodes.length} 个节点 · ${edges.length} 条关系边</div></div><div class="relation-network-canvas"><svg class="relation-network-svg" viewBox="0 0 ${width} 360"><defs><marker id="relationArrowVue" markerWidth="9" markerHeight="9" refX="8" refY="4.5" orient="auto"><path d="M0,0 L9,4.5 L0,9 Z" fill="#8fa0b8" /></marker></defs>${edges.map(edge => { const s = byName(edge.source); const t = byName(edge.target); if (!s || !t) return ''; return `<path class="relation-network-edge" d="M ${s.x} ${s.y} C ${(s.x + t.x) / 2} ${s.y}, ${(s.x + t.x) / 2} ${t.y}, ${t.x} ${t.y}" marker-end="url(#relationArrowVue)"/><text class="relation-network-edge-label" x="${(s.x + t.x) / 2}" y="${(s.y + t.y) / 2 - 8}">${escapeHtml(edge.relation)}</text>` }).join('')}${coords.map(node => `<g><rect class="relation-network-node" x="${node.x - 72}" y="${node.y - 28}" width="144" height="56" rx="12" fill="#eef3ff" stroke="#9eb2ff"/><text class="relation-network-node-text" x="${node.x}" y="${node.y - 3}">${escapeHtml(node.name)}</text><text class="relation-network-node-type" x="${node.x}" y="${node.y + 16}">${escapeHtml(node.type || '实体')}</text></g>`).join('')}</svg></div><details class="relation-network-details"><summary>查看全部关系边列表</summary><div class="relation-network-list">${edges.map(edge => `<div class="relation-network-list-item"><span>${renderTextWithMath(edge.source)}</span><span class="relation-triple-edge">${renderTextWithMath(edge.relation)}</span><span>${renderTextWithMath(edge.target)}</span></div>`).join('')}</div></details></div>`
}

function renderRelations(response) {
  const data = dataOf(response)
  const records = recordsOf(response)
  const triples = records.flatMap(record => array(record.payload.triples ?? record.payload.relations ?? record.payload.relation_results).map(item => ({ ...item, __record: record })))
  const summary = object(data.summary ?? records[0]?.payload?.summary)
  const networkSource = object(data.knowledge_network ?? data.network ?? records[0]?.payload?.knowledge_network ?? records[0]?.payload?.network)
  const nodes = array(networkSource.nodes)
  return `<div class="relation-result-root" data-viz-group>
    ${summaryCards([['关系三元组', summary.triple_count ?? triples.length], ['实体对', summary.entity_pair_count ?? triples.length], ['关系类型', summary.relation_type_count ?? new Set(triples.map(item => entityPart(item.relation))).size], ['涉及实体', summary.entity_count ?? nodes.length]], 'relation-summary-grid')}
    <div class="relation-result-header"><div class="relation-tabs"><button class="relation-tab-btn active" data-viz-tab="triples">关系三元组</button><button class="relation-tab-btn" data-viz-tab="network">知识网络</button></div><div class="relation-export-actions"><button class="relation-export-btn" data-viz-export="json">导出 JSON</button><button class="relation-export-btn" data-viz-export="csv">导出 CSV</button></div></div>
    <div class="relation-tab-panel" data-viz-panel="triples"><div class="distribution-table-wrap"><table class="distribution-table relation-results-table"><thead><tr><th>编号</th><th>主体实体</th><th>关系类型</th><th>客体实体</th><th>句子位置</th><th>置信度</th><th>操作</th></tr></thead><tbody>${triples.map((item, index) => `<tr class="relation-main-row"><td><span class="distribution-level-tag">${escapeHtml(valueOf(item, ['triple_id', 'id'], `T${index + 1}`))}</span></td><td><div class="relation-entity-text">${renderTextWithMath(entityPart(item.subject ?? item.source ?? item.head))}</div></td><td><span class="relation-label-badge">${renderTextWithMath(entityPart(item.relation ?? item.predicate ?? item.type))}</span></td><td><div class="relation-entity-text">${renderTextWithMath(entityPart(item.object ?? item.target ?? item.tail))}</div></td><td>${escapeHtml(positionLabel(item))}</td><td>${confidence(item.confidence)}</td><td><button class="relation-detail-btn" data-viz-detail="relation-detail-${index}">查看详情</button></td></tr><tr id="relation-detail-${index}" class="relation-detail-row" hidden><td class="relation-detail-cell" colspan="7"><div class="relation-detail-content"><div class="relation-detail-label">关系三元组</div><div class="relation-detail-value"><div class="relation-triple-line"><span class="relation-triple-node">${renderTextWithMath(entityPart(item.subject ?? item.source ?? item.head))}</span><span class="relation-triple-edge">${renderTextWithMath(entityPart(item.relation ?? item.predicate ?? item.type))}</span><span class="relation-triple-node">${renderTextWithMath(entityPart(item.object ?? item.target ?? item.tail))}</span></div></div><div class="relation-detail-label">关系触发词</div><div class="relation-detail-value">${renderTextWithMath(item.relation?.trigger || '—')}</div><div class="relation-detail-label">上下文证据</div><div class="relation-detail-value">${renderTextWithMath(item.context || item.evidence || item.sentence || '—')}</div><div class="relation-detail-label">依存路径</div><div class="relation-detail-value"><div class="relation-dependency-path">${escapeHtml(item.dependency_path || '未返回')}</div></div></div></td></tr>`).join('') || '<tr><td colspan="7">未识别到达到阈值的实体关系三元组。</td></tr>'}</tbody></table></div></div>
    <div class="relation-tab-panel" data-viz-panel="network" hidden>${renderNetwork({ ...data, knowledge_network: networkSource })}</div>
  </div>`
}

const clusterColors = ['#315efb', '#08a66c', '#f59e0b', '#9b51e0', '#e5484d']

function renderDeepCluster(response) {
  const data = (recordsOf(response)[0] || {}).payload || dataOf(response)
  const clusters = array(data.clusters)
  const points = array(data.semantic_projection)
  const quality = object(data.clustering_quality)
  const trend = object(data.theme_trend_analysis)
  const hasTrend = Boolean(array(trend.series).length || array(trend.years).length)
  const colorMap = Object.fromEntries(clusters.map((item, index) => [item.cluster_id, clusterColors[index % clusterColors.length]]))
  return `<div class="deep-cluster-result-root" data-viz-group>
    <div class="deep-cluster-summary-grid"><div class="deep-cluster-summary-card"><div class="deep-cluster-summary-label">输入文献</div><div class="deep-cluster-summary-value">${data.input_summary?.document_count || 0}<span class="deep-cluster-summary-unit">篇</span></div></div><div class="deep-cluster-summary-card"><div class="deep-cluster-summary-label">形成类簇</div><div class="deep-cluster-summary-value">${quality.cluster_count || clusters.length}<span class="deep-cluster-summary-unit">个</span></div></div><div class="deep-cluster-summary-card"><div class="deep-cluster-summary-label">聚类维度</div><div class="deep-cluster-summary-value deep-cluster-summary-value-text">${escapeHtml(data.cluster_dimension_name || '—')}</div></div><div class="deep-cluster-summary-card"><div class="deep-cluster-summary-label">轮廓系数</div><div class="deep-cluster-summary-value">${quality.silhouette_score != null ? fixed(quality.silhouette_score) : '—'}</div></div></div>
    <div class="deep-cluster-result-tabs"><button class="deep-cluster-result-tab active" data-viz-tab="overview">类簇与特征统计</button><button class="deep-cluster-result-tab" data-viz-tab="assignments">文献归属</button>${hasTrend ? '<button class="deep-cluster-result-tab" data-viz-tab="trends">主题趋势</button>' : ''}</div>
    <div class="deep-cluster-result-panel active" data-viz-panel="overview"><div class="deep-cluster-projection-card"><div class="deep-cluster-panel-title">二维语义投影</div><svg class="deep-cluster-projection-svg" viewBox="0 0 800 310"><line x1="35" y1="285" x2="770" y2="285" stroke="#d8e0ea"/><line x1="35" y1="20" x2="35" y2="285" stroke="#d8e0ea"/>${points.map(point => `<g><circle cx="${number(point.x) * 7.3 + 35}" cy="${number(point.y) * 2.7 + 20}" r="6" fill="${colorMap[point.cluster_id] || '#6b7c93'}"/><text x="${number(point.x) * 7.3 + 44}" y="${number(point.y) * 2.7 + 24}" font-size="9.5" fill="#53657c">${escapeHtml(point.document_id)}</text></g>`).join('')}</svg><div class="deep-cluster-legend">${clusters.map((cluster, index) => `<span class="deep-cluster-legend-item"><i class="deep-cluster-legend-dot" style="background:${clusterColors[index % clusterColors.length]}"></i>${escapeHtml(cluster.cluster_id)}</span>`).join('')}</div></div><div class="deep-cluster-cards">${clusters.map(cluster => { const fs = object(cluster.feature_statistics); return `<div class="deep-cluster-card"><div class="deep-cluster-card-head"><div class="deep-cluster-card-title">${escapeHtml(cluster.cluster_id)}</div><div class="deep-cluster-card-size">${number(cluster.size)} 篇 · ${fixed(number(cluster.ratio) * 100, 1)}%</div></div><div class="deep-cluster-term-row">${array(cluster.representative_terms).map(term => `<span class="deep-cluster-term">${renderTextWithMath(term)}</span>`).join('')}</div>${[['类内相似度', fs.intra_cluster_similarity], ['类间分离度', fs.inter_cluster_separation], ['语义密度', fs.semantic_density]].map(([label, val]) => `<div class="deep-cluster-stat-row"><span>${label}</span><i class="deep-cluster-stat-track"><b class="deep-cluster-stat-fill" style="width:${number(val) * 100}%"></b></i><strong>${fixed(val)}</strong></div>`).join('')}<div class="deep-cluster-doc-links"><b>代表文献：</b>${array(cluster.representative_documents).map(doc => `${escapeHtml(doc.document_id)} ${renderTextWithMath(doc.title)}`).join('；') || '—'}</div></div>` }).join('')}</div></div>
    <div class="deep-cluster-result-panel" data-viz-panel="assignments" hidden><div class="deep-cluster-table-wrap"><table><thead><tr><th>文献编号</th><th>文献标题</th><th>年份</th><th>所属类簇</th><th>中心相似度</th><th>归类依据</th></tr></thead><tbody>${array(data.document_assignments).map(item => `<tr><td><code>${escapeHtml(item.document_id)}</code></td><td>${renderTextWithMath(item.title)}</td><td>${escapeHtml(item.publication_year)}</td><td>${escapeHtml(item.cluster_id)}</td><td>${fixed(item.similarity_to_centroid, 3)}</td><td>${renderTextWithMath(item.key_evidence)}</td></tr>`).join('') || '<tr><td colspan="6">暂无文献归属数据。</td></tr>'}</tbody></table></div></div>
    <div class="deep-cluster-result-panel" data-viz-panel="trends" hidden><div class="deep-cluster-trend-insights"><div class="deep-cluster-insight"><b>上升类簇</b><span>${escapeHtml(trend.rising_cluster_id || '—')}</span></div><div class="deep-cluster-insight"><b>新兴类簇</b><span>${escapeHtml(trend.emerging_cluster_id || '—')}</span></div><div class="deep-cluster-insight"><b>稳定类簇</b><span>${escapeHtml(trend.stable_cluster_id || '—')}</span></div></div><div class="deep-cluster-trend-card"><div class="deep-cluster-panel-title">类簇年度分布</div><div class="deep-cluster-year-header"><span>类簇编号 / 代表短语</span>${array(trend.years).map(year => `<span>${year}</span>`).join('')}</div>${array(trend.series).map((item, index) => `<div class="deep-cluster-trend-row"><div class="deep-cluster-trend-label"><i class="deep-cluster-legend-dot" style="display:inline-block;background:${clusterColors[index % clusterColors.length]};margin-right:6px"></i><b>${escapeHtml(item.cluster_id)}</b><small style="display:block;margin-left:18px;color:#7a889b">${renderTextWithMath(array(item.representative_terms).slice(0, 2).join(' / '))}</small></div>${array(item.yearly_counts).map(value => `<div class="deep-cluster-trend-cell"><span>${value}</span><i class="deep-cluster-trend-bar" style="height:${Math.max(3, number(value) * 10)}px;background:${clusterColors[index % clusterColors.length]}"></i></div>`).join('')}</div>`).join('')}</div><div class="deep-cluster-method-note"><b>趋势判断：</b>${renderTextWithMath(trend.summary || '—')}</div></div>
    <div class="deep-cluster-method-note">当前结果基于双轴主题映射：每篇文献经 LLM 抽取技术路线与应用场景描述后，匹配至主题体系并聚成类簇。技术路线轴聚焦方法、模型、算法与处理流程；应用场景轴聚焦研究对象、行业领域与应用目标。</div>
  </div>`
}

function renderClusterLabels(response) {
  const data = (recordsOf(response)[0] || {}).payload || dataOf(response)
  const labels = array(data.labels ?? data.cluster_labels)
  const avgConf = data.statistics?.average_confidence ?? average(labels.map(item => item.confidence))
  const avgDist = data.statistics?.average_distinctiveness ?? average(labels.map(item => item.distinctiveness))
  return `<div class="cluster-label-result-v705" data-viz-group><div class="cluster-label-result-toolbar-v705"><span>结果与接口响应保持一致，可复制或下载类簇标签和候选证据。</span><div class="cluster-label-result-actions-v705"><button data-viz-export="copy">复制结果</button><button data-viz-export="json">下载 JSON</button><button data-viz-export="csv">下载 CSV</button></div></div><div class="cluster-label-result-summary-v705"><div class="cluster-label-result-stat-v705"><strong>${data.cluster_count || labels.length}</strong><span>输入类簇</span></div><div class="cluster-label-result-stat-v705"><strong>${data.generated_label_count || labels.length}</strong><span>推荐标签</span></div><div class="cluster-label-result-stat-v705"><strong>${avgConf != null ? fixed(avgConf) : '—'}</strong><span>平均置信度</span></div><div class="cluster-label-result-stat-v705"><strong>${avgDist != null ? fixed(avgDist) : '—'}</strong><span>平均区分度</span></div></div><div class="cluster-label-result-tabs-v705"><button class="cluster-label-result-tab-v705 active" data-viz-tab="labels">推荐标签</button><button class="cluster-label-result-tab-v705" data-viz-tab="candidates">候选与证据</button></div><div class="cluster-label-result-panel-v705 active" data-viz-panel="labels"><div class="distribution-table-wrap"><table class="cluster-label-result-table-v705"><thead><tr><th>类簇</th><th>推荐标签</th><th>置信度</th><th>区分度</th><th>区分度说明</th><th>关联信息</th></tr></thead><tbody>${labels.map(item => `<tr><td>${escapeHtml(item.cluster_id)}</td><td><span class="cluster-label-recommend-v705">${escapeHtml(item.recommended_label || item.label || '—')}</span></td><td>${confidence(item.confidence)}</td><td>${confidence(item.distinctiveness)}</td><td>${renderTextWithMath(item.difference_explanation || item.description || '—')}</td><td>${array(item.linked_document_ids).length ? escapeHtml(item.linked_document_ids.join('、')) : `${item.evidence?.text_count || 0} 条文本`}</td></tr>`).join('') || '<tr><td colspan="6">当前没有可用的推荐标签。</td></tr>'}</tbody></table></div></div><div class="cluster-label-result-panel-v705" data-viz-panel="candidates" hidden><div class="cluster-label-candidate-grid-v705">${labels.map(item => `<div class="cluster-label-candidate-card-v705"><h4>${escapeHtml(item.cluster_id)} · ${escapeHtml(item.recommended_label || item.label || '—')}</h4><div class="cluster-label-chip-row-v705">${array(item.candidate_labels ?? item.candidates ?? item.alternatives).map((candidate, index) => `<span class="cluster-label-chip-v705">#${candidate.rank || index + 1} ${escapeHtml(candidate.label || candidate)} · ${confidence(candidate.confidence)}</span>`).join('')}</div><div class="cluster-label-evidence-line-v705"><b>关键词：</b>${escapeHtml(join(item.evidence?.keywords))}</div><div class="cluster-label-evidence-line-v705"><b>命名实体：</b>${escapeHtml(join(item.evidence?.named_entities))}</div><div class="cluster-label-evidence-line-v705"><b>中心句：</b>${renderTextWithMath(item.evidence?.center_sentence || '—')}</div></div>`).join('') || '<div class="cluster-label-note-v705">当前没有可展示的候选标签与证据。</div>'}</div></div></div>`
}

function renderReview(response) {
  const data = (recordsOf(response)[0] || {}).payload || dataOf(response)
  const stats = object(data.statistics)
  const tree = array(data.tree ?? data.review_tree)
  const trendRaw = data.trend_hotspot_distribution ?? data.trends
  const trendsHtml = (typeof trendRaw === 'string' && trendRaw.trim())
    ? `<div class="v710-review-report"><p>${renderTextWithMath(trendRaw)}</p></div>`
    : array(trendRaw?.hotspots).length
      ? array(trendRaw.hotspots).map(item => `<div class="v710-review-hotspot-item"><div class="v710-review-hotspot-head"><span>${escapeHtml(item.name)} · ${escapeHtml(item.status)}</span><b>${fixed(item.score)}</b></div><div class="v710-review-hotspot-track"><i class="v710-review-hotspot-fill" style="width:${number(item.score) * 100}%"></i></div></div>`).join('')
      : '<div class="semantic-empty" style="padding:16px;color:#7a889b">暂无趋势分析数据。</div>'
  return `<div class="v710-review-result" data-viz-group><div class="v710-review-result-toolbar"><div class="v710-review-summary-grid"><div class="v710-review-summary-card"><b>${data.document_count || 0}</b><span>综述文献</span></div><div class="v710-review-summary-card"><b>${stats.research_question_count || tree.length}</b><span>研究问题</span></div><div class="v710-review-summary-card"><b>${stats.method_count || tree.reduce((sum, item) => sum + array(item.methods).length, 0)}</b><span>研究方法</span></div><div class="v710-review-summary-card"><b>${stats.evidence_sentence_count || 0}</b><span>证据句</span></div></div><div class="v710-review-result-actions"><button class="outline-btn" data-viz-export="copy">复制结果</button><button class="outline-btn" data-viz-export="json">下载JSON</button><button class="outline-btn" data-viz-export="csv">下载CSV</button></div></div><div class="v710-review-result-tabs"><button class="v710-review-tab active" data-viz-tab="tree">三层树形综述</button><button class="v710-review-tab" data-viz-tab="report">结构化文本</button><button class="v710-review-tab" data-viz-tab="trends">趋势热点</button><button class="v710-review-tab" data-viz-tab="evidence">来源证据</button></div><div class="v710-review-result-panel active" data-viz-panel="tree"><div class="v710-review-tree">${tree.map(item => `<div class="v710-review-question"><div class="v710-review-question-head"><span>${escapeHtml(item.question_id || '—')} · ${renderTextWithMath(item.research_question || item.question || '—')}</span><span>${item.document_count || 0}篇</span></div>${array(item.methods).map(method => `<div class="v710-review-method"><b>${escapeHtml(method.method_id || '—')} · ${renderTextWithMath(method.method || method.name || '—')}</b>${array(method.progress ?? method.progresses).map(progress => `<div class="v710-review-progress"><strong>研究进展：</strong>${renderTextWithMath(progress.summary || progress.progress || '—')}<br><strong>阶段结论：</strong>${renderTextWithMath(progress.conclusion || '—')}<div class="v710-review-chip-row">${array(progress.source_ids).map(id => `<span class="v710-review-chip">${escapeHtml(id)}</span>`).join('')}</div></div>`).join('')}</div>`).join('')}</div>`).join('')}</div></div><div class="v710-review-result-panel" data-viz-panel="report" hidden><div class="v710-review-report"><strong>${renderTextWithMath(data.topic || '结构化自动综述')}</strong><p>${renderTextWithMath(data.structured_report?.overview || '—')}</p>${array(data.structured_report?.sections).map(section => `<h4>${renderTextWithMath(section.title)}</h4><p>${renderTextWithMath(section.content)}</p>`).join('')}</div></div><div class="v710-review-result-panel" data-viz-panel="trends" hidden>${trendsHtml}</div><div class="v710-review-result-panel" data-viz-panel="evidence" hidden><div class="v710-review-table-wrap"><table class="v710-review-table"><thead><tr><th>文献编号</th><th>文献题名</th><th>来源章节</th><th>证据片段</th><th>支撑节点</th></tr></thead><tbody>${array(data.evidence_index).map(item => `<tr><td>${escapeHtml(item.document_id)}</td><td>${renderTextWithMath(item.title)}</td><td>${escapeHtml(item.source_section)}</td><td>${renderTextWithMath(item.evidence_excerpt)}</td><td>${array(item.supported_nodes).map(node => `<span class="v710-review-chip">${escapeHtml(node)}</span>`).join(' ')}</td></tr>`).join('') || '<tr><td colspan="5">未返回来源证据。</td></tr>'}</tbody></table></div></div></div>`
}

export const specializedVisualizationIds = new Set([
  'fund-move', 'zh-abstract-move', 'en-abstract-move',
  'zh-classify', 'en-classify', 'zh-keyword', 'en-keyword', 'rq-detect',
  'citation-sentiment', 'citation-intent', 'definition-detect', 'general-ner', 'research-ner',
  'domain-ner', 'relation-extract', 'deep-cluster', 'cluster-label', 'structured-review',
])

export function renderSpecializedVisualization(toolId, response) {
  if (!specializedVisualizationIds.has(toolId)) return ''
  if (toolId === 'fund-move') return renderFundMove(response)
  if (toolId === 'zh-abstract-move') return renderAbstractMove(response, false)
  if (toolId === 'en-abstract-move') return renderAbstractMove(response, true)
  if (toolId === 'zh-classify') return renderClassification(response, false)
  if (toolId === 'en-classify') return renderClassification(response, true)
  if (toolId === 'zh-keyword') return renderZhKeyword(response)
  if (toolId === 'en-keyword') return renderEnKeyword(response)
  if (toolId === 'rq-detect') return renderResearchQuestions(response)
  if (toolId === 'citation-sentiment') return renderCitation(response, false)
  if (toolId === 'citation-intent') return renderCitation(response, true)
  if (toolId === 'definition-detect') return renderDefinitions(response)
  if (toolId === 'general-ner') return renderNer(response, 'general')
  if (toolId === 'research-ner') return renderNer(response, 'research')
  if (toolId === 'domain-ner') return renderNer(response, 'domain')
  if (toolId === 'relation-extract') return renderRelations(response)
  if (toolId === 'deep-cluster') return renderDeepCluster(response)
  if (toolId === 'cluster-label') return renderClusterLabels(response)
  if (toolId === 'structured-review') return renderReview(response)
  return ''
}

function csvEscape(value) {
  return `"${String(value ?? '').replace(/"/g, '""')}"`
}

export function responseToCsv(response) {
  const data = dataOf(response)
  const rows = Array.isArray(data.results) ? data.results : [data]
  const columns = [...new Set(rows.flatMap(item => Object.keys(object(item))))]
  return [columns.map(csvEscape).join(','), ...rows.map(row => columns.map(column => csvEscape(typeof row[column] === 'object' ? JSON.stringify(row[column]) : row[column])).join(','))].join('\n')
}
