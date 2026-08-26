const array = value => Array.isArray(value) ? value : []
const object = value => value && typeof value === 'object' && !Array.isArray(value) ? value : {}

const pathKeys = [
  'chapter_path',
  'chapter_hierarchy',
  'section_path',
  'section_hierarchy',
  'heading_path',
  'title_path',
]

const levelKeys = [
  ['level_1', 'level1', 'first_level_title', 'primary_title', 'chapter_title'],
  ['level_2', 'level2', 'second_level_title', 'secondary_title', 'section_title'],
  ['level_3', 'level3', 'third_level_title', 'tertiary_title', 'subsection_title'],
]

const startKeys = ['start', 'start_char', 'char_start', 'start_offset', 'offset_start', 'begin']
const endKeys = ['end', 'end_char', 'char_end', 'end_offset', 'offset_end', 'stop']
const positionKeys = ['source_position', 'position', 'text_position', 'entity_position']
const clean = value => String(value ?? '').trim()

function splitPath(value) {
  if (Array.isArray(value)) return value.flatMap(splitPath).filter(Boolean)
  if (value && typeof value === 'object') return positionParts(value)
  const text = clean(value)
  if (!text) return []
  // 反斜杠不当分隔符——基金报告标题的 \ 是 LaTeX 命令前缀(\mathrm 等)，非 Windows 路径；
  // LaTeX 清理/归并/排序已交后端 LLM 汇总(_summarize_sources_via_llm)，前端只做路径分层展示
  return text.split(/\s*(?:>|›|→|\/)\s*/).map(clean).filter(Boolean)
}

const distinct = parts => parts.filter((part, index) => part && part !== parts[index - 1])

function positionParts(value) {
  const position = object(value)
  for (const key of pathKeys) {
    const parts = distinct(splitPath(position[key]))
    if (parts.length) return parts
  }

  const levels = levelKeys.map(keys => {
    const key = keys.find(candidate => clean(position[candidate]))
    return key ? clean(position[key]) : ''
  }).filter(Boolean)
  if (levels.length) return distinct(levels)

  return distinct(splitPath(position.section ?? position.source_section))
}

function numberFrom(source, keys) {
  const key = keys.find(candidate => source[candidate] !== undefined && source[candidate] !== null && source[candidate] !== '')
  if (!key) return null
  const value = Number(source[key])
  return Number.isFinite(value) ? value : null
}

function characterParts(value) {
  const position = object(value)
  const start = numberFrom(position, startKeys)
  const end = numberFrom(position, endKeys)
  return start !== null && end !== null ? { start, end } : null
}

function inputTypeOf(item) {
  const source = object(item)
  const record = object(source.__record ?? source.record)
  const recordPayload = object(record.payload)
  const candidates = [
    source.input_type,
    object(source.input).input_type,
    recordPayload.input_type,
    object(recordPayload.input).input_type,
    object(recordPayload.input_summary).input_type,
  ]
  return clean(candidates.find(Boolean)).toLowerCase().replace(/_/g, '-')
}

function modeFromInputType(inputType) {
  if (!inputType) return ''
  if (inputType.includes('file') || inputType === 'collection' || inputType.includes('document')) return 'chapter'
  if (inputType.includes('text')) return 'character'
  return ''
}

export function chapterPositionParts(item) {
  const source = object(item)
  for (const key of positionKeys) {
    const parts = positionParts(source[key])
    if (parts.length) return parts
  }

  for (const key of pathKeys) {
    const parts = distinct(splitPath(source[key]))
    if (parts.length) return parts
  }

  const direct = positionParts(source)
  if (direct.length) return direct

  const sections = array(source.source_sections)
  if (sections.length === 1) return distinct(splitPath(sections[0]))
  return []
}

export function characterPositionParts(item) {
  const source = object(item)
  for (const key of positionKeys) {
    const parts = characterParts(source[key])
    if (parts) return parts
  }
  return characterParts(source)
}

export function positionDisplayKind(item) {
  const expected = modeFromInputType(inputTypeOf(item))
  const characters = characterPositionParts(item)
  const chapters = chapterPositionParts(item)
  if (expected === 'character') return characters ? 'character' : chapters.length ? 'chapter' : 'missing'
  if (expected === 'chapter') return chapters.length ? 'chapter' : characters ? 'character' : 'missing'
  if (characters) return 'character'
  if (chapters.length) return 'chapter'
  return 'missing'
}

export function chapterPositionLabel(item, fallback = '章节位置未返回') {
  const parts = chapterPositionParts(item)
  return parts.length ? parts.join(' > ') : fallback
}

export function characterPositionLabel(item, fallback = '字符位置未返回') {
  const parts = characterPositionParts(item)
  return parts ? `字符 ${parts.start}—${parts.end}` : fallback
}

export function resultPositionLabel(item, fallback = '位置未返回') {
  const kind = positionDisplayKind(item)
  if (kind === 'character') return characterPositionLabel(item, fallback)
  if (kind === 'chapter') return chapterPositionLabel(item, fallback)
  return fallback
}

export function resultPositionHeading(items, chapterHeading = '来源章节', characterHeading = '来源位置') {
  return array(items).some(item => positionDisplayKind(item) === 'character') ? characterHeading : chapterHeading
}

export function chapterSectionListLabel(value, fallback = '章节位置未返回') {
  const sections = array(value)
  if (!sections.length) return chapterPositionLabel({ source_section: value }, fallback)
  const paths = sections.map(section => splitPath(section).join(' > ')).filter(Boolean)
  return paths.length ? paths.join('；') : fallback
}

// fund-move 片段级绑定后，一个语步常跨同上级下的多个叶子（如「2.研究工作主要进展 > 2)…」
// 重复 8 次。按首段(上级章节)分组：上级只列一次，同上级下的多个叶子聚到该组。
// 单层来源（章节本身即叶子，如「中文摘要：」「1.研究背景与动机」）按核心归并——去括号补充与
// 尾标点后核心相同者（如「中文摘要：」与「中文摘要（…）：」）合并为一条，避免同一标题多种写法
// 重复罗列。返回结构化 [{head, leaves:[]}]：单层(leaves=[])在前、多层在后，leaves 已去重。
function normalizeSourceCore(value) {
  return String(value ?? '')
    .replace(/（[^（）]*）/g, '')
    .replace(/\([^()]*\)/g, '')
    .replace(/[:：。；;,\s]+$/g, '')
    .trim()
}

export function fundMoveSourceGroups(sections) {
  const arr = array(sections)
  const paths = arr.map(section => splitPath(section)).filter(parts => parts.length)
  const multi = new Map()
  const single = new Map()
  for (const parts of paths) {
    if (parts.length === 1) {
      const core = normalizeSourceCore(parts[0])
      const prev = single.get(core)
      if (!prev) single.set(core, { head: parts[0], count: 1 })
      else prev.count++
    } else {
      const head = parts[0]
      if (!multi.has(head)) multi.set(head, [])
      multi.get(head).push(parts.slice(1).join(' > '))
    }
  }
  const result = []
  for (const { head, count } of single.values()) {
    result.push({ head: count > 1 ? normalizeSourceCore(head) : head, leaves: [] })
  }
  for (const [head, leaves] of multi) {
    result.push({ head, leaves: [...new Set(leaves)] })
  }
  return result
}

// 单行字符串版（备用）：上级：叶1、叶2；上级2：…
export function fundMoveSourceLabel(sections, fallback = '位置未返回') {
  const groups = fundMoveSourceGroups(sections)
  if (!groups.length) return fallback
  const segments = groups.map(({ head, leaves }) =>
    leaves.length ? `${head}：${leaves.join('、')}` : head)
  return segments.join('；') || fallback
}

// 把完整路径列表建成前缀树（trie）：公共前缀节点只存一次，不同分支并列挂下，
// 避免同前缀路径反复重写（如「（一）结题部分 > 2.研究进展 >」重复 N 次）。
// 返回树根 {children: Map<seg, node>, leaf: bool}，供渲染层做树形分层展示。
export function buildSourceTree(sections) {
  const paths = array(sections).map(section => splitPath(section)).filter(parts => parts.length)
  const root = { children: new Map(), leaf: false }
  for (const parts of paths) {
    let node = root
    for (const seg of parts) {
      if (!node.children.has(seg)) node.children.set(seg, { children: new Map(), leaf: false })
      node = node.children.get(seg)
    }
    node.leaf = true
  }
  return root
}
