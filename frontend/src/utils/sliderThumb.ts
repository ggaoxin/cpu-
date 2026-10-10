import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch, type Ref } from 'vue'

/**
 * 滑块式 tab 切换的滑块定位（问题清单 #1：切换时滑块滑动动画）。
 *
 * 测量容器内 `.active` 按钮相对容器 padding 盒的几何位置，输出绝对定位
 * 滑块的样式；滑动本身由 app.css 中滑块的 transform transition 完成。
 * 容器尺寸变化（窗口缩放、折叠侧栏、字体加载完成、modes 增减）自动重测。
 */
export function useSliderThumb(rootRef: Ref<HTMLElement | null>, source: () => unknown) {
  const x = ref(0)
  const y = ref(0)
  const w = ref(0)
  const h = ref(0)
  const ready = ref(false)
  let ro: ResizeObserver | undefined

  function update() {
    const root = rootRef.value
    if (!root) return
    const el = root.querySelector<HTMLElement>('button.active')
    if (!el) { ready.value = false; return }
    // 绝对定位起点是容器 padding 盒边：getBoundingClientRect 差值给出相对容器
    // 边框盒的位移，再扣 border 宽度；全程保留小数（offsetLeft/offsetWidth 会
    // 取整，grid 布局下 323.5px 宽会被舍入成 324 造成半像素错位）。
    const rootRect = root.getBoundingClientRect()
    const elRect = el.getBoundingClientRect()
    x.value = elRect.left - rootRect.left - root.clientLeft
    y.value = elRect.top - rootRect.top - root.clientTop
    w.value = elRect.width
    h.value = elRect.height
    ready.value = true
  }

  watch(source, () => { nextTick(update) })
  onMounted(() => {
    nextTick(update)
    // 字体加载完成后文字宽度变化会挪动按钮位置，滑块需要跟随
    document.fonts?.ready.then(update).catch(() => {})
    ro = new ResizeObserver(() => update())
    watch(rootRef, (el, prev) => {
      if (prev) ro?.unobserve(prev)
      if (el) ro?.observe(el)
    }, { immediate: true })
  })
  onBeforeUnmount(() => ro?.disconnect())

  const thumbStyle = computed(() => ready.value
    ? { transform: `translate(${x.value}px, ${y.value}px)`, width: `${w.value}px`, height: `${h.value}px` }
    : null)

  return { thumbStyle, ready }
}
