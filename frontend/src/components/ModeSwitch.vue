<script setup lang="ts">
import type { InputMode, ToolDefinition } from '../types'
import { labelFor } from '../utils/tooling'
defineProps<{ modes: InputMode[]; modelValue: InputMode; tool: ToolDefinition; kind?: string }>()
const emit = defineEmits<{ 'update:modelValue': [mode: InputMode] }>()
</script>

<template>
  <div class="api-mode-wrap">
    <div class="api-mode-switch" :style="{ gridTemplateColumns: `repeat(${modes.length}, minmax(0, 1fr))` }" :aria-label="kind || '输入方式'">
      <button v-for="mode in modes" :key="mode" class="api-mode-btn" :class="{ active: mode === modelValue }" type="button" @click="emit('update:modelValue', mode)">{{ labelFor(tool, mode) }}</button>
    </div>
  </div>
</template>
