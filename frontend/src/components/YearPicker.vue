<template>
  <AppSelect v-model="year" :options="yearOptions" placeholder="年份（可选）" class="year-picker-v754" />
</template>

<script setup lang="ts">
// 发表时间·年份选择（2026-10-11 用户定稿二轮：只需年，选填——趋势分析只消费年，
// 且仅统计填了年份的文献）。值口径 YYYY（后端 _year_of 正则取年兼容）。
import { ref, watch } from 'vue'
import AppSelect from './AppSelect.vue'

const props = defineProps<{ modelValue: string }>()
const emit = defineEmits<{ (e: 'update:modelValue', v: string): void }>()

const currentYear = new Date().getFullYear()
const initial = (props.modelValue || '').match(/(19|20)\d{2}/)
const year = ref<string>(initial ? initial[0] : '')

// 1900~今年，倒序（近年靠前一眼可选）
const yearOptions = Array.from({ length: currentYear - 1900 + 1 }, (_, i) => {
  const y = String(currentYear - i)
  return { value: y, label: y }
})

watch(year, (y) => { emit('update:modelValue', y || '') })
// 外部赋值回显（2026-10-19 深度聚类元数据自动填充：解析完成后才写入年份，
// 此前仅挂载时读一次 modelValue，晚到的值不回显）
watch(() => props.modelValue, (v) => {
  const m = String(v || '').match(/(19|20)\d{2}/)
  const incoming = m ? m[0] : ''
  if (incoming !== year.value) year.value = incoming
})
</script>
