<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import type { ToolGroup } from '../types'

const props = defineProps<{ groups: ToolGroup[]; activeId: string }>()
const emit = defineEmits<{ select: [id: string]; toggle: [] }>()
const flyoutGroup = ref<ToolGroup | null>(null)
const flyoutTop = ref(0)

const activeGroupName = computed(() =>
  props.groups.find(group => group.items.some(([itemId]) => itemId === props.activeId))?.name || ''
)

function openFlyout(group: ToolGroup, event: MouseEvent) {
  const target = event.currentTarget as HTMLElement
  flyoutGroup.value = group
  flyoutTop.value = Math.max(16, Math.min(target.getBoundingClientRect().top, window.innerHeight - 180))
}

// 单 item 分组直接直达选中，不弹三级 flyout（深度聚类/聚类标签生成/结构化综述等）
function handleGroupClick(group: ToolGroup, event: MouseEvent) {
  if (group.items.length === 1) {
    selectTool(group.items[0][0])
  } else {
    openFlyout(group, event)
  }
}

function selectTool(id: string) {
  emit('select', id)
  flyoutGroup.value = null
}

function closeOnOutside(event: MouseEvent) {
  const target = event.target as HTMLElement
  if (!target.closest('#libraryTree') && !target.closest('.v752-nav-flyout')) flyoutGroup.value = null
}

onMounted(() => document.addEventListener('click', closeOnOutside))
onBeforeUnmount(() => document.removeEventListener('click', closeOnOutside))
</script>

<template>
  <aside class="sidebar">
    <div class="sidebar-title-row"><div class="sidebar-title">算法列表</div><div class="menu-icon" title="收起导航" role="button" tabindex="0" @click="emit('toggle')" @keydown.enter="emit('toggle')">☰</div></div>
    <div class="menu-section sidebar-decorative-sections">
      <div class="sidebar-decorative-label">算法中心其他算法库（原型展示）</div>
      <div v-for="name in ['分类分析算法','回归分析算法','聚类分析算法','关联规则算法','时间序列算法','信息推荐算法','文本挖掘算法','统计分析算法','图挖掘算法','科技资源服务算法库','科技决策支持算法库','科技专题服务算法库']" :key="name" class="menu-section">
        <div class="menu-row menu-row-decorative"><span>{{ name }}</span></div>
      </div>
    </div>
    <div class="menu-section">
      <div class="menu-row expanded"><span>语义计算工具库</span><span class="chev" aria-hidden="true"><svg class="v727-chevron-svg" viewBox="0 0 12 12"><path d="M4.25 2.5L8.25 6L4.25 9.5Z" /></svg></span></div>
      <div id="libraryTree" class="library-tree">
        <div v-for="group in groups" :key="group.name" class="tool-group" :class="{ 'v752-group-active': activeGroupName === group.name }">
          <div class="tool-group-title" @click.stop="handleGroupClick(group, $event)"><span>{{ group.name }}</span><span v-if="group.items.length > 1" class="chev"><svg class="v727-chevron-svg" viewBox="0 0 12 12"><path d="M4.25 2.5L8.25 6L4.25 9.5Z" /></svg></span></div>
          <div class="tool-items" aria-hidden="true"><div v-for="item in group.items" :key="item[0]" class="tool-item">{{ item[1] }}</div></div>
        </div>
      </div>
    </div>
    <!-- 三级弹出菜单 Teleport 到 body:Safari/WebKit 下 position:fixed 元素若留在
         sticky/overflow/backdrop-filter 的侧栏祖先内,可能改以祖先为定位基准并被裁剪 -->
    <Teleport to="body">
      <div v-if="flyoutGroup" class="v752-nav-flyout v752-open" :style="{ top: `${flyoutTop}px` }" @click.stop>
        <div class="v752-nav-flyout-list">
          <button v-for="item in flyoutGroup.items" :key="item[0]" type="button" class="v752-nav-flyout-item" :class="{ 'v752-active': item[0] === activeId }" @click="selectTool(item[0])">
            <span>{{ item[1] }}</span><span class="v752-nav-flyout-item-arrow">›</span>
          </button>
        </div>
      </div>
    </Teleport>
  </aside>
</template>
