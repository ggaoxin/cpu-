<script lang="ts">
// 模块级“当前展开的下拉”登记：保证全局同时只有一个菜单打开
let activeCloser: (() => void) | null = null
</script>

<script setup lang="ts">
// 统一自定义下拉框（问题清单 #2.2 / 第三阶段）。
// 替代原生 <select>：闭合态与展开列表都用设计稿样式（白色框/白色菜单、
// 选中项蓝色、hover 浅灰、圆角/边框/箭头）。菜单 Teleport 到 body 固定定位，
// 避开 .form-grid 等内部滚动容器的 overflow 裁剪；空间不足时向上展开。
// 契约与原生一致：先 emit update:modelValue 再 emit change；未知/空值只显示
// 占位文字，不悄悄替换成第一项；disabled 选项不可选。
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'

interface Opt { value: string; label: string; disabled?: boolean }

const props = withDefaults(defineProps<{
  modelValue: string
  options: Opt[]
  disabled?: boolean
  placeholder?: string
}>(), { disabled: false, placeholder: '' })

const emit = defineEmits<{ 'update:modelValue': [value: string]; change: [value: string] }>()

const rootEl = ref<HTMLElement | null>(null)
const triggerEl = ref<HTMLButtonElement | null>(null)
const menuEl = ref<HTMLElement | null>(null)
const open = ref(false)
const activeIdx = ref(-1)
const menuStyle = ref<{ left: string; top: string; width: string; maxHeight: string; transform: string } | null>(null)

let uidSeed = Math.floor(Math.random() * 1e6)
const listId = `app-select-list-${uidSeed += 1}`
const activeOptionId = computed(() => (open.value && activeIdx.value >= 0 ? `${listId}-opt-${activeIdx.value}` : undefined))

const selectedIdx = computed(() => props.options.findIndex(o => o.value === props.modelValue))
const selectedOpt = computed(() => (selectedIdx.value >= 0 ? props.options[selectedIdx.value] : undefined))
// 找不到当前值（含空值/占位）时只显示占位文字，绝不静默换成第一项
const displayLabel = computed(() => selectedOpt.value?.label ?? props.placeholder)
const isPlaceholder = computed(() => !selectedOpt.value && !!props.placeholder)

function enabledIndices() {
  const out: number[] = []
  props.options.forEach((o, i) => { if (!o.disabled) out.push(i) })
  return out
}

// ── 定位：贴触发框下方，下方空间不够且上方更高时向上展开；左右夹在视口内。
// 向上展开用 top=触发框上缘-4 + translateY(-100%)：菜单底边始终紧贴触发框，
// 高度由 maxHeight 限定在真实可用上方空间内（无需测量渲染高度）。
// 触发框已出视口或被滚动容器裁掉时菜单失去锚点，直接关闭，不再追踪。
// maxHeight 只受真实可用空间约束（不加人为下限，避免制造越界悬挂）。──
function reposition() {
  const root = rootEl.value
  if (!root) return
  const r = root.getBoundingClientRect()
  if (!triggerVisible(r)) { close(); return }
  const width = Math.max(r.width, 132)
  const vw = window.innerWidth
  const vh = window.innerHeight
  const left = Math.min(Math.max(8, r.left), Math.max(8, vw - width - 8))
  const spaceDown = vh - r.bottom - 12
  const spaceUp = r.top - 12
  const preferUp = spaceDown < 132 && spaceUp > spaceDown
  const maxHeight = Math.min(preferUp ? spaceUp : spaceDown, vh - 16)
  if (maxHeight <= 0) { close(); return }
  menuStyle.value = preferUp
    ? { left: `${left}px`, top: `${r.top - 4}px`, width: `${width}px`, maxHeight: `${maxHeight}px`, transform: 'translateY(-100%)' }
    : { left: `${left}px`, top: `${r.bottom + 4}px`, width: `${width}px`, maxHeight: `${maxHeight}px`, transform: '' }
}

// 触发框可见性：与视口相交，且未被任一 overflow 裁剪祖先完全裁掉
function triggerVisible(r: DOMRect): boolean {
  const vw = window.innerWidth
  const vh = window.innerHeight
  if (r.bottom <= 0 || r.top >= vh || r.right <= 0 || r.left >= vw) return false
  let el: HTMLElement | null = rootEl.value?.parentElement ?? null
  while (el && el !== document.body) {
    const s = getComputedStyle(el)
    if (/(auto|hidden|scroll|clip)/.test(`${s.overflow}${s.overflowX}${s.overflowY}`)) {
      const c = el.getBoundingClientRect()
      if (r.bottom <= c.top || r.top >= c.bottom || r.right <= c.left || r.left >= c.right) return false
    }
    el = el.parentElement
  }
  return true
}

function onDocMouseDown(e: MouseEvent) {
  const t = e.target as Node
  if (rootEl.value?.contains(t) || menuEl.value?.contains(t)) return
  close()
}
function onDocKeyDown(e: KeyboardEvent) {
  if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); close(); triggerEl.value?.focus() }
  else if (e.key === 'Tab') { close() }
}
function onReposition() { if (open.value) reposition() }

function openMenu() {
  if (props.disabled || open.value) return
  activeCloser?.() // 关掉别的下拉，保证全局同时只有一个打开
  activeCloser = close
  open.value = true
  const en = enabledIndices()
  activeIdx.value = selectedIdx.value >= 0 && !props.options[selectedIdx.value].disabled
    ? selectedIdx.value
    : (en.length ? en[0] : -1)
  reposition()
  document.addEventListener('mousedown', onDocMouseDown, true)
  document.addEventListener('keydown', onDocKeyDown, true)
  window.addEventListener('scroll', onReposition, true)
  window.addEventListener('resize', onReposition)
  nextTick(() => {
    reposition()
    menuEl.value?.querySelector<HTMLElement>('.app-select-option.is-active')?.scrollIntoView({ block: 'nearest' })
  })
}

function close() {
  if (!open.value) return
  open.value = false
  activeIdx.value = -1
  if (activeCloser === close) activeCloser = null
  document.removeEventListener('mousedown', onDocMouseDown, true)
  document.removeEventListener('keydown', onDocKeyDown, true)
  window.removeEventListener('scroll', onReposition, true)
  window.removeEventListener('resize', onReposition)
}

function toggle() { open.value ? close() : openMenu() }

function move(delta: 1 | -1) {
  const en = enabledIndices()
  if (!en.length) return
  const pos = en.indexOf(activeIdx.value)
  const next = pos === -1 ? (delta === 1 ? 0 : en.length - 1) : (pos + delta + en.length) % en.length
  activeIdx.value = en[next]
  nextTick(() => menuEl.value?.querySelector<HTMLElement>(`.app-select-option[data-idx="${activeIdx.value}"]`)?.scrollIntoView({ block: 'nearest' }))
}

function moveEdge(last: boolean) {
  const en = enabledIndices()
  if (!en.length) return
  activeIdx.value = last ? en[en.length - 1] : en[0]
  nextTick(() => menuEl.value?.querySelector<HTMLElement>(`.app-select-option[data-idx="${activeIdx.value}"]`)?.scrollIntoView({ block: 'nearest' }))
}

function commit(idx: number) {
  const opt = props.options[idx]
  if (!opt || opt.disabled) return
  // 原生 change 语义：点击当前已选中项只关菜单，不 emit（避免误清用户已选文件/输入）；
  // 实际变化时先 emit update:modelValue，再 emit change
  if (opt.value === props.modelValue) { close(); return }
  emit('update:modelValue', opt.value)
  emit('change', opt.value)
  close()
  triggerEl.value?.focus()
}

function onTriggerKeydown(e: KeyboardEvent) {
  if (props.disabled) return
  if (!open.value) {
    if (['ArrowDown', 'ArrowUp', 'Enter', ' '].includes(e.key)) { e.preventDefault(); openMenu() }
    return
  }
  if (e.key === 'ArrowDown') { e.preventDefault(); move(1) }
  else if (e.key === 'ArrowUp') { e.preventDefault(); move(-1) }
  else if (e.key === 'Home') { e.preventDefault(); moveEdge(false) }
  else if (e.key === 'End') { e.preventDefault(); moveEdge(true) }
  else if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); if (activeIdx.value >= 0) commit(activeIdx.value) }
}

onBeforeUnmount(() => {
  close() // 移除监听并注销“当前打开”登记
})

// options 动态变化（历史列表加载等）时夹住键盘焦点位置
watch(() => props.options.length, () => { if (open.value && activeIdx.value >= props.options.length) moveEdge(false) })

defineExpose({ close })
</script>

<template>
  <div ref="rootEl" class="app-select">
    <button
      ref="triggerEl"
      type="button"
      class="app-select-trigger"
      :disabled="disabled"
      role="combobox"
      aria-haspopup="listbox"
      :aria-expanded="open"
      :aria-controls="open ? listId : undefined"
      :aria-activedescendant="activeOptionId"
      @click="toggle"
      @keydown="onTriggerKeydown"
    >
      <span class="app-select-label" :class="{ 'is-placeholder': isPlaceholder }">{{ displayLabel }}</span>
      <i class="app-select-arrow" aria-hidden="true"></i>
    </button>
    <Teleport to="body">
      <ul v-if="open" ref="menuEl" :id="listId" class="app-select-menu" role="listbox" :style="menuStyle">
        <!-- 与原生一致：仅剩“暂无…”占位时，菜单里显示一行不可选的占位项 -->
        <li v-if="!options.length && placeholder" :id="`${listId}-opt-empty`" class="app-select-option is-disabled" role="option" :aria-disabled="true" aria-selected="false">{{ placeholder }}</li>
        <li
          v-for="(opt, i) in options"
          :id="`${listId}-opt-${i}`"
          :key="`${opt.value}-${i}`"
          class="app-select-option"
          :class="{ 'is-selected': i === selectedIdx, 'is-active': i === activeIdx, 'is-disabled': opt.disabled }"
          role="option"
          :data-idx="i"
          :aria-selected="i === selectedIdx"
          :aria-disabled="opt.disabled || undefined"
          @mousedown.prevent
          @click="commit(i)"
        >{{ opt.label }}</li>
      </ul>
    </Teleport>
  </div>
</template>
