<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, useId, watch } from 'vue'
import type { ToolGroup } from '../types'

const props = defineProps<{ groups: ToolGroup[]; activeId: string }>()
const emit = defineEmits<{ select: [id: string] }>()
const rootEl = ref<HTMLElement | null>(null)
const triggerEl = ref<HTMLButtonElement | null>(null)
const treeEl = ref<HTMLElement | null>(null)
const open = ref(false)
const expanded = ref(new Set<string>())
const focusedKey = ref('')
const treeId = `algorithm-directory-${useId()}`
const menuStyle = ref<Record<string, string>>({})
const activeGroup = computed(() => props.groups.find(group => group.items.some(([id]) => id === props.activeId)))
const activeLabel = computed(() => activeGroup.value?.items.find(([id]) => id === props.activeId)?.[1] || '')

type TreeNode = { key: string; label: string; group: ToolGroup; toolId?: string; level: number; position: number; size: number }
// The same groups supplied to ToolSidebar determine branches and direct tools.
const nodes = computed<TreeNode[]>(() => props.groups.flatMap((group, index) => {
  if (group.items.length === 1) return [{ key: `tool:${group.items[0][0]}`, label: group.name, group, toolId: group.items[0][0], level: 1, position: index + 1, size: props.groups.length }]
  const parent: TreeNode = { key: `group:${group.name}`, label: group.name, group, level: 1, position: index + 1, size: props.groups.length }
  const children = expanded.value.has(group.name) ? group.items.map(([toolId, label], childIndex) => ({ key: `tool:${toolId}`, label, group, toolId, level: 2, position: childIndex + 1, size: group.items.length })) : []
  return [parent, ...children]
}))

function resetCurrentGroup() {
  expanded.value = new Set(activeGroup.value && activeGroup.value.items.length > 1 ? [activeGroup.value.name] : [])
  focusedKey.value = `tool:${props.activeId}`
}
function focusNode(key: string) {
  focusedKey.value = key
  nextTick(() => {
    const button = Array.from(treeEl.value?.querySelectorAll<HTMLButtonElement>('[role="treeitem"]') || []).find(el => el.dataset.key === key)
    button?.focus({ preventScroll: true })
    button?.scrollIntoView({ block: 'nearest' })
  })
}
function toggleGroup(group: ToolGroup) {
  const next = new Set(expanded.value)
  next.has(group.name) ? next.delete(group.name) : next.add(group.name)
  expanded.value = next
  focusedKey.value = `group:${group.name}`
}
function choose(node: TreeNode) {
  if (!node.toolId) { toggleGroup(node.group); return }
  if (node.toolId !== props.activeId) emit('select', node.toolId)
  close(true)
}
function reposition() {
  const r = triggerEl.value?.getBoundingClientRect()
  if (!r) return
  const vw = window.innerWidth, vh = window.innerHeight
  if (r.bottom <= 0 || r.top >= vh || r.right <= 0 || r.left >= vw) { close(); return }
  const width = Math.min(Math.max(r.width, 240), vw - 16)
  const spaceDown = vh - r.bottom - 12, spaceUp = r.top - 12
  const up = spaceDown < 160 && spaceUp > spaceDown
  const maxHeight = Math.min(560, up ? spaceUp : spaceDown)
  if (maxHeight <= 0) { close(); return }
  menuStyle.value = { left: `${Math.max(8, Math.min(r.left, vw - width - 8))}px`, top: `${up ? r.top - 4 : r.bottom + 4}px`, width: `${width}px`, maxHeight: `${maxHeight}px`, transform: up ? 'translateY(-100%)' : '' }
}
function outside(event: PointerEvent) {
  const target = event.target as Node
  if (!rootEl.value?.contains(target) && !treeEl.value?.contains(target)) close()
}
function escape(event: KeyboardEvent) {
  if (event.key === 'Escape') { event.preventDefault(); close(true) }
}
function openMenu() {
  if (open.value) return
  resetCurrentGroup()
  open.value = true
  reposition()
  if (!open.value) return
  document.addEventListener('pointerdown', outside, true)
  document.addEventListener('keydown', escape, true)
  window.addEventListener('scroll', reposition, true)
  window.addEventListener('resize', reposition)
  nextTick(() => { reposition(); focusNode(focusedKey.value) })
}
function close(restoreFocus = false) {
  open.value = false
  document.removeEventListener('pointerdown', outside, true)
  document.removeEventListener('keydown', escape, true)
  window.removeEventListener('scroll', reposition, true)
  window.removeEventListener('resize', reposition)
  if (restoreFocus) triggerEl.value?.focus()
}
function triggerKey(event: KeyboardEvent) {
  if (['ArrowDown', 'ArrowUp', 'Enter', ' '].includes(event.key)) { event.preventDefault(); openMenu() }
}
function treeKey(event: KeyboardEvent) {
  const index = nodes.value.findIndex(node => node.key === focusedKey.value)
  const node = nodes.value[index]
  if (event.key === 'Tab') { close(true); return }
  if (!node) return
  if (['ArrowDown', 'ArrowUp', 'Home', 'End', 'ArrowRight', 'ArrowLeft'].includes(event.key)) event.preventDefault()
  if (event.key === 'ArrowDown') focusNode(nodes.value[Math.min(index + 1, nodes.value.length - 1)].key)
  else if (event.key === 'ArrowUp') focusNode(nodes.value[Math.max(index - 1, 0)].key)
  else if (event.key === 'Home') focusNode(nodes.value[0].key)
  else if (event.key === 'End') focusNode(nodes.value[nodes.value.length - 1].key)
  else if (event.key === 'ArrowRight' && !node.toolId) {
    if (expanded.value.has(node.group.name)) focusNode(`tool:${node.group.items[0][0]}`)
    else toggleGroup(node.group)
  } else if (event.key === 'ArrowLeft') {
    if (!node.toolId && expanded.value.has(node.group.name)) toggleGroup(node.group)
    else if (node.level === 2) focusNode(`group:${node.group.name}`)
  }
}
watch(() => props.activeId, () => { if (open.value) { resetCurrentGroup(); focusNode(focusedKey.value) } })
onBeforeUnmount(() => close())
</script>

<template>
  <div ref="rootEl" class="algorithm-directory app-select">
    <button ref="triggerEl" type="button" class="app-select-trigger" aria-haspopup="tree" :aria-expanded="open" :aria-controls="open ? treeId : undefined" @click="open ? close() : openMenu()" @keydown="triggerKey">
      <span class="algorithm-directory-prefix">算法目录</span>
      <span class="app-select-label">{{ activeLabel }}</span>
      <i class="app-select-arrow" aria-hidden="true"></i>
    </button>
    <Teleport to="body">
      <div v-if="open" ref="treeEl" :id="treeId" class="algorithm-directory-menu app-select-menu" role="tree" aria-label="语义计算工具库算法目录" :style="menuStyle" @keydown="treeKey">
        <button v-for="node in nodes" :key="node.key" type="button" class="algorithm-directory-node" :class="{ 'is-group': !node.toolId, 'is-leaf': node.level === 2, 'is-selected': node.toolId === activeId }" role="treeitem" :data-key="node.key" :data-tool-id="node.toolId" :data-group="node.group.name" :aria-level="node.level" :aria-posinset="node.position" :aria-setsize="node.size" :aria-expanded="!node.toolId ? expanded.has(node.group.name) : undefined" :aria-selected="node.toolId ? node.toolId === activeId : undefined" :tabindex="focusedKey === node.key ? 0 : -1" @focus="focusedKey = node.key" @click="choose(node)">
          <span>{{ node.label }}</span>
          <svg v-if="!node.toolId" class="algorithm-directory-chevron" :class="{ expanded: expanded.has(node.group.name) }" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.4" aria-hidden="true"><path d="m4 2 4 4-4 4" /></svg>
        </button>
      </div>
    </Teleport>
  </div>
</template>
