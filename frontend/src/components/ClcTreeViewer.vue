<template>
  <section class="section clc-tree-section-v756">
    <div class="section-header"><h2 class="section-title">中图分类法（CLC）标准分类体系</h2>
      <button class="outline-btn" @click="$router.back()">返回</button></div>
    <div class="clc-tree-toolbar-v756">
      <input v-model="search" class="input clc-tree-search-v756" placeholder="搜索分类号或名称（如 TP3、计算机）" />
      <select v-model="domainFilter" class="select clc-tree-domain-v756">
        <option value="">全部领域</option>
        <option v-for="d in domainList" :key="d.code" :value="d.code">{{ d.code }} {{ d.name }}</option>
      </select>
      <button class="outline-btn" @click="expandAll = !expandAll">{{ expandAll ? '全部收起' : '全部展开' }}</button>
    </div>
    <div class="clc-tree-body-v756">
      <div v-if="loading" class="clc-tree-loading-v756">加载中…</div>
      <div v-else-if="filteredTop.length === 0" class="clc-tree-empty-v756">未找到匹配的分类体系</div>
      <template v-for="node in filteredTop" :key="node.code">
        <div class="clc-tree-l1-v756" @click="toggle(node.code)">
          <span class="clc-tree-toggle-v756">{{ expanded.has(node.code) ? '▾' : '▸' }}</span>
          <span class="clc-tree-code-v756">{{ node.code }}</span>
          <span class="clc-tree-name-v756">{{ node.name }}</span>
          <span class="clc-tree-count-v756">{{ Object.keys(node.children).length }} 个二级类目</span>
        </div>
        <div v-if="expanded.has(node.code)" class="clc-tree-l2-group-v756">
          <template v-for="l2 in visibleChildren(node)" :key="l2.code">
            <div class="clc-tree-l2-v756" @click="toggle(l2.code)">
              <span class="clc-tree-toggle-v756">{{ expanded.has(l2.code) ? '▾' : '▸' }}</span>
              <span class="clc-tree-code-v756">{{ l2.code }}</span>
              <span class="clc-tree-name-v756">{{ l2.name }}</span>
              <span class="clc-tree-count-v756">{{ Object.keys(l2.children).length }} 个三级类目</span>
            </div>
            <div v-if="expanded.has(l2.code)" class="clc-tree-l3-group-v756">
              <div v-for="l3 in visibleGrandchildren(l2)" :key="l3.code" class="clc-tree-l3-v756">
                <span class="clc-tree-code-v756">{{ l3.code }}</span>
                <span class="clc-tree-name-v756">{{ l3.name }}</span>
              </div>
              <div v-if="Object.keys(l2.children).length > visibleGrandchildren(l2).length"
                   class="clc-tree-more-v756" @click="showAll(l2.code)">
                显示全部 {{ Object.keys(l2.children).length }} 个三级类目 ▾
              </div>
            </div>
          </template>
        </div>
      </template>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'

interface TreeNode { code: string; name: string; children: Record<string, TreeNode> | string }
const loading = ref(true)
const tree = ref<Record<string, TreeNode>>({})
const search = ref('')
const domainFilter = ref('')
const expandAll = ref(false)
const expanded = ref(new Set<string>())
const showAllSet = ref(new Set<string>())

const domainList = [
  { code: '01', name: '数学与计算科学', prefixes: ['O1'] },
  { code: '02', name: '力学与工程力学', prefixes: ['O3', 'TB1'] },
  { code: '03', name: '物理学与应用物理', prefixes: ['O4'] },
  { code: '04', name: '化学与化学科学', prefixes: ['O6'] },
  { code: '05', name: '天文学与空间科学', prefixes: ['P1'] },
  { code: '06', name: '地球科学与地质资源', prefixes: ['P5', 'P6'] },
  { code: '07', name: '测绘遥感与地理信息', prefixes: ['P2'] },
  { code: '08', name: '气象海洋科学', prefixes: ['P4', 'P7'] },
  { code: '09', name: '生物科学与生物技术', prefixes: ['Q'] },
  { code: '10', name: '医学与卫生健康', prefixes: ['R'] },
  { code: '11', name: '药学与毒理学', prefixes: ['R9'] },
  { code: '12', name: '农业科学与农业工程', prefixes: ['S'] },
  { code: '13', name: '林业畜牧兽医与水产', prefixes: ['S7', 'S8', 'S9'] },
  { code: '14', name: '材料科学与材料工程', prefixes: ['TB3', 'TG'] },
  { code: '15', name: '矿业与矿物加工', prefixes: ['TD'] },
  { code: '16', name: '石油与天然气工程', prefixes: ['TE'] },
  { code: '17', name: '冶金与金属加工', prefixes: ['TF', 'TG1'] },
  { code: '18', name: '机械工程与智能制造', prefixes: ['TH'] },
  { code: '19', name: '仪器仪表与计量检测', prefixes: ['TH7', 'TB9'] },
  { code: '20', name: '能源与动力工程', prefixes: ['TK'] },
  { code: '21', name: '核科学与核工程', prefixes: ['TL'] },
  { code: '22', name: '电气工程与电力系统', prefixes: ['TM'] },
  { code: '23', name: '电子通信与半导体', prefixes: ['TN'] },
  { code: '24', name: '自动化与控制工程', prefixes: ['TP2', 'TP27'] },
  { code: '25', name: '人工智能与计算机技术', prefixes: ['TP'] },
  { code: '26', name: '化学工程与过程工业', prefixes: ['TQ'] },
  { code: '27', name: '轻工食品与纺织', prefixes: ['TS'] },
  { code: '28', name: '建筑与土木工程', prefixes: ['TU'] },
  { code: '29', name: '水利与水电工程', prefixes: ['TV'] },
  { code: '30', name: '交通运输工程', prefixes: ['U'] },
  { code: '31', name: '航空航天工程', prefixes: ['V'] },
  { code: '32', name: '环境与安全工程', prefixes: ['X'] },
]

onMounted(async () => {
  try { const r = await fetch('/clc-tree-data.json'); tree.value = await r.json() } catch { /* 静默 */ }
  loading.value = false
})

const filteredTop = computed(() => {
  const result: { code: string; name: string; children: Record<string, TreeNode> }[] = []
  const domainPrefixes = domainFilter.value ? domainList.find(d => d.code === domainFilter.value)?.prefixes || [] : []
  const q = search.value.trim().toLowerCase()
  for (const [code, node] of Object.entries(tree.value)) {
    const children = (typeof node.children === 'object' && node.children !== null) ? node.children : {}
    if (domainPrefixes.length && !domainPrefixes.some(p => code.startsWith(p))) {
      const hasMatch = Object.keys(children).some(l2 => domainPrefixes.some(p => l2.startsWith(p)))
      if (!hasMatch) continue
    }
    if (q && !code.toLowerCase().includes(q) && !node.name.toLowerCase().includes(q)) {
      const childMatch = Object.entries(children).some(([l2c, l2]) =>
        l2c.toLowerCase().includes(q) || l2.name.toLowerCase().includes(q))
      if (!childMatch) continue
    }
    result.push({ code, name: node.name, children })
  }
  return result
})

function toggle(code: string) { expanded.value.has(code) ? expanded.value.delete(code) : expanded.value.add(code); expanded.value = new Set(expanded.value) }
function visibleChildren(node: { children: Record<string, TreeNode> }): TreeNode[] {
  return Object.entries(node.children).map(([code, v]) => ({ code, name: v.name, children: (v as TreeNode).children || {} }))
}
function visibleGrandchildren(l2: TreeNode): TreeNode[] {
  const children = (typeof l2.children === 'object' && l2.children !== null) ? l2.children : {}
  const all = Object.entries(children).map(([code, v]) => ({ code, name: typeof v === 'string' ? v : (v as TreeNode).name, children: {} }))
  const q = search.value.trim().toLowerCase()
  if (q) return all.filter(n => n.code.toLowerCase().includes(q) || n.name.toLowerCase().includes(q)).slice(0, 50)
  if (showAllSet.value.has(l2.code)) return all
  return all.slice(0, 20)
}
function showAll(code: string) { showAllSet.value.add(code); showAllSet.value = new Set(showAllSet.value) }
</script>
