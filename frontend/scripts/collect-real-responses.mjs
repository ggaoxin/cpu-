#!/usr/bin/env node
/**
 * 采集所有功能点的真实接口响应，写入 real-responses.generated.json。
 *
 * 用途：前端"响应示例"原本用合成演示数据（旧 schema），与真实接口输出对不上。
 * 本脚本用各功能点"调用示例"的输入，打到真实 Vue 集成端点，采集真实响应，
 * 作为响应示例的数据源。text 模式用 demoApiPayloadForTool 的 payload；
 * batch-text 模式在此基础上把主文本字段换成 demoBatchTexts 数组。
 *
 * 运行：node scripts/collect-real-responses.mjs
 * 前置：后端 8000 在跑、GLM key 已配、bge 权重和 CLC 索引就绪。
 */
import { writeFile, readFile } from 'node:fs/promises'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { tools } from '../src/data/tool-overrides.ts'
import { demoApiPayloadForTool } from '../src/data/demo-semantic-consistency.ts'
import { payloadFor } from '../src/utils/tooling.ts'

const scriptDir = dirname(fileURLToPath(import.meta.url))
const outFile = resolve(scriptDir, '..', 'src', 'data', 'real-responses.generated.json')
const BASE = process.env.API_BASE || 'http://127.0.0.1:8000'

const TEXT_TOOLS = [
  'zh-abstract-move', 'en-abstract-move', 'fund-move',
  'zh-classify', 'en-classify', 'domain-classify',
  'zh-keyword', 'en-keyword', 'rq-detect',
  'citation-sentiment', 'citation-intent', 'definition-detect',
  'general-ner', 'research-ner', 'domain-ner',
]
const BATCH_ONLY_TOOLS = ['deep-cluster', 'cluster-label', 'structured-review']
const TIMEOUT_MS = 15 * 60 * 1000

// 资源字段名（demoApiPayloadForTool 里带正确 resource_id 的嵌套结构）
const RESOURCE_KEYS = [
  'clc_labeled_data', 'domain_terminology_library', 'classification_standard_mapping_table',
  'domain_classification_rules', 'manually_labeled_training_data', 'preprocessed_training_set',
  'general_domain_annotated_corpus', 'multi_domain_scientific_corpus', 'manually_labeled_data',
  'ontology_classification_system', 'domain_labeled_training_data',
]

/**
 * 构造 batch-text 模式的 payload。
 * 策略：以前端"调用示例" payloadFor(tool,'batch-text') 为基础（保证与展示一致）。
 * payloadFor 对 citation/domain-classify 的 batch 已返回自构造简短输入
 * （CUSTOM_BATCH_PAYLOADS，<8000 字符），其余工具用 demoBatchTexts + 资源字段。
 * 用 demoApiPayloadForTool 的资源字段覆盖修复（payloadFor 会把资源字段拆成空占位）。
 */
function batchPayloadFor(toolId) {
  const tool = tools[toolId]
  if (!tool) return null
  const base = payloadFor(tool, 'batch-text')
  const demo = demoApiPayloadForTool(toolId) || {}
  const payload = { ...base }
  // 用 demo 的资源字段（含正确 resource_id）覆盖 payloadFor 拆坏的占位
  for (const key of RESOURCE_KEYS) {
    if (demo[key] !== undefined) {
      payload[key] = demo[key]
      // 删除 payloadFor 拆出的扁平占位键
      delete payload[`${key}.source`]
      delete payload[`${key}.resource_id`]
      delete payload[`${key}.file`]
      delete payload[`${key}.terms`]
      delete payload[`${key}.weight_boost`]
      delete payload[`${key}.dictionary_name`]
      delete payload[`${key}.use_mode`]
    }
  }
  return payload
}

async function callEndpoint(endpoint, payload, label) {
  console.log(`[${label}] POST ${endpoint}`)
  const start = Date.now()
  try {
    const res = await fetch(BASE + endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(TIMEOUT_MS),
    })
    const text = await res.text()
    let body
    try { body = JSON.parse(text) } catch { body = { _raw: text } }
    const elapsed = Date.now() - start
    if (!res.ok) {
      console.error(`  ✗ HTTP ${res.status} (${elapsed}ms): ${text.slice(0, 180)}`)
      return null
    }
    console.log(`  ✓ ${elapsed}ms code=${body?.code}`)
    return body
  } catch (e) {
    console.error(`  ✗ 异常 (${Date.now() - start}ms): ${e.message}`)
    return null
  }
}

async function main() {
  // 命令行参数：指定 toolId 只重采这些（合并到现有 JSON），不传则全量采集
  const onlyIds = process.argv.slice(2).filter(a => !a.startsWith('-'))
  const targetTextIds = onlyIds.length ? TEXT_TOOLS.filter(id => onlyIds.includes(id)) : TEXT_TOOLS
  const targetBatchIds = onlyIds.length
    ? [...TEXT_TOOLS, ...BATCH_ONLY_TOOLS].filter(id => onlyIds.includes(id))
    : [...TEXT_TOOLS, ...BATCH_ONLY_TOOLS]
  // 只重采时，先加载现有 JSON 保留其余结果
  let result = {}
  if (onlyIds.length) {
    try {
      const existing = await readFile(outFile, 'utf8')
      result = JSON.parse(existing)
    } catch { /* 全新采集 */ }
  }
  // text 模式
  for (const id of targetTextIds) {
    const tool = tools[id]
    const payload = demoApiPayloadForTool(id)
    result[id] = result[id] || {}
    result[id].text = await callEndpoint(tool.textEndpoint, payload, `${id}/text`)
  }
  // batch-text 模式
  for (const id of targetBatchIds) {
    const tool = tools[id]
    const payload = batchPayloadFor(id)
    result[id] = result[id] || {}
    result[id]['batch-text'] = payload
      ? await callEndpoint(tool.batchTextEndpoint, payload, `${id}/batch-text`)
      : null
  }
  // 统计
  const all = []
  for (const [id, modes] of Object.entries(result)) {
    for (const [mode, r] of Object.entries(modes)) all.push({ id, mode, ok: r !== null })
  }
  const ok = all.filter(x => x.ok).length
  const fail = all.filter(x => !x.ok)
  console.log(`\n采集完成: ${ok}/${all.length} 成功`)
  if (fail.length) {
    console.log('失败:')
    for (const f of fail) console.log(`  ${f.id}/${f.mode}`)
  }
  await writeFile(outFile, JSON.stringify(result, null, 2), 'utf8')
  console.log(`已写入: ${outFile}`)
}

main().catch(e => { console.error(e); process.exit(1) })
