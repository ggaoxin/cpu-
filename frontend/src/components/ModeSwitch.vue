<script setup lang="ts">
import { ref } from 'vue'
import type { InputMode, ToolDefinition } from '../types'
import { labelFor } from '../utils/tooling'
import { useSliderThumb } from '../utils/sliderThumb'
const props = defineProps<{ modes: InputMode[]; modelValue: InputMode; tool: ToolDefinition; kind?: string }>()
const emit = defineEmits<{ 'update:modelValue': [mode: InputMode] }>()
// 滑块式切换：白色滑块随选中项滑动（见 app.css .api-mode-thumb）
const switchEl = ref<HTMLElement | null>(null)
const { thumbStyle, ready } = useSliderThumb(switchEl, () => props.modelValue)
</script>

<template>
  <div class="api-mode-wrap">
    <div ref="switchEl" class="api-mode-switch" :style="{ gridTemplateColumns: `repeat(${modes.length}, minmax(0, 1fr))` }" :aria-label="kind || '输入方式'">
      <span class="api-mode-thumb" aria-hidden="true" :data-ready="ready" :style="thumbStyle"></span>
      <button v-for="mode in modes" :key="mode" class="api-mode-btn" :class="{ active: mode === modelValue }" type="button" @click="emit('update:modelValue', mode)">{{ labelFor(tool, mode) }}</button>
    </div>
  </div>
</template>
