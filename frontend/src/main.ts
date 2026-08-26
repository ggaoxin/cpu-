import { createApp } from 'vue'
import App from './App.vue'
import './styles/prototype.generated.css'
import './styles/app.css'

document.body.classList.add('figma-ui-v717')

// 将滚轮交给当前仍可滚动的最近容器，避免隐藏滚动条的嵌套区域卡住滚轮。
document.addEventListener('wheel', (event) => {
  if (event.defaultPrevented || event.ctrlKey || event.shiftKey || event.deltaY === 0) return

  const scale = event.deltaMode === WheelEvent.DOM_DELTA_LINE
    ? 18
    : event.deltaMode === WheelEvent.DOM_DELTA_PAGE
      ? window.innerHeight
      : 1
  const delta = event.deltaY * scale
  const scrollTarget = event.composedPath().find((node): node is HTMLElement => {
    if (!(node instanceof HTMLElement)) return false
    const style = window.getComputedStyle(node)
    if (!/(auto|scroll)/.test(style.overflowY) || node.scrollHeight <= node.clientHeight + 1) return false
    if (delta > 0) return node.scrollTop < node.scrollHeight - node.clientHeight - 1
    return node.scrollTop > 1
  })

  if (!scrollTarget) return
  event.preventDefault()
  scrollTarget.scrollTop += delta
}, { capture: true, passive: false })

createApp(App).mount('#app')
