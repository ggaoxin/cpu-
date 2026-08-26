import type { InputMode } from '../types'

export class ApiRequestError extends Error {
  status: number
  details: unknown

  constructor(message: string, status: number, details?: unknown) {
    super(message)
    this.name = 'ApiRequestError'
    this.status = status
    this.details = details
  }
}

function apiUrl(endpoint: string) {
  const configured = String(import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')
  if (!configured || configured === '/api') return endpoint
  if (/^https?:\/\//i.test(configured)) return `${configured}${endpoint}`
  return `${configured}${endpoint}`.replace(/\/+/g, '/')
}

function jsonSafeValue(value: unknown): unknown {
  if (value instanceof File) return null
  if (Array.isArray(value)) return value.map(jsonSafeValue)
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.entries(value as Record<string, unknown>).map(([key, child]) => [key, jsonSafeValue(child)]))
  }
  return value
}

function appendFormValue(form: FormData, key: string, value: unknown) {
  if (value === undefined || value === null) return
  if (value instanceof File) {
    form.append(key, value, value.name)
    return
  }
  if (Array.isArray(value) && value.every(item => item instanceof File)) {
    value.forEach(item => form.append(key, item as File, (item as File).name))
    return
  }
  if (value && typeof value === 'object') {
    const record = value as Record<string, unknown>
    Object.entries(record).forEach(([nestedKey, child]) => {
      if (child instanceof File) form.append(`${key}__${nestedKey}`, child, child.name)
    })
    form.append(key, JSON.stringify(jsonSafeValue(value)))
    return
  }
  if (Array.isArray(value)) {
    form.append(key, JSON.stringify(jsonSafeValue(value)))
    return
  }
  form.append(key, String(value))
}

function containsFile(value: unknown): boolean {
  if (value instanceof File) return true
  if (Array.isArray(value)) return value.some(containsFile)
  return Boolean(value && typeof value === 'object' && Object.values(value as Record<string, unknown>).some(containsFile))
}

async function parseResponse(response: Response) {
  const contentType = response.headers.get('content-type') || ''
  const body = contentType.includes('application/json')
    ? await response.json()
    : { message: await response.text() }
  if (!response.ok || Number(body?.code || 0) !== 0) {
    const detail = body?.detail || body?.message || `请求失败（HTTP ${response.status}）`
    throw new ApiRequestError(typeof detail === 'string' ? detail : JSON.stringify(detail), response.status, body)
  }
  return body
}

export async function executeToolRequest(
  endpoint: string,
  mode: InputMode,
  payload: Record<string, unknown>,
) {
  const fileMode = mode === 'file' || mode === 'batch' || containsFile(payload)
  const init: RequestInit = { method: 'POST', headers: { Accept: 'application/json' } }
  if (fileMode) {
    const form = new FormData()
    Object.entries(payload).forEach(([key, value]) => appendFormValue(form, key, value))
    init.body = form
  } else {
    ;(init.headers as Record<string, string>)['Content-Type'] = 'application/json'
    init.body = JSON.stringify(jsonSafeValue(payload))
  }
  return parseResponse(await fetch(apiUrl(endpoint), init))
}

export async function listSemanticResources() {
  const response = await fetch(apiUrl('/api/v1/semantic-resources?status=current&limit=500'), {
    headers: { Accept: 'application/json' },
  })
  return parseResponse(response)
}

export async function listDocumentCollections(topic?: string) {
  const query = new URLSearchParams({ limit: '200' })
  if (topic && topic.trim()) {
    query.set('topic', topic.trim())
    query.set('threshold', '0.3')
  }
  return parseResponse(await fetch(apiUrl(`/api/v1/collections?${query}`), { headers: { Accept: 'application/json' } }))
}

export async function listCompatibleHistory(downstreamTool: string, upstreamType: string) {
  const query = new URLSearchParams({ downstream_tool: downstreamTool, upstream_type: upstreamType, limit: '200' })
  return parseResponse(await fetch(apiUrl(`/api/v1/history/compatible?${query}`), { headers: { Accept: 'application/json' } }))
}

export async function listDictionaries() {
  return parseResponse(await fetch(apiUrl('/api/v1/dictionaries?limit=200'), { headers: { Accept: 'application/json' } }))
}

export async function saveDictionary(payload: Record<string, unknown>) {
  return parseResponse(await fetch(apiUrl('/api/v1/dictionaries'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify(payload),
  }))
}

export async function uploadSemanticResource(file: File, resourceKey: string) {
  const form = new FormData()
  form.append('resource_key', resourceKey)
  form.append('upload', file)
  return parseResponse(await fetch(apiUrl('/api/v1/semantic-resources/upload'), {
    method: 'POST',
    headers: { Accept: 'application/json' },
    body: form,
  }))
}

export async function evaluateDeepCluster(payload: Record<string, unknown>) {
  return executeToolRequest('/api/v1/cluster/deep/evaluate', 'batch-text', payload)
}
