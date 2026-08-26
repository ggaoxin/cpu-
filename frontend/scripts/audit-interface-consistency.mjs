import { createServer } from 'vite'

const server = await createServer({
  appType: 'custom',
  logLevel: 'silent',
  server: { middlewareMode: true },
})

const failures = []
let checkedModes = 0

const objectOf = value => value && typeof value === 'object' && !Array.isArray(value) ? value : {}
const dataOf = response => objectOf(response?.data ?? response)
const resultPayloads = response => {
  const data = dataOf(response)
  if (!Array.isArray(data.results)) return []
  return data.results.map(item => {
    const result = objectOf(item?.result ?? item?.data ?? item)
    return objectOf(result?.data ?? result)
  })
}

try {
  const tooling = await server.ssrLoadModule('/src/utils/tooling.ts')
  const toolModule = await server.ssrLoadModule('/src/data/tool-overrides.ts')

  for (const [toolId, tool] of Object.entries(toolModule.tools)) {
    for (const mode of tooling.modesFor(tool)) {
      checkedModes += 1
      const payload = tooling.payloadFor(tool, mode)
      const payloadKeys = Object.keys(payload)
      const parameterRows = tooling.requestParameterRowsFor(tool, mode)
      const topLevelParameterKeys = parameterRows
        .map(row => row[0])
        .filter(name => !name.includes('.'))

      const missingParameterRows = payloadKeys.filter(key => !topLevelParameterKeys.includes(key))
      const extraParameterRows = topLevelParameterKeys.filter(key => !payloadKeys.includes(key))
      if (missingParameterRows.length || extraParameterRows.length) {
        failures.push(`${toolId}/${mode}: 请求 JSON 与参数表不一致`)
      }

      const apiCode = tooling.buildCallCode(tool, mode, 'api')
      const sdkCode = tooling.buildCallCode(tool, mode, 'sdk')
      const endpoint = tooling.endpointFor(tool, mode)
      if (!apiCode.includes(endpoint) || !sdkCode.includes(endpoint)) {
        failures.push(`${toolId}/${mode}: API 或 SDK 未使用当前输入方式端点`)
      }
      if (!sdkCode.includes('SemanticToolkitClient') || !sdkCode.includes('json.loads')) {
        failures.push(`${toolId}/${mode}: SDK 示例不是可执行的 Python SDK 写法`)
      }
      if (!apiCode.includes('requests.post')) {
        failures.push(`${toolId}/${mode}: API 示例未使用 HTTP POST`)
      }

      const response = tooling.responseFor(tool, mode)
      const modalResponse = toolModule.demoResponseForMode(toolId, tool, mode)
      if (JSON.stringify(response) !== JSON.stringify(modalResponse)) {
        failures.push(`${toolId}/${mode}: 响应示例与可视化弹窗数据源不一致`)
      }

      // 批量请求和批量弹窗必须描述同一批对象，避免示例提交 2 篇、
      // 结果却展示 3 篇等原型演示错位。
      if (mode === 'batch-text' || mode === 'batch') {
        const primaryValue = payload[payloadKeys[0]]
        const responseRecords = resultPayloads(response)
        if (Array.isArray(primaryValue) && responseRecords.length && primaryValue.length !== responseRecords.length) {
          failures.push(`${toolId}/${mode}: 批量请求 ${primaryValue.length} 项，但弹窗响应 ${responseRecords.length} 项`)
        }
      }

      if ((mode === 'text' || mode === 'batch-text') && payload.document_title) {
        const requestedTitles = Array.isArray(payload.document_title)
          ? payload.document_title.map(String)
          : [String(payload.document_title)]
        const records = resultPayloads(response)
        const titledRecords = records.length ? records : [dataOf(response)]
        requestedTitles.forEach((title, index) => {
          const record = titledRecords[index]
          const responseTitle = String(record?.document_title || record?.document?.title || '').trim()
          if (title.trim() && responseTitle !== title.trim()) {
            failures.push(`${toolId}/${mode}#${index + 1}: 请求题名“${title.trim()}”，弹窗题名“${responseTitle || '空'}”`)
          }
        })
      }

      if (toolId === 'domain-classify') {
        const expectedDomain = String(payload.professional_domain || '').trim()
        const records = resultPayloads(response)
        const domainRecords = records.length ? records : [dataOf(response)]
        if (!expectedDomain) failures.push(`${toolId}/${mode}: 未提供目标专业领域`)
        domainRecords.forEach((record, index) => {
          const selectedDomain = String(
            record?.domain_match_result?.selected_domain?.name
            || record?.selected_domain?.name
            || record?.professional_domain
            || '',
          ).trim()
          const primary = Array.isArray(record?.multilevel_classification_results)
            ? record.multilevel_classification_results[0]
            : Array.isArray(record?.classifications) ? record.classifications[0] : null
          const candidates = Array.isArray(record?.candidate_classifications) ? record.candidate_classifications : []
          if (selectedDomain !== expectedDomain) {
            failures.push(`${toolId}/${mode}#${index + 1}: 目标领域“${selectedDomain || '空'}”与请求“${expectedDomain}”不一致`)
          }
          if (!primary?.level_1 || !primary?.level_2 || !primary?.level_3) {
            failures.push(`${toolId}/${mode}#${index + 1}: 缺少完整三级分类路径`)
          }
          if (candidates.length < 2) {
            failures.push(`${toolId}/${mode}#${index + 1}: 候选分类不足，无法进行人工确认`)
          }
          const primaryRoot = String(primary?.level_1 || '')
          if (candidates.some(candidate => {
            const path = Array.isArray(candidate?.classification_path)
              ? candidate.classification_path
              : [candidate?.level_1, candidate?.level_2, candidate?.level_3]
            return path[0] && String(path[0]) !== primaryRoot
          })) {
            failures.push(`${toolId}/${mode}#${index + 1}: 候选分类跨出当前专业大类`)
          }
        })
      }
    }
  }

  if (failures.length) {
    console.error(`接口一致性审查失败：${failures.length} 项`)
    failures.forEach(item => console.error(`- ${item}`))
    process.exitCode = 1
  } else {
    console.log(`接口一致性审查通过：${Object.keys(toolModule.tools).length} 个功能，${checkedModes} 种输入方式。`)
    console.log('API/SDK 业务参数、请求参数表、输入方式端点和弹窗响应数据源已同步。')
  }
} finally {
  await server.close()
}
