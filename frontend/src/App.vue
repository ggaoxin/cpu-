<script setup lang="ts">
import { computed, ref } from 'vue'
import { groups as generatedGroups } from './data/prototype.generated.js'
import { tools } from './data/tool-overrides'
import type { InputMode, ToolGroup } from './types'
import ToolSidebar from './components/ToolSidebar.vue'
import DocumentationPanel from './components/DocumentationPanel.vue'
import OnlineTester from './components/OnlineTester.vue'
import VisualizationModal from './components/VisualizationModal.vue'
import { modesFor, responseFor, supportsVisualization } from './utils/tooling'
import { appPath } from './services/api'

// The last tool-definition patch in V7.74 is the source of truth for both the
// page heading and its sidebar label. Keeping one label source prevents tiny
// late-prototype naming corrections from drifting between the two locations.
const groups = (generatedGroups as ToolGroup[]).map((group) => ({
  ...group,
  items: group.items.map(([id, label]) => [id, tools[id]?.title || label] as [string, string])
}))

// 每个工具一个独立路由 /tool/<toolId>：页面加载时按 URL 解析当前工具，
// 直链打开、刷新、浏览器回退/前进都按路由渲染对应工具页。
// 前缀可选：兼容子路径部署（/dma/sem/tool/x）与不带前缀的旧链接（/tool/x）。
const TOOL_ROUTE_RE = new RegExp(`^(?:${appPath('')})?/tool/([a-z0-9-]+)/?$`)
function toolIdFromLocation(): string {
  if (typeof window === 'undefined') return ''
  const match = window.location.pathname.match(TOOL_ROUTE_RE)
  return match && tools[match[1]] ? match[1] : ''
}
const activeId = ref(toolIdFromLocation() || 'zh-abstract-move')
// 侧栏开关:桌面端=收起/展开左栏;移动端(≤900px)=抽屉滑出/收起
const sidebarOpen = ref(true)
if (typeof window !== 'undefined' && window.innerWidth <= 900) sidebarOpen.value = false
const content = ref<HTMLElement | null>(null)
const modalOpen = ref(false)
const modalPreview = ref(false)
const currentResponse = ref<unknown>(null)
const tool = computed(() => tools[activeId.value])

// 独立页面路由：浏览器标签标题随当前工具页同步（如「深度聚类工具 · 语义计算工具库」）
document.title = `${tool.value.title} · 语义计算工具库`

function selectTool(id: string) {
  // 「语义计算工具库」子菜单：SPA 局部切换（2026-09-21 甲方反馈：此前
  // window.location.assign 整页跳转——重新加载整个 JS 包、白屏一闪，切换
  // 不流畅；别人的系统无刷新感。改 history.pushState 只换组件不刷新：
  // 地址栏更新、产生历史记录、组件因 :key 变化重挂载，全部局部完成）。
  if (!tools[id] || id === activeId.value) return
  activeId.value = id
  modalOpen.value = false
  currentResponse.value = null
  history.pushState({}, '', appPath(`/tool/${id}`))
  document.title = `${tools[id].title} · 语义计算工具库`
  content.value?.scrollTo({ top: 0 })
}

// 浏览器返回/前进：按当前 URL 恢复工具（pushState 路由的配套监听）
window.addEventListener('popstate', () => {
  const id = toolIdFromLocation() || 'zh-abstract-move'
  if (tools[id] && id !== activeId.value) {
    activeId.value = id
    modalOpen.value = false
    document.title = `${tools[id].title} · 语义计算工具库`
  }
})
function visualize(response: unknown) { currentResponse.value = response; modalPreview.value = false; modalOpen.value = true }
function previewVisualization(mode: InputMode) {
  if (!supportsVisualization(activeId.value)) return
  currentResponse.value = responseFor(tool.value, mode)
  modalPreview.value = true
  modalOpen.value = true
}
</script>

<template>
  <div class="platform-frame-v640" :class="{ 'sidebar-open': sidebarOpen, 'sidebar-collapsed': !sidebarOpen }">
    <div v-if="sidebarOpen" class="mobile-sidebar-backdrop" @click="sidebarOpen = false"></div>
    <button v-else class="mobile-nav-fab" type="button" aria-label="打开导航" @click="sidebarOpen = true">☰ 导航</button>
    <div class="app">
      <ToolSidebar :groups="groups" :active-id="activeId" @select="selectTool" />
      <main ref="content" class="content-wrap">
        <div class="page-shell">
          <div class="breadcrumb"><span>算法中心</span><span class="slash">/</span><span>语义计算工具库</span><span class="slash">/</span><strong>{{ tool.title }}</strong></div>
          <section class="main-card">
            <div class="hero">
              <h1>{{ tool.title }}</h1>
              <p>{{ tool.description }}</p>
              <div class="tag-row"><div class="tag-box"><b>功能特点</b><i aria-hidden="true"></i><span>{{ tool.features }}</span></div><div class="tag-box"><b>适用场景</b><i aria-hidden="true"></i><span>{{ tool.scenarios }}</span></div></div>
            </div>
            <DocumentationPanel :key="`${activeId}-docs`" :tool="tool" />
            <OnlineTester :key="`${activeId}-test`" :tool-id="activeId" :tool="tool" @visualize="visualize" @preview="previewVisualization" />
          </section>
          <div class="footer-note">语义计算工具库</div>
        </div>
      </main>
    </div>
  </div>
  <VisualizationModal :open="modalOpen" :preview="modalPreview" :tool-id="activeId" :tool="tool" :response="currentResponse" @close="modalOpen = false" />
</template>
