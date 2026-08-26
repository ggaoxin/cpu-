<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { ToolDefinition } from '../types'
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
const correctionLogs = ref<Array<{ operation: string; object: string; target: string; reason: string; status: string }>>([])
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

function renderCorrectionLog(panel: Element | null) {
  const tbody = panel?.querySelector('[data-correction-log]')
  if (!tbody) return
  tbody.innerHTML = correctionLogs.value.length
    ? correctionLogs.value.map((row, index) => `<tr><td>${index + 1}</td><td>${row.operation}</td><td>${row.object}</td><td>${row.target}</td><td>${row.reason}</td><td>${row.status}</td></tr>`).join('')
    : '<tr><td colspan="6" style="text-align:center;color:#8a96a6">暂无校正记录</td></tr>'
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
    const drawer = reviewRoot.querySelector<HTMLElement>('[data-review-evidence-drawer]')
    drawer?.removeAttribute('hidden')
    reviewRoot.querySelectorAll<HTMLElement>('[data-review-document]').forEach(row => {
      row.classList.toggle('review-trace-highlight', row.dataset.reviewDocument === documentId)
    })
    const evidenceRow = [...reviewRoot.querySelectorAll<HTMLElement>('[data-review-document]')]
      .find(row => row.dataset.reviewDocument === documentId)
    evidenceRow?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
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
    if (detail) {
      detail.hidden = !detail.hidden
      detailButton.textContent = detail.hidden ? '查看详情' : '收起详情'
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
    fetch(`/api/v1/classification-results/${encodeURIComponent(recordId)}/confirm`, {
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

  const correctionButton = target.closest<HTMLElement>('[data-correction-action]')
  if (correctionButton) {
    const panel = correctionButton.closest('[data-viz-panel="correction"]')
    const documentSelect = panel?.querySelector<HTMLSelectElement>('[data-correction-document]')
    const targetSelect = panel?.querySelector<HTMLSelectElement>('[data-correction-target]')
    const reasonInput = panel?.querySelector<HTMLInputElement>('[data-correction-reason]')
    const selected = documentSelect?.selectedOptions?.[0]
    const sourceCluster = selected?.dataset.cluster || '—'
    const operationCode = correctionButton.dataset.correctionAction || 'move'
    const labels: Record<string, string> = { move: '移动文献', merge: '合并类簇', split: '拆分类簇' }
    correctionLogs.value.push({
      operation: labels[operationCode] || operationCode,
      object: operationCode === 'move' ? documentSelect?.value || '—' : sourceCluster,
      target: operationCode === 'split' ? `${sourceCluster}-NEW` : targetSelect?.value || '—',
      reason: reasonInput?.value.trim() || '未填写',
      status: '待提交',
    })
    renderCorrectionLog(panel)
    const status = panel?.querySelector('[data-correction-status]')
    if (status) status.textContent = `已记录 ${correctionLogs.value.length} 条校正，等待提交。`
    return
  }

  const correctionSubmit = target.closest('[data-correction-submit]')
  if (correctionSubmit) {
    const panel = correctionSubmit.closest('[data-viz-panel="correction"]')
    const status = panel?.querySelector('[data-correction-status]')
    if (!correctionLogs.value.length) {
      if (status) status.textContent = '请先记录至少一条移动、合并或拆分操作。'
      return
    }
    correctionLogs.value = correctionLogs.value.map(row => ({ ...row, status: '已提交' }))
    renderCorrectionLog(panel)
    if (status) status.textContent = `已提交 ${correctionLogs.value.length} 条校正反馈。`
  }
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape' && props.open) close()
}

watch(() => props.open, open => {
  setBodyState(open)
  if (open) {
    correctionLogs.value = []
    nextTick(removePrototypeExportActions)
  }
})

watch(() => [props.toolId, props.response], () => {
  correctionLogs.value = []
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
            <div class="visualization-modal-subtitle-v645">可视化内容与当前响应 JSON 保持一致</div>
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
