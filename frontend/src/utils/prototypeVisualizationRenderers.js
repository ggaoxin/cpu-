import { renderSpecializedVisualization, renderTextWithMath } from './visualizationRenderers.js'
import { resultPositionHeading, resultPositionLabel } from './chapterPositions.js'

const array = value => Array.isArray(value) ? value : []
const object = value => value && typeof value === 'object' && !Array.isArray(value) ? value : {}
const number = (value, fallback = 0) => Number.isFinite(Number(value)) ? Number(value) : fallback
const fixed = (value, digits = 2) => number(value).toFixed(digits)
const escapeHtml = value => String(value ?? '').replace(/[&<>'"]/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[char]))
const average = values => {
  const usable = values.map(Number).filter(Number.isFinite)
  return usable.length ? usable.reduce((sum, value) => sum + value, 0) / usable.length : 0
}
const confidence = value => value == null || value === '' ? '—' : `${(number(value) * 100).toFixed(1)}%`

function dataOf(response) {
  return object(response?.data ?? response)
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
      return {
        index,
        status: item?.status || 'success',
        // 文件名优先：PDF 抽取的 document_title 可能是期刊名/页眉等噪声，
        // 上传场景用户以文件名识别文献（与 visualizationRenderers.js 同序）
        name: item?.file_name || payload?.document_title || payload?.document?.title || item?.document_title || item?.input_id || `第${index + 1}篇文献`,
        payload,
      }
    })
  }
  // 单文件响应 data 无 file_name；后端 _vue_public_response 单文件分支把 file_name 放在 meta
  const singleFileName = response?.meta?.file_name || data?.input?.file_name || data?.file_name
  return [{ index: 0, status: 'success', name: singleFileName || data?.document_title || data?.document?.title || '当前文献', payload: data }]
}

function entityText(value) {
  if (value && typeof value === 'object') return value.text || value.name || value.label || value.value || value.entity || '—'
  return value || '—'
}

function positionLabel(item) {
  return resultPositionLabel(item)
}

function renderDomainClassification(response) {
  const responseData = dataOf(response)
  const responseDomainValue = response?.meta?.selected_domain
    ?? responseData.selected_domain
    ?? responseData.professional_domain
  const responseDomain = typeof responseDomainValue === 'string'
    ? { name: responseDomainValue }
    : object(responseDomainValue)
  const sourceRecords = recordsOf(response)
  const records = sourceRecords.map(record => {
    const payload = record.payload
    const sourceClassifications = array(payload.multilevel_classification_results).length
      ? array(payload.multilevel_classification_results)
      : array(payload.classifications)
    const primaryClassification = sourceClassifications.find(item => ['main', 'primary'].includes(String(item.role || '').toLowerCase())) || sourceClassifications[0]
    const classifications = primaryClassification ? [{ ...primaryClassification, role: 'main' }] : []
    const overall = number(payload.classification_confidence?.overall ?? classifications[0]?.confidence)
    const selectedDomainValue = payload.domain_match_result?.selected_domain
      ?? payload.selected_domain
      ?? payload.professional_domain
      ?? responseDomain
    const selectedDomain = typeof selectedDomainValue === 'string'
      ? { name: selectedDomainValue }
      : object(selectedDomainValue)
    const match = {
      ...object(payload.domain_match_result),
      status: payload.domain_match_result?.status || (overall >= 0.75 ? 'matched' : 'low_confidence'),
      match_score: payload.domain_match_result?.match_score ?? overall,
      selected_domain: Object.keys(selectedDomain).length ? selectedDomain : { name: '未提供目标领域' },
    }
    const candidateSources = [primaryClassification, ...array(payload.candidate_classifications), ...sourceClassifications].filter(Boolean)
    const pathKeyOf = (item) => {
      const p = array(item?.classification_path)
      return p.length ? p.join('>') : [item?.level_1, item?.level_2, item?.level_3].filter(Boolean).join('>')
    }
    const candidateKeys = new Set()
    const candidates = candidateSources.flatMap((item, index) => {
      const classificationPath = array(item.classification_path).length
        ? item.classification_path
        : [item.level_1, item.level_2, item.level_3].filter(Boolean)
      const key = classificationPath.join(' > ') || item.candidate_id || item.label || `${index}`
      if (!key || candidateKeys.has(key)) return []
      candidateKeys.add(key)
      return [{ ...item, candidate_id: item.candidate_id || `domain_candidate_${candidateKeys.size}`, classification_path: classificationPath }]
    })
    // 与 zh/en-classify 一致：候选只列置信度 ≥0.8 且非当前首选的替代分类；当前首选已在主表展示、
    // 不再进下拉。无替代候选的文献已是正式结果并入库，不进候选确认区、无需人工确认。
    const primaryPathKey = pathKeyOf(primaryClassification)
    const confirmableCandidates = candidates.filter(c =>
      pathKeyOf(c) !== primaryPathKey && number(c.confidence) >= 0.8)
    return { ...record, classifications, match, candidates, confirmableCandidates, labels: array(payload.domain_labels), confirmation: object(payload.manual_confirmation) }
  })
  const successful = records.filter(record => record.status !== 'failed' && record.classifications.length)
  if (!successful.length) return '<div class="domain-classify-empty-v669">当前结果为空、领域匹配失败或缺少有效分类字段，无法生成结构化展示。</div>'

  const matched = successful.filter(record => record.match.status === 'matched').length
  const level2Count = new Set(successful.flatMap(record => record.classifications.map(item => item.level_2).filter(Boolean))).size
  // 与 zh/en-classify 一致：只把"有 ≥0.8 替代候选"的文献放进候选确认区；只有当前首选、无替代
  // 候选的文献已是正式结果并入库，不在候选区出现空占位、无需人工确认。summary 的"待人工确认"
  // 因此只统计这类真正待确认的文献（有替代候选且未确认），没有则显示 0（不再像旧版把所有
  // 非已确认记录都算成"待确认"，那会把只有当前首选、无需确认的文献也计入，数字虚高且误导）。
  const confirmableRecords = successful.filter(record => record.confirmableCandidates.length > 0)
  const pendingCount = confirmableRecords.filter(record => record.confirmation.status !== 'confirmed').length
  const summary = [['文献数量', records.length], ['领域匹配', `${matched}/${successful.length}`], ['二级类目', level2Count], ['待人工确认', pendingCount]]

  const detailRows = successful.map(record => {
    const item = record.classifications[0]
    const low = record.match.status !== 'matched'
    const labels = record.labels.map(label => `<span class="domain-classify-domain-tag-v669">${escapeHtml(label.label || label)}</span>`).join('')
    return `<tr class="viz-record-start"><td>${renderTextWithMath(record.name)}</td><td>${escapeHtml(record.match.selected_domain?.name || '未提供目标领域')}</td><td><span class="domain-classify-match-badge-v669 ${low ? 'low' : ''}">${low ? '低置信匹配' : '领域匹配'}</span><br>${record.match.match_score == null ? '—' : `${(number(record.match.match_score) * 100).toFixed(1)}%`}</td><td><b>${escapeHtml(item.level_1 || '—')}</b><br>${escapeHtml(item.level_2 || '—')}<br>${escapeHtml(item.level_3 || '—')}</td><td>${confidence(item.confidence)}</td><td><div class="domain-classify-domain-list-v669">${labels || '—'}</div></td></tr>`
  }).join('')

  const level2 = new Map()
  const level3 = new Map()
  successful.forEach(record => record.classifications.forEach(item => {
    if (item.level_2) level2.set(item.level_2, (level2.get(item.level_2) || 0) + 1)
    if (item.level_3) level3.set(item.level_3, (level3.get(item.level_3) || 0) + 1)
  }))
  const distributionRows = [
    ...[...level2.entries()].map(([category, count]) => ({ level: '二级', category, count })),
    ...[...level3.entries()].map(([category, count]) => ({ level: '三级', category, count })),
  ]

  // confirmableRecords 已在上方 summary 处计算（有 ≥0.8 替代候选的文献）。候选确认区只渲染
  // 这些记录；全无则整块不渲染（与 zh/en 一致）。
  const confirmationItems = confirmableRecords.map(record => {
    const primary = record.classifications[0] || {}
    const primaryLabel = array(primary.classification_path).join(' > ') || primary.label || '当前首选'
    // 占位 option（当前首选）：不可选、点开列表隐藏，末尾带主分类置信度（与 zh/en 一致）
    const placeholder = `<option value="" disabled selected hidden>当前首选 · ${escapeHtml(primaryLabel)}｜${confidence(primary.confidence)}</option>`
    const options = record.confirmableCandidates.map((candidate, index) => `<option value="${escapeHtml(candidate.candidate_id || '')}" data-primary="${escapeHtml(candidate.classification_code || candidate.clc_code || '')}">候选 ${index + 1} · ${escapeHtml(array(candidate.classification_path).join(' > ') || candidate.label || '未提供分类路径')}｜${confidence(candidate.confidence)}</option>`).join('')
    return `<div class="domain-classify-confirm-item-v669" data-record-index="${record.index}"><div class="domain-classify-confirm-name-v669">${renderTextWithMath(record.name)}</div><select class="domain-classify-confirm-select-v669" data-viz-confirm-select="${record.index}">${placeholder}${options}</select><div class="domain-classify-confirm-actions-v669"><button type="button" class="domain-classify-confirm-btn-v669 primary" data-viz-confirm="${record.index}" data-viz-confirm-record="${escapeHtml(record.record_id || '')}" data-viz-confirm-label="确认所选分类">确认所选分类</button></div></div>`
  }).join('')

  return `<div class="domain-classify-visual-v669" data-viz-confirm-root>${`<div class="domain-classify-summary-grid-v669">${summary.map(([label, value]) => `<div class="domain-classify-summary-item-v669"><div class="domain-classify-summary-value-v669">${escapeHtml(value)}</div><div class="domain-classify-summary-label-v669">${label}</div></div>`).join('')}</div>`}<div class="domain-classify-result-card-v669"><div class="domain-classify-result-title-v669">专业领域多层级分类结果</div><div class="domain-classify-result-table-wrap-v669"><table class="domain-classify-result-table-v669"><thead><tr><th style="width:18%">文献</th><th style="width:13%">目标领域</th><th style="width:12%">领域匹配</th><th>一级 / 二级 / 三级分类</th><th style="width:11%">置信度</th><th style="width:16%">领域标签</th></tr></thead><tbody>${detailRows}</tbody></table></div></div><div class="domain-classify-result-card-v669"><div class="domain-classify-result-title-v669">数据分布报告</div><div class="domain-classify-result-table-wrap-v669"><table class="domain-classify-result-table-v669"><thead><tr><th style="width:14%">分类层级</th><th>专业类目</th><th style="width:18%">文献数量</th></tr></thead><tbody>${distributionRows.map(row => `<tr><td>${row.level}</td><td>${escapeHtml(row.category)}</td><td>${row.count}</td></tr>`).join('')}</tbody></table></div></div>${confirmationItems ? `<div class="domain-classify-result-card-v669"><div class="domain-classify-result-title-v669">候选分类与人工确认</div><div class="domain-classify-confirm-list-v669">${confirmationItems}</div><div class="domain-classify-note-v669">候选仅列置信度高于0.8的替代分类（不含当前首选），按置信度从高到低排列；当前首选已是正式结果并入库，无需确认。确认某候选后由后端同步替换结果并保存审核记录，原首选会作为候选回到下拉、可反复切换。</div></div>` : ''}</div>`
}

function relationTriples(response) {
  return recordsOf(response).flatMap(record => array(record.payload.relation_triples ?? record.payload.triples ?? record.payload.relations ?? record.payload.relation_results))
}

function entityType(value) {
  return value && typeof value === 'object' ? value.type || value.entity_type || '实体' : '实体'
}

function buildRelationNetwork(triples) {
  const nodeMap = new Map()
  triples.forEach((triple, tripleIndex) => {
    const entities = [triple.subject ?? triple.source ?? triple.head, triple.object ?? triple.target ?? triple.tail]
    entities.forEach((entity, entityIndex) => {
      const name = entityText(entity)
      if (!name || name === '—' || nodeMap.has(name)) return
      nodeMap.set(name, {
        node_id: entity?.entity_id || entity?.id || `NODE_${String(nodeMap.size + 1).padStart(3, '0')}`,
        name,
        type: entityType(entity),
        source_index: `${tripleIndex}-${entityIndex}`,
      })
    })
  })
  return {
    nodes: [...nodeMap.values()],
    edges: triples.map((triple, index) => ({
      edge_id: triple.edge_id || `EDGE_${String(index + 1).padStart(3, '0')}`,
      source: entityText(triple.subject ?? triple.source ?? triple.head),
      target: entityText(triple.object ?? triple.target ?? triple.tail),
      relation: entityText(triple.relation ?? triple.predicate ?? triple.type),
      relation_code: triple.relation?.code || triple.relation_code || '',
      confidence: triple.confidence,
    })),
  }
}

function relationNodePalette(type) {
  const value = String(type || '')
  if (/人名|人物|PERSON/i.test(value)) return ['#eef3ff', '#6f8fd8', '#315efb']
  if (/机构|组织|ORGANIZATION/i.test(value)) return ['#fff5e8', '#d5a45c', '#9a5b00']
  if (/地名|地点|LOCATION/i.test(value)) return ['#eaf8f1', '#64aa87', '#087443']
  if (/事件|EVENT/i.test(value)) return ['#faedf8', '#bf76b2', '#8a2d7a']
  if (/方法|治疗|METHOD|TREATMENT/i.test(value)) return ['#eef3ff', '#6f8fd8', '#315efb']
  if (/数据|结果|DATA|RESULT/i.test(value)) return ['#eaf8f1', '#64aa87', '#087443']
  if (/设备|DEVICE/i.test(value)) return ['#fff4e3', '#d6a257', '#8a4b00']
  if (/理论|原理|规律|现象|THEORY|PHENOMENON/i.test(value)) return ['#f4f0ff', '#9b7ad5', '#6941c6']
  if (/药物|疾病|症状|DRUG|DISEASE|SYMPTOM/i.test(value)) return ['#fcecf2', '#cf7797', '#a12d58']
  if (/化合物|CHEMICAL/i.test(value)) return ['#eaf8f1', '#64aa87', '#087443']
  return ['#f3f6fa', '#8ea0b9', '#52627a']
}

function connectedComponents(nodes, edges) {
  const adjacency = new Map(nodes.map(node => [node.name, new Set()]))
  edges.forEach(edge => {
    adjacency.get(edge.source)?.add(edge.target)
    adjacency.get(edge.target)?.add(edge.source)
  })
  const visited = new Set()
  const components = []
  nodes.forEach(node => {
    if (visited.has(node.name)) return
    const queue = [node.name]
    const names = []
    visited.add(node.name)
    while (queue.length) {
      const current = queue.shift()
      names.push(current)
      ;(adjacency.get(current) || []).forEach(next => {
        if (!visited.has(next)) {
          visited.add(next)
          queue.push(next)
        }
      })
    }
    const namesSet = new Set(names)
    components.push({
      nodes: nodes.filter(item => namesSet.has(item.name)),
      edges: edges.filter(edge => namesSet.has(edge.source) && namesSet.has(edge.target)),
    })
  })
  return components.sort((a, b) => b.nodes.length - a.nodes.length)
}

function componentLevels(component) {
  const outgoing = new Map(component.nodes.map(node => [node.name, []]))
  const incoming = new Map(component.nodes.map(node => [node.name, []]))
  component.edges.forEach(edge => {
    outgoing.get(edge.source)?.push(edge.target)
    incoming.get(edge.target)?.push(edge.source)
  })
  const root = [...component.nodes].sort((a, b) => {
    const scoreA = (outgoing.get(a.name)?.length || 0) * 3 - (incoming.get(a.name)?.length || 0)
    const scoreB = (outgoing.get(b.name)?.length || 0) * 3 - (incoming.get(b.name)?.length || 0)
    return scoreB - scoreA
  })[0]
  const levels = new Map([[root.name, 0]])
  const queue = [root.name]
  while (queue.length) {
    const current = queue.shift()
    const nextLevel = (levels.get(current) || 0) + 1
    ;[...(outgoing.get(current) || []), ...(incoming.get(current) || [])].forEach(next => {
      if (!levels.has(next)) {
        levels.set(next, nextLevel)
        queue.push(next)
      }
    })
  }
  component.nodes.forEach(node => {
    if (!levels.has(node.name)) levels.set(node.name, 0)
  })
  return { root, levels }
}

function layoutRelationNetwork(nodes, edges) {
  const components = connectedComponents(nodes, edges)
  const width = 1500
  const columns = components.length > 1 ? 2 : 1
  const padding = 24
  const gap = 28
  const clusterWidth = columns === 2 ? (width - padding * 2 - gap) / 2 : width - padding * 2
  const columnBottoms = new Array(columns).fill(padding)
  const positionedNodes = []
  const positionedEdges = []
  const clusters = []
  components.forEach(component => {
    const { root, levels } = componentLevels(component)
    const buckets = new Map()
    component.nodes.forEach(node => {
      const level = Math.min(levels.get(node.name) || 0, 3)
      if (!buckets.has(level)) buckets.set(level, [])
      buckets.get(level).push(node)
    })
    const keys = [...buckets.keys()].sort((a, b) => a - b)
    const largest = Math.max(1, ...keys.map(key => buckets.get(key).length))
    const clusterHeight = Math.max(250, 94 + largest * 90)
    const column = columnBottoms.indexOf(Math.min(...columnBottoms))
    const left = padding + column * (clusterWidth + gap)
    const top = columnBottoms[column]
    columnBottoms[column] += clusterHeight + 28
    const local = new Map()
    const leftX = left + 100
    const rightX = left + clusterWidth - 100
    const levelDivisor = Math.max(1, keys.length - 1)
    keys.forEach((key, levelIndex) => {
      const items = buckets.get(key)
      const x = leftX + (rightX - leftX) * (levelIndex / levelDivisor)
      const topY = top + 72
      const bottomY = top + clusterHeight - 36
      const available = bottomY - topY
      items.forEach((node, itemIndex) => {
        const y = items.length === 1 ? topY + available / 2 : topY + available * (itemIndex / (items.length - 1))
        const positioned = { ...node, x, y, width: 168, height: 58, isRoot: node.name === root.name }
        local.set(node.name, positioned)
        positionedNodes.push(positioned)
      })
    })
    component.edges.forEach((edge, edgeIndex) => {
      const sourceNode = local.get(edge.source)
      const targetNode = local.get(edge.target)
      if (sourceNode && targetNode) positionedEdges.push({ ...edge, sourceNode, targetNode, edgeIndex })
    })
    clusters.push({ left, top, width: clusterWidth, height: clusterHeight, title: root.name, nodeCount: component.nodes.length, edgeCount: component.edges.length })
  })
  return { width, height: Math.max(340, Math.max(...columnBottoms) + 6), nodes: positionedNodes, edges: positionedEdges, clusters }
}

function truncateRelationLabel(value, maxLength = 18) {
  const text = String(value || '')
  return text.length > maxLength ? `${text.slice(0, maxLength - 1)}…` : text
}

function renderRelationNetwork(network) {
  const nodes = array(network.nodes)
  const edges = array(network.edges)
  if (!nodes.length) return '<div class="relation-network-wrap"><div class="relation-network-head"><div class="relation-network-title">科研实体知识图谱</div></div><div class="relation-network-empty">暂无可展示的知识图谱。</div></div>'
  const layout = layoutRelationNetwork(nodes, edges)
  const clusterSvg = layout.clusters.map(cluster => `<g><rect class="relation-network-cluster" x="${cluster.left}" y="${cluster.top}" width="${cluster.width}" height="${cluster.height}" rx="18"/><text class="relation-network-cluster-title" x="${cluster.left + 18}" y="${cluster.top + 28}">${escapeHtml(truncateRelationLabel(cluster.title, 26))}</text><text class="relation-network-cluster-meta" x="${cluster.left + cluster.width - 18}" y="${cluster.top + 28}">${cluster.nodeCount}节点 · ${cluster.edgeCount}关系</text></g>`).join('')
  const edgeSvg = layout.edges.map((edge, index) => {
    const source = edge.sourceNode
    const target = edge.targetNode
    const direction = target.x >= source.x ? 1 : -1
    const startX = source.x + direction * source.width / 2
    const endX = target.x - direction * target.width / 2
    const distance = Math.max(60, Math.abs(endX - startX))
    const control = Math.max(42, distance * .45)
    const labelX = (startX + endX) / 2
    const labelY = (source.y + target.y) / 2 + (source.y <= target.y ? -18 : 18) + (index % 2 ? 6 : -6)
    const labelWidth = Math.max(58, Math.min(132, String(edge.relation || '').length * 14 + 20))
    return `<path class="relation-network-edge" d="M ${startX} ${source.y} C ${startX + direction * control} ${source.y}, ${endX - direction * control} ${target.y}, ${endX} ${target.y}" marker-end="url(#relationArrowV612)"/><g><rect class="relation-network-edge-label-bg" x="${labelX - labelWidth / 2}" y="${labelY - 12}" width="${labelWidth}" height="24" rx="12"/><text class="relation-network-edge-label" x="${labelX}" y="${labelY}">${escapeHtml(edge.relation)}</text></g>`
  }).join('')
  const nodeSvg = layout.nodes.map(node => {
    const [fill, stroke, accent] = relationNodePalette(node.type)
    const x = node.x - node.width / 2
    const y = node.y - node.height / 2
    return `<g class="relation-network-node-group"><rect class="relation-network-node" x="${x}" y="${y}" width="${node.width}" height="${node.height}" rx="12" fill="${fill}" stroke="${stroke}" stroke-width="${node.isRoot ? 2.4 : 1.5}"/><rect x="${x}" y="${y}" width="6" height="${node.height}" rx="3" fill="${accent}"/><text class="relation-network-node-text" x="${node.x + 3}" y="${node.y - 5}">${escapeHtml(truncateRelationLabel(node.name))}</text><text class="relation-network-node-type" x="${node.x + 3}" y="${node.y + 15}">${escapeHtml(node.type || '实体')}</text><title>${escapeHtml(node.name)} · ${escapeHtml(node.type || '实体')}</title></g>`
  }).join('')
  const typeLegend = [...new Set(nodes.map(node => node.type || '实体'))].map(type => `<span class="relation-network-legend-item"><span class="relation-network-legend-dot" style="background:${relationNodePalette(type)[2]}"></span>${escapeHtml(type)}</span>`).join('')
  const edgeList = edges.map(edge => `<div class="relation-network-list-item"><span>${renderTextWithMath(edge.source)}</span><span class="relation-triple-edge">${renderTextWithMath(edge.relation)}</span><span>${renderTextWithMath(edge.target)}</span></div>`).join('')
  return `<div class="relation-network-wrap"><div class="relation-network-head"><div><div class="relation-network-title">科研实体知识图谱</div><div class="relation-network-meta">连通分量分区 · 分层防碰撞布局 · 曲线有向边</div></div><div class="relation-network-meta">${nodes.length} 个节点 · ${edges.length} 条关系边</div></div><div class="relation-network-legend">${typeLegend}</div><div class="relation-network-canvas"><svg class="relation-network-svg" viewBox="0 0 ${layout.width} ${layout.height}" role="img" aria-label="实体关系知识图谱，使用分层防碰撞布局"><defs><marker id="relationArrowV612" markerWidth="9" markerHeight="9" refX="8" refY="4.5" orient="auto"><path d="M0,0 L9,4.5 L0,9 Z" fill="#8fa0b8"/></marker></defs>${clusterSvg}${edgeSvg}${nodeSvg}</svg></div><details class="relation-network-details"><summary>查看全部关系边列表</summary><div class="relation-network-list">${edgeList}</div></details></div>`
}

function buildRdf(triples) {
  const base = 'https://example.org/semantic-toolkit/'
  const uri = value => encodeURIComponent(String(value || 'entity').trim().replace(/\s+/g, '_'))
  const literal = value => String(value ?? '').replace(/\\/g, '\\\\').replace(/"/g, '\\"').replace(/\r?\n/g, '\\n')
  const content = `@prefix ent: <${base}entity/> .\n@prefix rel: <${base}relation/> .\n@prefix ex: <${base}> .\n@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .\n@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n\n` + triples.map((triple, index) => {
    const subject = entityText(triple.subject ?? triple.source ?? triple.head)
    const relation = entityText(triple.relation ?? triple.predicate ?? triple.type)
    const objectValue = entityText(triple.object ?? triple.target ?? triple.tail)
    const subjectUri = `${base}entity/${uri(subject)}`
    const predicateUri = `${base}relation/${uri(triple.relation?.code || relation)}`
    const objectUri = `${base}entity/${uri(objectValue)}`
    return `<${subjectUri}> rdfs:label "${literal(subject)}" ;\n  <${predicateUri}> <${objectUri}> .\n<${objectUri}> rdfs:label "${literal(objectValue)}" .\n_:statement${index + 1} a rdf:Statement ;\n  rdf:subject <${subjectUri}> ;\n  rdf:predicate <${predicateUri}> ;\n  rdf:object <${objectUri}> ;\n  ex:evidence "${literal(triple.context || triple.evidence || triple.sentence || '')}" ;\n  ex:confidence "${triple.confidence ?? ''}"^^xsd:decimal .`
  }).join('\n\n')
  return { base, content, count: triples.length }
}

function renderRelations(response) {
  const data = dataOf(response)
  const records = recordsOf(response)
  const triples = relationTriples(response)
  const dependencies = records.flatMap(record => array(record.payload.dependency_parse ?? record.payload.dependencies ?? record.payload.dependency_analysis?.dependencies))
  const returnedPaths = records.flatMap(record => array(record.payload.dependency_paths))
  const dependencyPaths = returnedPaths.length
    ? returnedPaths
    : triples.filter(item => item.dependency_path).map((item, index) => ({ triple_id: item.triple_id || item.id || `T${index + 1}`, path: item.dependency_path }))
  const summary = object(data.summary ?? records[0]?.payload?.summary)
  const returnedNetwork = object(data.knowledge_network ?? data.network ?? records[0]?.payload?.knowledge_network ?? records[0]?.payload?.network)
  const network = array(returnedNetwork.nodes).length ? returnedNetwork : buildRelationNetwork(triples)
  const nodes = array(network.nodes)
  const rdf = buildRdf(triples)
  const summaryItems = [
    ['关系三元组', summary.triple_count ?? triples.length],
    ['实体对', summary.entity_pair_count ?? new Set(triples.map(item => `${entityText(item.subject ?? item.source ?? item.head)}|${entityText(item.object ?? item.target ?? item.tail)}`)).size],
    ['关系类型', summary.relation_type_count ?? new Set(triples.map(item => entityText(item.relation ?? item.predicate ?? item.type))).size],
    ['涉及实体', summary.entity_count ?? nodes.length],
  ]
  const summaryHtml = `<div class="relation-summary-grid">${summaryItems.map(([label, value]) => `<div class="distribution-summary-item"><div class="distribution-summary-value">${escapeHtml(value)}</div><div class="distribution-summary-label">${label}</div></div>`).join('')}</div>`
  const tripleRows = triples.map((item, index) => `<tr class="relation-main-row"><td><span class="distribution-level-tag">${escapeHtml(item.triple_id || item.id || `T${index + 1}`)}</span></td><td><div class="relation-entity-text">${renderTextWithMath(entityText(item.subject ?? item.source ?? item.head))}</div></td><td><span class="relation-label-badge">${renderTextWithMath(entityText(item.relation ?? item.predicate ?? item.type))}</span></td><td><div class="relation-entity-text">${renderTextWithMath(entityText(item.object ?? item.target ?? item.tail))}</div></td><td>${escapeHtml(positionLabel(item))}</td><td>${confidence(item.confidence)}</td><td><button class="relation-detail-btn" data-viz-detail="relation-detail-${index}">查看详情</button></td></tr><tr id="relation-detail-${index}" class="relation-detail-row" hidden><td class="relation-detail-cell" colspan="7"><div class="relation-detail-content"><div class="relation-detail-label">关系三元组</div><div class="relation-detail-value"><div class="relation-triple-line"><span class="relation-triple-node">${renderTextWithMath(entityText(item.subject ?? item.source ?? item.head))}</span><span class="relation-triple-edge">${renderTextWithMath(entityText(item.relation ?? item.predicate ?? item.type))}</span><span class="relation-triple-node">${renderTextWithMath(entityText(item.object ?? item.target ?? item.tail))}</span></div></div><div class="relation-detail-label">关系触发词</div><div class="relation-detail-value">${renderTextWithMath(item.relation?.trigger || item.relation_trigger || '—')}</div><div class="relation-detail-label">上下文证据</div><div class="relation-detail-value">${renderTextWithMath(item.context || item.evidence || item.sentence || '—')}</div><div class="relation-detail-label">依存路径</div><div class="relation-detail-value"><div class="relation-dependency-path">${escapeHtml(item.dependency_path || '未返回')}</div></div></div></td></tr>`).join('') || '<tr><td colspan="7">未识别到达到阈值的实体关系三元组。</td></tr>'
  const pathItems = dependencyPaths.map(item => `<li><b>${escapeHtml(item.triple_id || '关系路径')}</b><span>${escapeHtml(item.path || item.dependency_path || '—')}</span></li>`).join('')
  const dependencyPanel = `<div class="relation-dependency-result">${pathItems ? `<div class="relation-dependency-result-head"><div><b>实体关系依存路径</b><span>由实体关系识别工具内部自动生成</span></div><strong>${dependencyPaths.length} 条路径</strong></div><div class="relation-dependency-paths"><ul>${pathItems}</ul></div>` : '<div class="relation-dependency-result-head"><div><b>实体关系依存路径</b></div><span>暂无依存路径</span></div>'}</div>`

  return `<div class="relation-result-root" data-viz-group>${summaryHtml}<div class="relation-result-header"><div class="relation-tabs"><button class="relation-tab-btn" data-relation-tab="triples">关系三元组</button><button class="relation-tab-btn" data-relation-tab="dependency">依存路径</button><button class="relation-tab-btn active" data-relation-tab="network">知识图谱</button><button class="relation-tab-btn" data-relation-tab="rdf">RDF表示</button></div><div class="relation-export-actions"></div></div><div class="relation-tab-panel" data-relation-panel="triples" hidden><div class="distribution-table-wrap"><table class="distribution-table relation-results-table"><thead><tr><th>编号</th><th>主体实体</th><th>关系类型</th><th>客体实体</th><th>句子位置</th><th>置信度</th><th>操作</th></tr></thead><tbody>${tripleRows}</tbody></table></div></div><div class="relation-tab-panel" data-relation-panel="dependency" hidden>${dependencyPanel}</div><div class="relation-tab-panel" data-relation-panel="network">${renderRelationNetwork(network)}</div><div class="relation-tab-panel" data-relation-panel="rdf" hidden><div class="relation-rdf-card-v699"><div class="relation-rdf-toolbar-v699"><div class="relation-rdf-meta-v699">TURTLE · ${rdf.count} 条关系 · 命名空间 ${escapeHtml(rdf.base)}</div></div><pre class="relation-rdf-preview-v699">${escapeHtml(rdf.content || '暂无可序列化的关系三元组。')}</pre></div></div></div>`
}

const clusterColors = ['#4776b3', '#5e9b8a', '#9a72b0', '#c7864d', '#b95f68']

function renderDeepCluster(response) {
  const data = dataOf(response)
  const clusters = array(data.clusters)
  const points = array(data.semantic_projection)
  const quality = object(data.clustering_quality)
  const trend = object(data.theme_trend_analysis)
  const evaluation = object(data.training_evaluation)
  const metrics = object(evaluation.metrics)
  const colorMap = Object.fromEntries(clusters.map((cluster, index) => [cluster.cluster_id, clusterColors[index % clusterColors.length]]))
  const maxTrend = Math.max(1, ...array(trend.series).flatMap(item => array(item.yearly_counts).map(number)))
  const clusterIdentity = item => {
    // 类目分布名优先（锚定体系的人工类目），无分布的簇回退代表短语
    const names = array(item?.category_distribution).slice(0, 2).map(x => x?.name).filter(Boolean)
    if (names.length) return names.join(' / ')
    return array(item?.representative_terms).slice(0, 2).join(' / ')
  }
  const describeCluster = clusterId => {
    const item = array(trend.series).find(row => row.cluster_id === clusterId)
    const label = clusterIdentity(item)
    return clusterId ? `${clusterId}${label ? ` · ${label}` : ''}` : '—'
  }
  const projection = `<div class="deep-cluster-projection-card"><div class="deep-cluster-panel-title">二维语义投影</div><svg class="deep-cluster-projection-svg" viewBox="0 0 800 310" role="img" aria-label="文献语义聚类投影"><line x1="35" y1="285" x2="770" y2="285" stroke="#d8e0ea"/><line x1="35" y1="20" x2="35" y2="285" stroke="#d8e0ea"/>${points.map(point => `<g><circle cx="${number(point.x) * 7.3 + 35}" cy="${number(point.y) * 2.7 + 20}" r="6" fill="${colorMap[point.cluster_id] || '#6b7c93'}" opacity=".92"><title>${escapeHtml(point.document_id)} · ${escapeHtml(point.title)}</title></circle><text x="${number(point.x) * 7.3 + 44}" y="${number(point.y) * 2.7 + 24}" font-size="9.5" fill="#53657c">${escapeHtml(point.document_id)}</text></g>`).join('')}</svg><div class="deep-cluster-legend">${clusters.map((cluster, index) => `<span class="deep-cluster-legend-item"><i class="deep-cluster-legend-dot" style="background:${clusterColors[index % clusterColors.length]}"></i>${escapeHtml(cluster.cluster_id)}</span>`).join('')}</div></div>`
  const clusterCards = `<div class="deep-cluster-cards">${clusters.map(cluster => { const stats = object(cluster.feature_statistics); const distribution = array(cluster.category_distribution); const identityChips = distribution.length ? distribution.map(item => `<span class="deep-cluster-term">${escapeHtml(item.name)}<small style="color:#7a889b;font-size:.85em"> ×${number(item.count)}</small></span>`) : array(cluster.representative_terms).map(term => `<span class="deep-cluster-term">${renderTextWithMath(term)}</span>`); return `<div class="deep-cluster-card"><div class="deep-cluster-card-head"><div class="deep-cluster-card-title">${escapeHtml(cluster.topic_name && cluster.topic_name !== cluster.cluster_id ? `${cluster.cluster_id} · ${escapeHtml(cluster.topic_name)}` : cluster.cluster_id)}</div><div class="deep-cluster-card-size">${number(cluster.size)} 篇 · ${(number(cluster.ratio) * 100).toFixed(1)}%</div></div><div class="deep-cluster-term-row">${(distribution.length ? '<small style="width:100%;color:#8a96a6;font-size:11px;margin-bottom:2px">候选类目（簇内成员锚定与双候选票数；未锚定簇显示代表短语）</small>' : '')}${identityChips.join('')}</div>${[['类内相似度', stats.intra_cluster_similarity], ['类间分离度', stats.inter_cluster_separation], ['语义密度', stats.semantic_density]].map(([label, value]) => `<div class="deep-cluster-stat-row"><span>${label}</span><i class="deep-cluster-stat-track"><b class="deep-cluster-stat-fill" style="width:${number(value) * 100}%"></b></i><strong>${fixed(value)}</strong></div>`).join('')}<div class="deep-cluster-doc-links"><b>代表文献：</b>${array(cluster.representative_documents).map(doc => `${escapeHtml(doc.document_id)} ${renderTextWithMath(doc.title)}`).join('；') || '—'}</div></div>` }).join('')}</div>`
  const assignments = `<div class="deep-cluster-table-wrap"><table><thead><tr><th>文献编号</th><th>文献标题</th><th>年份</th><th>所属类簇</th><th>中心相似度</th><th>归类依据</th></tr></thead><tbody>${array(data.document_assignments).map(item => `<tr><td><code>${escapeHtml(item.document_id)}</code></td><td>${renderTextWithMath(item.title)}</td><td>${escapeHtml(item.publication_year)}</td><td>${escapeHtml(item.cluster_id)}</td><td>${fixed(item.similarity_to_centroid, 3)}</td><td>${renderTextWithMath(item.key_evidence)}</td></tr>`).join('') || '<tr><td colspan="6">暂无文献归属数据。</td></tr>'}</tbody></table></div>`
  const trends = `<div class="deep-cluster-trend-insights"><div class="deep-cluster-insight"><b>上升类簇</b><span>${renderTextWithMath(describeCluster(trend.rising_cluster_id))}</span></div><div class="deep-cluster-insight"><b>新兴类簇</b><span>${renderTextWithMath(describeCluster(trend.emerging_cluster_id))}</span></div><div class="deep-cluster-insight"><b>稳定类簇</b><span>${renderTextWithMath(describeCluster(trend.stable_cluster_id))}</span></div></div><div class="deep-cluster-trend-card"><div class="deep-cluster-panel-title">类簇年度分布</div><div class="deep-cluster-year-header"><span>类簇编号 / 候选类目</span>${array(trend.years).map(year => `<span>${year}</span>`).join('')}</div>${array(trend.series).map((item, index) => `<div class="deep-cluster-trend-row"><div class="deep-cluster-trend-label"><i class="deep-cluster-legend-dot" style="display:inline-block;background:${clusterColors[index % clusterColors.length]};margin-right:6px"></i><b>${escapeHtml(item.cluster_id)}</b><small style="display:block;margin-left:18px;color:#7a889b">${renderTextWithMath(clusterIdentity(item))}</small></div>${array(item.yearly_counts).map(value => `<div class="deep-cluster-trend-cell"><span>${value}</span><i class="deep-cluster-trend-bar" style="height:${Math.max(3, number(value) / maxTrend * 58)}px;background:${clusterColors[index % clusterColors.length]}"></i></div>`).join('')}</div>`).join('')}</div><div class="deep-cluster-method-note"><b>趋势判断：</b>${renderTextWithMath(trend.summary || '')}</div>`
  const correction = `<div class="deep-cluster-correction-layout-v704"><div class="deep-cluster-correction-card-v704"><h4>评测摘要</h4><div class="deep-cluster-evidence-summary-v704">${[['轮廓系数', metrics.silhouette_score], ['NMI', metrics.normalized_mutual_information], ['ARI', metrics.adjusted_rand_index], ['专家一致率', metrics.expert_agreement]].map(([label, value]) => `<div class="deep-cluster-evidence-stat-v704"><strong>${fixed(value, 3)}</strong><span>${label}</span></div>`).join('')}</div><div class="deep-cluster-evidence-note-v704">${renderTextWithMath(evaluation.notice || '')}</div></div><div class="deep-cluster-correction-card-v704"><h4>人工校正操作</h4><div class="deep-cluster-correction-grid-v704"><div class="field"><label>选择文献</label><select class="select" data-correction-document>${array(data.document_assignments).map(row => `<option value="${escapeHtml(row.document_id)}" data-cluster="${escapeHtml(row.cluster_id)}">${escapeHtml(row.document_id)} · ${renderTextWithMath(row.title)}</option>`).join('')}</select></div><div class="field"><label>目标类簇</label><select class="select" data-correction-target>${clusters.map(row => `<option value="${escapeHtml(row.cluster_id)}">${escapeHtml(row.cluster_id)}</option>`).join('')}</select></div><div class="field full"><label>校正理由</label><input class="input" data-correction-reason placeholder="填写人工判定依据或专家意见"/></div></div><div class="deep-cluster-correction-actions-v704"><button class="outline-btn" type="button" data-correction-action="move">移动文献</button><button class="outline-btn" type="button" data-correction-action="merge">合并类簇</button><button class="outline-btn" type="button" data-correction-action="split">拆分类簇</button><button class="primary-btn" type="button" data-correction-submit>提交校正反馈</button></div><div class="deep-cluster-correction-status-v704" data-correction-status>尚未记录人工校正。</div></div></div><div class="deep-cluster-correction-card-v704" style="margin-top:12px"><h4>人工修正记录</h4><div class="deep-cluster-correction-log-v704"><table class="deep-cluster-evidence-table-v704"><thead><tr><th>序号</th><th>操作</th><th>对象</th><th>目标</th><th>理由</th><th>状态</th></tr></thead><tbody data-correction-log><tr><td colspan="6" style="text-align:center;color:#8a96a6">暂无校正记录</td></tr></tbody></table></div></div>`
  return `<div class="deep-cluster-result-root" data-viz-group><div class="deep-cluster-result-use-v704"><span>结果与接口响应保持一致，可复制结构化结果或下载文献归属表。</span><div class="deep-cluster-result-use-actions-v704"></div></div><div class="deep-cluster-summary-grid"><div class="deep-cluster-summary-card"><div class="deep-cluster-summary-label">输入文献</div><div class="deep-cluster-summary-value">${data.input_summary?.document_count || 0}<span class="deep-cluster-summary-unit">篇</span></div></div><div class="deep-cluster-summary-card"><div class="deep-cluster-summary-label">句子特征</div><div class="deep-cluster-summary-value">${data.input_summary?.parsed_sentence_count || 0}<span class="deep-cluster-summary-unit">句</span></div></div><div class="deep-cluster-summary-card"><div class="deep-cluster-summary-label">形成类簇</div><div class="deep-cluster-summary-value">${quality.cluster_count || 0}<span class="deep-cluster-summary-unit">个</span></div></div><div class="deep-cluster-summary-card"><div class="deep-cluster-summary-label">轮廓系数</div><div class="deep-cluster-summary-value">${fixed(quality.silhouette_score, 3)}</div></div><div class="deep-cluster-summary-card"><div class="deep-cluster-summary-label">聚类维度</div><div class="deep-cluster-summary-value deep-cluster-summary-value-text">${escapeHtml(data.cluster_dimension_name || '—')}</div></div></div><div class="deep-cluster-result-tabs"><button class="deep-cluster-result-tab active" type="button" data-viz-tab="overview">类簇与特征统计</button><button class="deep-cluster-result-tab" type="button" data-viz-tab="assignments">文献归属</button><button class="deep-cluster-result-tab" type="button" data-viz-tab="trends">主题趋势</button><button class="deep-cluster-result-tab" type="button" data-viz-tab="correction">评测与人工校正</button></div><div class="deep-cluster-result-panel active" data-viz-panel="overview">${projection}${clusterCards}</div><div class="deep-cluster-result-panel" data-viz-panel="assignments" hidden>${assignments}</div><div class="deep-cluster-result-panel" data-viz-panel="trends" hidden>${trends}</div><div class="deep-cluster-result-panel" data-viz-panel="correction" hidden>${correction}</div><div class="deep-cluster-method-note">当前结果基于句子级语义特征。技术路线模式提高方法、模型、算法和处理流程句子的权重；应用场景模式提高任务对象、行业领域、使用环境和应用目标句子的权重。</div></div>`
}

function renderClusterLabelReview(response) {
  const data = (recordsOf(response)[0] || {}).payload || dataOf(response)
  const labels = array(data.labels ?? data.cluster_labels)
  const process = object(data.label_generation_process_report)
  const optimization = object(data.label_distinctiveness_optimization_result)
  const stages = array(process.stages).length ? array(process.stages) : [
    { order: 1, name: '读取类簇结果', status: 'completed', output: `${data.cluster_count || labels.length} 个类簇` },
    { order: 2, name: '汇总代表特征', status: 'completed', output: '关键词、命名实体和中心句' },
    { order: 3, name: '生成候选标签', status: 'completed', output: `${labels.reduce((sum, item) => sum + array(item.candidate_labels).length, 0)} 个候选标签` },
    { order: 4, name: '差异化筛选', status: 'completed', output: `阈值 ${data.parameters?.distinctiveness_threshold ?? 0.75}` },
    { order: 5, name: '输出推荐标签', status: 'completed', output: `${data.generated_label_count || labels.length} 个标签` },
  ]
  const labelByClusterId = new Map(labels.map(item => [String(item.cluster_id), item]))
  const optimizedRows = (array(optimization.clusters).length ? array(optimization.clusters) : labels).map(item => ({
    cluster_id: item.cluster_id,
    recommended_label: item.recommended_label,
    distinctiveness: item.distinctiveness,
    difference_explanation: item.optimization_explanation || item.difference_explanation || labelByClusterId.get(String(item.cluster_id))?.difference_explanation || '已完成候选标签去重和差异度筛选，保留当前类簇中代表性与区分度更高的标签。',
    optimization_status: item.optimization_status || (number(item.distinctiveness) >= number(data.parameters?.distinctiveness_threshold, 0.75) ? 'passed' : 'needs_review'),
  }))
  const responseMeta = object(data.meta ?? response?.meta)
  const candidateCount = labels.reduce((sum, item) => sum + array(item.candidate_labels).length, 0)
  const passedCount = optimizedRows.filter(item => item.optimization_status === 'passed').length
  const strategyValue = process.strategy || data.generation_strategy || 'adaptive_label_generation'
  const strategyName = strategyValue === 'adaptive_label_generation' ? '自适应多策略融合' : strategyValue === 'llm_assisted' ? '大模型辅助生成' : strategyValue
  const outputLanguageValue = data.parameters?.output_language || data.parameters?.language_type || 'auto'
  const outputLanguageName = outputLanguageValue === 'auto' ? '自动识别' : outputLanguageValue === 'zh' ? '中文' : outputLanguageValue === 'en' ? '英文' : outputLanguageValue
  const labelLengthMin = data.parameters?.label_length?.min ?? 4
  const labelLengthMax = data.parameters?.label_length?.max ?? data.parameters?.label_length_limit ?? 12
  const reportId = process.report_id || data.task_id || responseMeta.request_id || '随任务结果生成'
  const reportTime = process.generated_at || data.completed_at || responseMeta.completed_at || '随任务完成时间记录'
  const reportConclusion = process.summary || `本次共处理 ${data.cluster_count || labels.length} 个类簇，生成 ${data.generated_label_count || labels.length} 个推荐标签；其中 ${passedCount} 个类簇通过差异化检查，生成过程及质量指标已完整记录。`
  return `<div class="cluster-label-result-v705" data-viz-group>
    <div class="cluster-label-result-summary-v705"><div class="cluster-label-result-stat-v705"><strong>${data.cluster_count || labels.length}</strong><span>输入类簇</span></div><div class="cluster-label-result-stat-v705"><strong>${data.generated_label_count || labels.length}</strong><span>推荐标签</span></div><div class="cluster-label-result-stat-v705"><strong>${fixed(data.statistics?.average_confidence || average(labels.map(item => item.confidence)))}</strong><span>平均置信度</span></div><div class="cluster-label-result-stat-v705"><strong>${fixed(data.statistics?.average_distinctiveness || average(labels.map(item => item.distinctiveness)))}</strong><span>平均区分度</span></div></div>
    <div class="cluster-label-result-tabs-v705"><button class="cluster-label-result-tab-v705 active" data-viz-tab="labels">推荐标签</button><button class="cluster-label-result-tab-v705" data-viz-tab="candidates">候选与证据</button><button class="cluster-label-result-tab-v705" data-viz-tab="process">标签生成过程报告</button><button class="cluster-label-result-tab-v705" data-viz-tab="optimization">标签差异化优化结果</button></div>
    <div class="cluster-label-result-panel-v705 active" data-viz-panel="labels"><div class="distribution-table-wrap"><table class="cluster-label-result-table-v705"><thead><tr><th>类簇</th><th>推荐标签</th><th>置信度</th><th>区分度</th><th>差异化说明</th><th>关联文献</th></tr></thead><tbody>${labels.map(item => `<tr><td>${escapeHtml(item.cluster_id)}</td><td><span class="cluster-label-recommend-v705">${escapeHtml(item.recommended_label || item.label || '—')}</span></td><td>${confidence(item.confidence)}</td><td>${confidence(item.distinctiveness)}</td><td>${renderTextWithMath(item.difference_explanation || '—')}</td><td>${escapeHtml(array(item.linked_document_ids).join('、') || `${item.evidence?.text_count || 0} 条文本`)}</td></tr>`).join('') || '<tr><td colspan="6">当前没有可用的推荐标签。</td></tr>'}</tbody></table></div></div>
    <div class="cluster-label-result-panel-v705" data-viz-panel="candidates" hidden><div class="cluster-label-candidate-grid-v705">${labels.map(item => `<div class="cluster-label-candidate-card-v705"><h4>${escapeHtml(item.cluster_id)} · ${escapeHtml(item.recommended_label || '—')}</h4><div class="cluster-label-chip-row-v705">${array(item.candidate_labels).map((candidate, index) => `<span class="cluster-label-chip-v705">#${candidate.rank || index + 1} ${escapeHtml(candidate.label || candidate)}${candidate.confidence != null ? ` · ${confidence(candidate.confidence)}` : ''}</span>`).join('')}</div><div class="cluster-label-evidence-line-v705"><b>关键词：</b>${escapeHtml(array(item.evidence?.keywords).join('、') || '—')}</div><div class="cluster-label-evidence-line-v705"><b>命名实体：</b>${escapeHtml(array(item.evidence?.named_entities).join('、') || '—')}</div><div class="cluster-label-evidence-line-v705"><b>中心句：</b>${renderTextWithMath(item.evidence?.center_sentence || '—')}</div></div>`).join('')}</div></div>
    <div class="cluster-label-result-panel-v705" data-viz-panel="process" hidden><article class="label-generation-report"><header class="label-generation-report-cover"><div><span>聚类标签生成工具</span><h3>标签生成过程报告</h3><p>记录类簇特征汇总、候选标签生成、差异化筛选及推荐标签输出全过程。</p></div><dl><div><dt>报告编号</dt><dd>${escapeHtml(reportId)}</dd></div><div><dt>生成时间</dt><dd>${escapeHtml(reportTime)}</dd></div></dl></header><section class="label-generation-report-section"><h4><i>一</i>任务概况</h4><div class="label-generation-report-summary"><span><b>${data.cluster_count || labels.length}</b><small>输入类簇</small></span><span><b>${candidateCount}</b><small>候选标签</small></span><span><b>${data.generated_label_count || labels.length}</b><small>推荐标签</small></span><span><b>${passedCount}</b><small>差异检查通过</small></span></div></section><div class="label-generation-report-columns"><section class="label-generation-report-section"><h4><i>二</i>生成配置</h4><dl class="label-generation-report-definition"><div><dt>生成策略</dt><dd>${escapeHtml(strategyName)}</dd></div><div><dt>标签长度</dt><dd>${escapeHtml(`≤ ${data.parameters?.label_length_limit ?? 12} 字符`)}</dd></div><div><dt>输出语言</dt><dd>${escapeHtml(outputLanguageName)}</dd></div><div><dt>差异度阈值</dt><dd>${escapeHtml(data.parameters?.distinctiveness_threshold ?? 0.75)}</dd></div></dl></section><section class="label-generation-report-section"><h4><i>三</i>质量摘要</h4><dl class="label-generation-report-definition"><div><dt>平均置信度</dt><dd>${confidence(data.statistics?.average_confidence || average(labels.map(item => item.confidence)))}</dd></div><div><dt>平均区分度</dt><dd>${confidence(data.statistics?.average_distinctiveness || average(labels.map(item => item.distinctiveness)))}</dd></div><div><dt>软回退触发</dt><dd>${escapeHtml(data.statistics?.soft_fallback_triggered_count ?? 0)} 个</dd></div><div><dt>软回退改判</dt><dd>${escapeHtml(data.statistics?.soft_fallback_changed_count ?? 0)} 个</dd></div></dl></section></div><section class="label-generation-report-section"><h4><i>四</i>处理过程明细</h4><div class="distribution-table-wrap"><table class="label-generation-process-table"><thead><tr><th>步骤</th><th>处理阶段</th><th>阶段输出</th><th>执行状态</th></tr></thead><tbody>${stages.map((stage, index) => `<tr><td><span>${stage.order || index + 1}</span></td><td>${escapeHtml(stage.name)}</td><td>${escapeHtml(stage.output || '—')}</td><td><em class="${stage.status === 'completed' ? 'completed' : ''}">${stage.status === 'completed' ? '已完成' : escapeHtml(stage.status || '待处理')}</em></td></tr>`).join('')}</tbody></table></div></section><section class="label-generation-report-section label-generation-report-conclusion"><h4><i>五</i>报告结论</h4><p>${renderTextWithMath(reportConclusion)}</p></section></article></div>
    <div class="cluster-label-result-panel-v705" data-viz-panel="optimization" hidden><div class="review-report-summary-strip"><span>差异阈值 <b>${optimization.threshold ?? data.parameters?.distinctiveness_threshold ?? 0.75}</b></span><span>软回退触发 <b>${data.statistics?.soft_fallback_triggered_count ?? 0}</b></span><span>软回退改判 <b>${data.statistics?.soft_fallback_changed_count ?? 0}</b></span><span>通过类簇 <b>${optimizedRows.filter(item => item.optimization_status === 'passed').length}</b></span></div><div class="distribution-table-wrap"><table class="cluster-label-result-table-v705"><thead><tr><th>类簇</th><th>优化后标签</th><th>区分度</th><th>优化状态</th><th>优化说明</th></tr></thead><tbody>${optimizedRows.map(item => `<tr><td>${escapeHtml(item.cluster_id)}</td><td><span class="cluster-label-recommend-v705">${escapeHtml(item.recommended_label || '—')}</span></td><td>${confidence(item.distinctiveness)}</td><td><span class="optimization-status ${item.optimization_status === 'passed' ? 'passed' : ''}">${item.optimization_status === 'passed' ? '已通过' : '待复核'}</span></td><td>${renderTextWithMath(item.difference_explanation || '—')}</td></tr>`).join('')}</tbody></table></div></div>
  </div>`
}

function renderStructuredReviewSupplement(response) {
  const data = (recordsOf(response)[0] || {}).payload || dataOf(response)
  const tree = array(data.tree ?? data.review_tree)
  const clusterReport = object(data.cluster_induction_results)
  const clusters = array(clusterReport.clusters).length ? array(clusterReport.clusters) : array(data.problem_clusters)
  const hotspots = array(data.trend_hotspot_distribution?.hotspots).length ? array(data.trend_hotspot_distribution.hotspots) : array(data.trends?.hotspots)
  const reportSections = array(data.structured_report?.sections)
  const hotspotAverage = hotspots.length ? hotspots.reduce((sum, item) => sum + number(item.score), 0) / hotspots.length : 0
  const strongestHotspot = [...hotspots].sort((left, right) => number(right.score) - number(left.score))[0]
  const hotspotRows = hotspots.map((item, index) => {
    const score = Math.max(0, Math.min(1, number(item.score)))
    const status = String(item.status || '持续关注')
    const direction = /上升|增长|新兴|升温/.test(status) ? '↗' : /下降|降温/.test(status) ? '↘' : '●'
    return `<div class="review-trend-row review-trend-tone-${index % 4}"><div class="review-trend-label"><i>${index + 1}</i><span><b>${escapeHtml(item.name || '未命名热点')}</b><small>${direction} ${escapeHtml(status)}</small></span></div><div class="review-trend-measure"><div class="review-trend-track"><span class="review-trend-fill" style="width:${score * 100}%"></span><i class="review-trend-dot" style="left:${score * 100}%"></i></div></div><strong>${fixed(score)}</strong></div>`
  }).join('')
  const evidenceRows = []
  const evidenceKeys = new Set()
  tree.forEach(question => array(question.methods).forEach(method => array(method.progress ?? method.progresses).forEach(progress => {
    array(progress.source_evidence).forEach(evidence => {
      const key = `${evidence.document_id || ''}|${evidence.source_section || ''}|${evidence.evidence_excerpt || ''}`
      if (!evidenceKeys.has(key)) { evidenceKeys.add(key); evidenceRows.push(evidence) }
    })
  })))
  const sourceIds = progress => {
    const ids = array(progress.source_ids).length ? array(progress.source_ids) : array(progress.source_evidence).map(item => item.document_id)
    return [...new Set(ids.filter(Boolean))]
  }
  const sourceButtons = (ids, nodeId) => ids.map(id => `<button type="button" class="v710-review-chip v710-review-source-link" data-review-source="${escapeHtml(id)}" data-review-from-node="${escapeHtml(nodeId)}">${escapeHtml(id)}</button>`).join('')
  const treeHtml = tree.map(question => {
    const questionId = question.question_id || '—'
    const methods = array(question.methods)
    const methodsHtml = methods.map(method => {
      const methodId = method.method_id || '—'
      const progresses = array(method.progress ?? method.progresses)
      return `<div class="v710-review-method" data-review-node="${escapeHtml(methodId)}"><div class="v710-review-method-head"><b>${escapeHtml(methodId)} · ${renderTextWithMath(method.method || method.name || '—')}</b></div>${progresses.map((progress, index) => { const progressId = progress.progress_id || `${methodId}-P${index + 1}`; return `<div class="v710-review-progress" data-review-node="${escapeHtml(progressId)}"><strong>研究进展：</strong>${renderTextWithMath(progress.summary || progress.progress || '—')}<br><strong>阶段结论：</strong>${renderTextWithMath(progress.conclusion || '—')}<div class="v710-review-chip-row">${sourceButtons(sourceIds(progress), progressId)}</div></div>` }).join('')}</div>`
    }).join('')
    return `<div class="v710-review-question" data-review-node="${escapeHtml(questionId)}"><div class="v710-review-question-head"><span>${escapeHtml(questionId)} · ${renderTextWithMath(question.research_question || question.question || '—')}</span></div><div class="v710-review-method-list">${methodsHtml}</div></div>`
  }).join('')
  const evidenceSourceHeading = resultPositionHeading(evidenceRows)
  const evidenceHtml = evidenceRows.map(item => `<tr data-review-document="${escapeHtml(item.document_id)}"><td>${escapeHtml(item.document_id)}</td><td>${renderTextWithMath(item.title)}</td><td>${escapeHtml(positionLabel(item))}</td><td>${renderTextWithMath(item.evidence_excerpt)}</td><td>${array(item.supported_nodes).map(node => `<button type="button" class="v710-review-chip v710-review-node-link" data-review-node-link="${escapeHtml(node)}">${escapeHtml(node)}</button>`).join(' ')}</td></tr>`).join('') || '<tr><td colspan="5">未返回可定位的原始文献证据。</td></tr>'
  return `<div class="v710-review-result" data-viz-group>
    <div class="v710-review-result-tabs"><button class="v710-review-tab active" data-viz-tab="tree">三层树形结构综述视图</button><button class="v710-review-tab" data-viz-tab="clusters">聚类及类簇归纳结果</button><button class="v710-review-tab" data-viz-tab="report">结构化文本综述报告</button><button class="v710-review-tab" data-viz-tab="trends">趋势分析与研究热点分布图</button></div>
    <div class="v710-review-result-panel active" data-viz-panel="tree"><div class="v710-review-tree">${treeHtml}</div><aside class="v710-review-evidence-drawer" data-review-evidence-drawer hidden><div class="v710-review-evidence-drawer-head"><div><b>溯源询证</b><span>从综述节点定位原始文献及相关关键句段</span></div><button type="button" class="ghost-btn" data-review-evidence-close>关闭</button></div><div class="v710-review-table-wrap"><table class="v710-review-table"><thead><tr><th>文献编号</th><th>文献题名</th><th>${evidenceSourceHeading}</th><th>关键句段</th><th>支撑节点</th></tr></thead><tbody>${evidenceHtml}</tbody></table></div></aside></div>
    <div class="v710-review-result-panel" data-viz-panel="clusters" hidden><div class="cluster-induction-note"><b>归纳依据</b><span>${renderTextWithMath(clusterReport.induction_basis || '研究问题语义相似度、研究方法共现和来源证据一致性')}</span></div><div class="cluster-induction-grid">${clusters.map((cluster, index) => `<article><div><i>${index + 1}</i><b>${escapeHtml(cluster.label || cluster.cluster_name || cluster.cluster_id || '未命名类簇')}</b></div><p>${renderTextWithMath(cluster.summary || cluster.induction || '汇总语义相近的研究问题及其方法证据。')}</p><span>${escapeHtml(cluster.cluster_id || '—')} · ${number(cluster.document_count)} 篇文献</span></article>`).join('') || '<div class="semantic-empty">暂无聚类及类簇归纳结果。</div>'}</div></div>
    <div class="v710-review-result-panel" data-viz-panel="report" hidden><article class="review-report-paper"><header class="review-report-cover"><span>STRUCTURED LITERATURE REVIEW</span><h3>结构化自动综述报告</h3><p>研究问题—研究方法—研究进展</p></header><section class="review-report-abstract"><h4>摘要</h4><p>${renderTextWithMath(data.structured_report?.overview || '暂无结构化综述摘要。')}</p>${hotspots.length ? `<div class="review-report-keywords"><b>研究热点：</b>${hotspots.map(item => escapeHtml(item.name)).join('；')}</div>` : ''}</section><div class="review-report-divider"><span>正文</span></div><div class="review-report-body">${reportSections.map((section, index) => `<section class="review-report-section"><div class="review-report-section-number">${String(index + 1).padStart(2, '0')}</div><div><h4>${renderTextWithMath(section.title || `第 ${index + 1} 部分`)}</h4><p>${renderTextWithMath(section.content || '—')}</p></div></section>`).join('') || '<div class="semantic-empty">暂无结构化文本综述内容。</div>'}</div></article></div>
    <div class="v710-review-result-panel" data-viz-panel="trends" hidden><section class="review-trend-dashboard"><header class="review-trend-summary"><div><span>趋势分析周期</span><b>${escapeHtml(data.trend_hotspot_distribution?.time_range || '未提供')}</b></div><div><span>研究热点数量</span><b>${hotspots.length}</b></div><div><span>平均热点强度</span><b>${fixed(hotspotAverage)}</b></div><div class="review-trend-leading"><span>首要研究热点</span><b>${escapeHtml(strongestHotspot?.name || '暂无')}</b></div></header><div class="review-trend-chart"><div class="review-trend-chart-head"><div><h4>研究热点强度排行</h4><p>依据当前响应中的热点得分与趋势状态进行展示</p></div><div class="review-trend-legend"><i></i><span>热点强度</span></div></div><div class="review-trend-axis"><span></span><div><i>0</i><i>0.25</i><i>0.50</i><i>0.75</i><i>1.00</i></div><span>得分</span></div><div class="review-trend-rows">${hotspotRows || '<div class="semantic-empty">暂无趋势和研究热点分布数据。</div>'}</div></div></section></div>
  </div>`
}

const titleByTool = {
  'fund-move': '中文基金项目语步识别结构化结果',
  'zh-abstract-move': '中文摘要语步识别结构化结果',
  'en-abstract-move': '英文摘要语步识别结构化结果',
  'zh-classify': '中文科技文献分类结构化结果',
  'en-classify': '英文科技文献分类结构化结果',
  'domain-classify': '专业领域科技文献分类结构化结果',
  'zh-keyword': '中文科技文献关键词识别结构化结果',
  'en-keyword': '英文科技文献关键词识别结构化结果',
  'rq-detect': '研究问题识别结果',
  'citation-sentiment': '引用情感识别结果',
  'citation-intent': '引用意图识别结果',
  'definition-detect': '概念定义句识别工具结构化结果',
  'general-ner': '命名实体识别结果',
  'research-ner': '科研实体识别结果',
  'domain-ner': '专业领域科研实体识别结果',
  'relation-extract': '实体关系识别结果',
  'deep-cluster': '深度聚类分析结果',
  'cluster-label': '类簇标签结构化结果',
  'structured-review': '结构化自动综述结果',
}

export function visualizationTitle(toolId, fallback) {
  return titleByTool[toolId] || `${fallback}可视化结果`
}

export function renderPrototypeVisualization(toolId, response) {
  if (toolId === 'domain-classify') return renderDomainClassification(response)
  if (toolId === 'relation-extract') return renderRelations(response)
  if (toolId === 'deep-cluster') return renderDeepCluster(response)
  if (toolId === 'cluster-label') return renderClusterLabelReview(response)
  if (toolId === 'structured-review') return renderStructuredReviewSupplement(response)
  return renderSpecializedVisualization(toolId, response)
}

