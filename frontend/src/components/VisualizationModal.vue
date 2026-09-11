<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { ToolDefinition } from '../types'
import { apiUrl } from '../services/api'
// Renderer markup and class names are copied from the V7.74 prototype result panels.
// @ts-expect-error The renderer intentionally remains plain JavaScript so its prototype templates stay verbatim.
import { renderPrototypeVisualization, visualizationTitle } from '../utils/prototypeVisualizationRenderers.js'

const props = defineProps<{
  open: boolean
  preview?: boolean
  toolId: string
  tool: ToolDefinition
  response: unknown
}>()
const emit = defineEmits<{ close: [] }>()
const visualizationHost = ref<HTMLElement | null>(null)
const prototypeBodyClasses: Record<string, string[]> = {
  'fund-move': ['v663-fund-move-active'],
  'zh-abstract-move': ['v663-fund-move-active'],
  'en-abstract-move': ['v663-fund-move-active'],
  'zh-classify': ['v667-zh-classify-active'],
  'en-classify': ['v668-en-classify-active'],
  'domain-classify': ['v669-domain-classify-active'],
  'zh-keyword': ['v670-zh-keyword-active'],
  'en-keyword': ['v675-en-keyword-active'],
  'relation-extract': ['v699-relation-active'],
  'deep-cluster': ['deep-cluster-active-v619', 'v704-deep-cluster-active'],
}
const allPrototypeBodyClasses = [...new Set(Object.values(prototypeBodyClasses).flat())]

const modalTitle = computed(() => visualizationTitle(props.toolId, props.tool.title))
// 本地可变副本：确认替换分类后更新它以触发重渲染，避免直接改只读 props.response
// 用 JSON 深拷贝而非 structuredClone：props.response 经 Vue 响应式系统后是 reactive Proxy
// （父组件 ref 对对象值做深度 reactive 包装），structuredClone(Proxy) 会抛 DataCloneError
// 导致组件 update 崩溃、连带按钮状态卡死；分类结果为纯 JSON，JSON 深拷贝等效且安全
const safeClone = (value: any): any => (value == null ? value : JSON.parse(JSON.stringify(value)))
const localResponse = ref<any>(safeClone(props.response))
watch(() => props.response, next => { localResponse.value = safeClone(next) })
const visualizationHtml = computed(() => renderPrototypeVisualization(props.toolId, localResponse.value))

function close() {
  emit('close')
}

function setBodyState(open: boolean) {
  document.body.classList.toggle('visualization-modal-open-v645', open)
  allPrototypeBodyClasses.forEach(className => {
    document.body.classList.toggle(className, open && prototypeBodyClasses[props.toolId]?.includes(className))
  })
}

function removePrototypeExportActions() {
  const host = visualizationHost.value
  if (!host) return
  host.querySelectorAll('[data-viz-export], [data-relation-export], [data-result-use]').forEach(node => node.remove())
  host.querySelectorAll<HTMLElement>([
    '[class*="result-actions"]',
    '[class*="result-use-actions"]',
    '[class*="output-actions"]',
    '[class*="export-actions"]',
    '[class*="toolbar-actions"]',
  ].join(',')).forEach(group => {
    if (!group.textContent?.trim() && !group.children.length) group.style.display = 'none'
  })
}

function switchPanels(root: Element | null, tabSelector: string, panelSelector: string, name: string, tab: Element) {
  if (!root) return
  root.querySelectorAll(tabSelector).forEach(item => item.classList.toggle('active', item === tab))
  root.querySelectorAll<HTMLElement>(panelSelector).forEach(panel => {
    const panelName = panel.getAttribute('data-viz-panel') || panel.getAttribute('data-relation-panel')
    const active = panelName === name
    panel.classList.toggle('active', active)
    panel.hidden = !active
  })
}



// 确认成功后，用所选候选的主/次分类替换本地响应副本，触发可视化重渲染
function applyConfirmedClassification(recordIndex: string, candidateId: string, primaryCode: string, secondaryCodes: string[]) {
  const resp = localResponse.value
  const data = resp?.data ?? resp
  let payload: any = null
  if (Array.isArray(data?.results)) {
    const item = data.results[Number(recordIndex)]
    payload = item ? (item.result ?? item.data ?? item) : null
  } else {
    payload = data
  }
  if (!payload || typeof payload !== 'object') return
  const candidates = Array.isArray(payload.candidate_classifications) ? payload.candidate_classifications
    : (Array.isArray(payload.candidates) ? payload.candidates : [])
  const cand: any = candidates.find((c: any) => String(c?.candidate_id || '') === String(candidateId)) || {}
  const mainName = cand.main_name || cand.label || ''
  const mainPath = cand.main_path || cand.classification_path || []
  const auxCode = cand.aux_code
  const auxName = cand.aux_name || ''
  const auxPath = cand.aux_path || []
  const conf = cand.confidence
  const newPrimary: any = { role: 'main', clc_code: primaryCode, code: primaryCode, label: mainName, category_name: mainName, classification_path: mainPath, path: mainPath, confidence: conf, level_1: cand.level_1 || '', level_2: cand.level_2 || '', level_3: cand.level_3 || '' }
  const newSecondary = auxCode ? { role: 'secondary', clc_code: auxCode, code: auxCode, label: auxName, category_name: auxName, classification_path: auxPath, path: auxPath, confidence: conf } : null
  const newClassifications = [newPrimary, newSecondary].filter(Boolean)
  payload.classifications = newClassifications
  payload.multilevel_classification_results = newClassifications
  payload.primary_classification = newPrimary
  if (newSecondary) payload.secondary_classification = newSecondary
  if (payload.manual_confirmation && typeof payload.manual_confirmation === 'object') {
    payload.manual_confirmation.status = 'confirmed'
  } else {
    payload.manual_confirmation = { status: 'confirmed' }
  }
  payload.confirmation_status = 'confirmed'
}

function handleVisualizationClick(event: MouseEvent) {
  const target = event.target
  if (!(target instanceof Element)) return

  const reviewRoot = target.closest('[data-viz-group]')
  const reviewSourceButton = target.closest<HTMLElement>('[data-review-source]')
  if (reviewSourceButton && reviewRoot) {
    const documentId = reviewSourceButton.dataset.reviewSource || ''
    // 2026-09-11 用户定稿：点击文献chip → 该chip正下方就地展开此文献的证据表；
    // 同一chip再点一次收起。表格从隐藏存储区拷入（无状态，可多处复用）。
    const slot = reviewSourceButton.closest('.v710-review-progress')
      ?.querySelector<HTMLElement>('[data-review-inline-evidence]')
    const storeTable = documentId
      ? reviewRoot.querySelector<HTMLElement>(`[data-review-doc-table="${CSS.escape(documentId)}"]`)
      : null
    if (slot && storeTable) {
      if (!slot.innerHTML.trim()) slot.innerHTML = storeTable.innerHTML
      const showing = !slot.hidden && slot.dataset.doc === documentId
      // 手风琴语义（2026-09-11 用户定稿）：展开一个收起其他——点 FILE003 时
      // 之前展开的 FILE002 表收起，任何时刻至多一张证据表打开
      reviewRoot.querySelectorAll<HTMLElement>('[data-review-inline-evidence]').forEach(other => {
        if (other !== slot) other.hidden = true
      })
      slot.dataset.doc = documentId
      slot.hidden = showing
      if (!showing) slot.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    }
    return
  }

  const reviewEvidenceClose = target.closest('[data-review-evidence-close]')
  if (reviewEvidenceClose) {
    const drawer = reviewEvidenceClose.closest<HTMLElement>('[data-review-evidence-drawer]')
    if (drawer) drawer.hidden = true
    return
  }

  const reviewNodeButton = target.closest<HTMLElement>('[data-review-node-link]')
  if (reviewNodeButton && reviewRoot) {
    const nodeId = reviewNodeButton.dataset.reviewNodeLink || ''
    const node = [...reviewRoot.querySelectorAll<HTMLElement>('[data-review-node]')]
      .find(item => item.dataset.reviewNode === nodeId)
    reviewRoot.querySelectorAll('.review-trace-highlight').forEach(item => item.classList.remove('review-trace-highlight'))
    if (node) {
      node.classList.add('review-trace-highlight')
      node.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
    const drawer = reviewRoot.querySelector<HTMLElement>('[data-review-evidence-drawer]')
    if (drawer) drawer.hidden = true
    return
  }

  const relationTab = target.closest('[data-relation-tab]')
  if (relationTab) {
    switchPanels(
      relationTab.closest('.relation-result-root'),
      '[data-relation-tab]',
      '[data-relation-panel]',
      relationTab.getAttribute('data-relation-tab') || '',
      relationTab,
    )
    return
  }

  const tab = target.closest('[data-viz-tab]')
  if (tab) {
    switchPanels(
      tab.closest('[data-viz-group]'),
      '[data-viz-tab]',
      '[data-viz-panel]',
      tab.getAttribute('data-viz-tab') || '',
      tab,
    )
    return
  }

  const detailButton = target.closest('[data-viz-detail]')
  if (detailButton) {
    const root = detailButton.closest('[data-viz-group]') || visualizationHost.value
    const detail = root?.querySelector<HTMLElement>(`#${detailButton.getAttribute('data-viz-detail')}`)
    // 首列合并单元格同步（NER 表：文献列 rowspan 按主行数渲染，展开/收起
    // 详情行会增减一行参与布局，rowspan 不同步会溢出串到下一组——向上找
    // 本组的合并单元格 ±1；无合并单元格的表（关键词等）自动跳过）
    const adjustRowspan = (row: HTMLElement, delta: number) => {
      let r = row.previousElementSibling
      while (r) {
        const merged = r.querySelector?.('.viz-merged-source-cell[rowspan]')
        if (merged) {
          const span = Number(merged.getAttribute('rowspan')) || 1
          merged.setAttribute('rowspan', String(Math.max(1, span + delta)))
          break
        }
        r = r.previousElementSibling
      }
    }
    const collapseDetail = (row: HTMLElement, btn: HTMLElement) => {
      row.hidden = true
      btn.textContent = '查看详情'
      adjustRowspan(row, -1)
    }
    if (detail) {
      if (detail.hidden) {
        // 手风琴（2026-09-11 用户需求）：同表内收起其它已展开的详情行
        const table = detail.closest('table')
        table?.querySelectorAll<HTMLElement>('[data-viz-detail]').forEach(btn => {
          if (btn === detailButton) return
          const other = root?.querySelector<HTMLElement>(`#${btn.getAttribute('data-viz-detail')}`)
          if (other && !other.hidden) collapseDetail(other, btn)
        })
      }
      const willShow = detail.hidden
      detail.hidden = !detail.hidden
      detailButton.textContent = detail.hidden ? '查看详情' : '收起详情'
      adjustRowspan(detail, willShow ? 1 : -1)
    }
    return
  }

  const reselectButton = target.closest('[data-viz-reselect]')
  if (reselectButton) {
    const recordIndex = reselectButton.getAttribute('data-viz-reselect') || ''
    const resp = localResponse.value
    const data = resp?.data ?? resp
    let payload: any = null
    if (Array.isArray(data?.results)) {
      const item = data.results[Number(recordIndex)]
      payload = item ? (item.result ?? item.data ?? item) : null
    } else {
      payload = data
    }
    // 重新选择：仅重置本地确认状态（不调后端），让确认按钮恢复可点击，用户可继续切换候选
    if (payload && typeof payload === 'object') {
      if (payload.manual_confirmation && typeof payload.manual_confirmation === 'object') {
        payload.manual_confirmation.status = 'pending'
      } else {
        payload.manual_confirmation = { status: 'pending' }
      }
    }
    return
  }

  const confirmButton = target.closest('[data-viz-confirm]')
  if (confirmButton) {
    const recordIndex = confirmButton.getAttribute('data-viz-confirm') || ''
    const recordId = confirmButton.getAttribute('data-viz-confirm-record') || ''
    const root = confirmButton.closest('[data-viz-confirm-root]') || visualizationHost.value
    const select = root?.querySelector<HTMLSelectElement>(`[data-viz-confirm-select="${recordIndex}"]`)
    const option = select?.selectedOptions?.[0]
    const candidateId = option?.value || ''
    const primaryCode = option?.dataset.primary || ''
    const secondaryRaw = option?.dataset.secondary || ''
    const secondaryCodes = secondaryRaw ? [secondaryRaw] : []
    const resetLabel = confirmButton.getAttribute('data-viz-confirm-label') || '确认所选分类'
    if (!recordId) {
      window.alert('缺少 record_id，无法确认（请刷新结果后重试）')
      return
    }
    // 占位 option（当前首选）value="" 且无 data-primary：用户未选候选或直接点了当前首选
    if (!candidateId) {
      window.alert('当前首选已是正式结果并入库，无需确认。如需更换分类，请先从下拉框选择其他候选，再点击确认。')
      return
    }
    if (!primaryCode) {
      window.alert('该候选缺少主分类号，无法确认')
      return
    }
    confirmButton.textContent = '提交中…'
    confirmButton.setAttribute('disabled', 'disabled')
    fetch(apiUrl(`/api/v1/classification-results/${encodeURIComponent(recordId)}/confirm`), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ candidate_id: candidateId, primary_code: primaryCode, secondary_codes: secondaryCodes }),
    })
      .then(r => r.json())
      .then(body => {
        if (body.code !== 0) throw new Error(body.detail || body.message || '确认失败')
        applyConfirmedClassification(recordIndex, candidateId, primaryCode, secondaryCodes)
        // applyConfirmedClassification 已把本地确认状态置为 confirmed 并替换主/次分类，
        // 触发重渲染后按钮区自动切换为"已确认 + 重新选择"，无需手动改按钮文案
      })
      .catch(err => {
        window.alert(err.message || '确认失败')
        confirmButton.textContent = resetLabel
        confirmButton.removeAttribute('disabled')
      })
    return
  }

  const labelOkButton = target.closest('[data-viz-label-ok]')
  if (labelOkButton) {
    submitLabelReview(labelOkButton, labelOkButton.getAttribute('data-viz-label-text') || '')
    return
  }

  const labelEditButton = target.closest('[data-viz-label-edit]')
  if (labelEditButton) {
    const rowId = labelEditButton.getAttribute('data-viz-label-edit') || ''
    const row = labelEditButton.closest('[data-viz-group]')?.querySelector<HTMLElement>(`[data-viz-label-row="${CSS.escape(rowId)}"]`)
    if (row) {
      row.hidden = !row.hidden
      if (!row.hidden) row.querySelector<HTMLInputElement>('input')?.focus()
    }
    return
  }

  const labelSubmitButton = target.closest('[data-viz-label-submit]')
  if (labelSubmitButton) {
    const rowId = labelSubmitButton.getAttribute('data-viz-label-submit') || ''
    const panel = labelSubmitButton.closest('[data-viz-panel]')
    const input = panel?.querySelector<HTMLInputElement>(`[data-viz-label-input="${CSS.escape(rowId)}"]`)
    const text = (input?.value || '').trim()
    if (!text) {
      window.alert('请填写合适的标签后再提交')
      input?.focus()
      return
    }
    submitLabelReview(labelSubmitButton, text)
    return
  }

}

function clusterLabelItems(): { recordId: string; labels: any[] } | null {
  const resp: any = localResponse.value
  const data = resp?.data ?? resp
  let payload: any = null
  let recordId = ''
  if (Array.isArray(data?.results) && data.results[0]) {
    payload = data.results[0].result ?? data.results[0].data ?? data.results[0]
    recordId = String(data.results[0].record_id || '')
  } else {
    payload = data
    recordId = String(resp?.meta?.record_id || data?.record_id || '')
  }
  if (!payload || typeof payload !== 'object') return null
  return { recordId, labels: Array.isArray(payload.labels) ? payload.labels : [] }
}

// 类簇标签人工复核：✓正确=按推荐标签确认入库；✕修改=人工填写新标签后入库
function submitLabelReview(button: Element, labelText: string) {
  const clusterId = button.getAttribute('data-viz-label-ok') || button.getAttribute('data-viz-label-submit') || ''
  const panel = button.closest('[data-viz-panel]')
  const recordId = panel?.getAttribute('data-viz-label-record') || clusterLabelItems()?.recordId || ''
  if (!recordId) {
    window.alert('缺少 record_id，无法确认入库（请刷新结果后重试）')
    return
  }
  const submitBtn = button as HTMLButtonElement
  const resetText = submitBtn.textContent
  submitBtn.textContent = '提交中…'
  submitBtn.setAttribute('disabled', 'disabled')
  fetch(apiUrl(`/api/v1/cluster-labels/${encodeURIComponent(recordId)}/confirm`), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ cluster_id: clusterId, label_text: labelText }),
  })
    .then(r => r.json())
    .then(body => {
      if (body.code !== 0) throw new Error(body.detail || body.message || '确认失败')
      const found = clusterLabelItems()
      const item = found?.labels.find(entry => String(entry.cluster_id) === clusterId)
      if (item) {
        const original = String(item.recommended_label ?? item.label ?? '')
        item.label = labelText
        item.recommended_label = labelText
        item.user_confirmed = true
        item.manual_label = labelText !== original
        item.optimization_status = 'passed'
        item.difference_explanation = item.manual_label
          ? `人工复核：推荐标签「${original}」不正确，已人工改为「${labelText}」并入库。`
          : '人工复核：推荐标签正确，已确认入库。'
      }
    })
    .catch(err => {
      window.alert(err.message || '确认失败')
      submitBtn.textContent = resetText
      submitBtn.removeAttribute('disabled')
    })
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape' && props.open) close()
}

watch(() => props.open, open => {
  setBodyState(open)
  if (open) {
    nextTick(removePrototypeExportActions)
  }
})

watch(() => [props.toolId, props.response], () => {
  if (props.open) {
    setBodyState(true)
    nextTick(removePrototypeExportActions)
  }
})

onMounted(() => document.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => {
  document.removeEventListener('keydown', onKeydown)
  setBodyState(false)
})
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      id="visualizationModalV645"
      class="visualization-modal-v645"
      role="dialog"
      aria-modal="true"
      aria-labelledby="visualizationModalTitleV645"
      @mousedown.self="close"
    >
      <div class="visualization-modal-dialog-v645">
        <div class="visualization-modal-header-v645">
          <div class="visualization-modal-heading-v645">
            <h3 id="visualizationModalTitleV645" class="visualization-modal-title-v645">{{ modalTitle }}</h3>
            
          </div>
          <button
            id="visualizationModalCloseV645"
            class="visualization-modal-close-v645"
            type="button"
            aria-label="关闭可视化结果"
            @click="close"
          >×</button>
        </div>
        <div class="visualization-modal-body-v645">
          <div class="distribution-report-panel online-distribution-panel visualization-modal-panel-v645">
            <div class="distribution-report-title">{{ modalTitle }}</div>
            <div
              ref="visualizationHost"
              class="specialized-visualization-host-v804"
              @click="handleVisualizationClick"
              v-html="visualizationHtml"
            ></div>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>
