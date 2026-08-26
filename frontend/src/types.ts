export type InputMode = 'text' | 'batch-text' | 'file' | 'batch' | 'existing-result' | 'collection'
export type CallType = 'api' | 'sdk'

export interface ToolDefinition {
  group: string
  title: string
  description: string
  features: string
  scenarios: string
  endpoint?: string
  textEndpoint?: string
  batchTextEndpoint?: string
  fileEndpoint?: string
  batchFileEndpoint?: string
  historyTaskEndpoint?: string
  collectionEndpoint?: string
  documentType?: string
  inputModes?: InputMode[]
  modeLabels?: Record<string, string>
  params?: Array<[string, string, string, string]>
  requirementOutputs?: Array<[string, string, string]>
  requirementKey?: string
  payload?: Record<string, unknown>
  response?: Record<string, unknown>
  [key: string]: unknown
}

export interface ToolGroup {
  name: string
  items: Array<[string, string]>
}
