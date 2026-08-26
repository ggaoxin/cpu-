<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { CallType, InputMode, ToolDefinition } from '../types'
import { buildCallCode, buildDeepClusterEvaluationCallCode, deepClusterEvaluationParameters, modesFor, pretty, requestParameterRowsFor, responseFor } from '../utils/tooling'
import ModeSwitch from './ModeSwitch.vue'

const props = defineProps<{ tool: ToolDefinition }>()
const callType = ref<CallType>('api')
const mode = ref<InputMode>('text')
const copied = ref('')
const modes = computed(() => modesFor(props.tool))
watch(() => props.tool, () => { callType.value = 'api'; mode.value = modes.value[0] }, { immediate: true })
const callCode = computed(() => buildCallCode(props.tool, mode.value, callType.value))
const responseCode = computed(() => pretty(responseFor(props.tool, mode.value)))
const evaluationCode = computed(() => buildDeepClusterEvaluationCallCode(callType.value))
const parameterRows = computed(() => requestParameterRowsFor(props.tool, mode.value))
async function copy(value: string, name: string) { try { await navigator.clipboard.writeText(value); copied.value = name; setTimeout(() => copied.value = '', 1400) } catch { copied.value = '复制失败' } }
</script>

<template>
  <section class="section">
    <div class="section-header call-sample-header-v773">
      <h2 class="section-title">调用示例</h2>
      <div id="callTypeSwitchV770" aria-label="调用方式">
        <button class="call-type-btn-v770" :class="{ active: callType === 'api' }" @click="callType = 'api'">API 调用</button>
        <button class="call-type-btn-v770" :class="{ active: callType === 'sdk' }" @click="callType = 'sdk'">SDK 调用</button>
      </div>
      <button class="outline-btn" type="button" @click="copy(callCode, '调用示例已复制')">⧉ 复制代码</button>
    </div>
    <ModeSwitch v-model="mode" :modes="modes" :tool="tool" :kind="callType === 'api' ? 'API 调用输入方式' : 'SDK 调用输入方式'" />
    <div class="code-box"><pre>{{ callCode }}</pre></div>
  </section>

  <section v-if="tool.documentType === 'deep-cluster'" class="section">
    <div class="section-header"><div><h2 class="section-title">独立模型评测调用</h2><p class="response-source-note">该接口只评测聚类模型性能，不会影响上方普通文献聚类请求。</p></div><button class="outline-btn" type="button" @click="copy(evaluationCode, '评测调用示例已复制')">⧉ 复制代码</button></div>
    <div class="code-box"><pre>{{ evaluationCode }}</pre></div>
    <div class="table-card evaluation-parameter-table"><table><thead><tr><th style="width:28%">参数名</th><th style="width:16%">类型</th><th style="width:12%">必填</th><th>说明</th></tr></thead><tbody><tr v-for="row in deepClusterEvaluationParameters" :key="row[0]"><td><code>{{ row[0] }}</code></td><td>{{ row[1] }}</td><td><span class="pill required">必填</span></td><td>{{ row[3] }}</td></tr></tbody></table></div>
  </section>

  <section class="section">
    <div class="section-header"><h2 class="section-title">请求参数</h2></div>
    <div class="table-card"><table><thead><tr><th style="width:24%">参数名</th><th style="width:14%">类型</th><th style="width:12%">必填</th><th>说明</th></tr></thead>
      <tbody><tr v-for="row in parameterRows" :key="row[0]"><td><code>{{ row[0] }}</code></td><td>{{ row[1] }}</td><td><span class="pill" :class="row[2]">{{ row[2] === 'required' ? '必填' : row[2] === 'conditional' ? '条件必填' : '选填' }}</span></td><td>{{ row[3] }}</td></tr></tbody>
    </table></div>
  </section>

  <section class="section">
    <div class="section-header"><h2 class="section-title">响应示例</h2></div>
    <ModeSwitch v-model="mode" :modes="modes" :tool="tool" kind="响应示例输入方式" />
    <div class="code-box hover-copy-box"><pre>{{ responseCode }}</pre><button class="hover-copy-btn" type="button" @click="copy(responseCode, '响应示例已复制')">⧉ 复制</button></div>
  </section>
  <div v-if="copied" class="toast show">{{ copied }}</div>
</template>
