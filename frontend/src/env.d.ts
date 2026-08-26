/// <reference types="vite/client" />

declare module '*.generated.js' {
  export const groups: Array<{ name: string; items: Array<[string, string]> }>
  export const tools: Record<string, Record<string, unknown>>
}
