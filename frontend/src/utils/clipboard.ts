// 跨环境剪贴板工具。
// navigator.clipboard 仅在安全上下文（HTTPS 或 localhost）可用：集成到第三方
// 系统经 HTTP + 非 localhost 域名/IP 访问时它是 undefined，直接调用会全量
// "复制失败"（本地 localhost 正常，易漏测）。这里统一加 execCommand 兜底。
export async function copyText(text: string): Promise<void> {
  if (navigator.clipboard && window.isSecureContext) {
    try {
      await navigator.clipboard.writeText(text)
      return
    } catch {
      // 权限拒绝/iframe 未授权（allow="clipboard-write"）等，走下方兜底
    }
  }
  const textarea = document.createElement('textarea')
  textarea.value = text
  textarea.setAttribute('readonly', '')
  textarea.style.position = 'fixed'
  textarea.style.top = '-9999px'
  textarea.style.opacity = '0'
  document.body.appendChild(textarea)
  const activeElement = document.activeElement as HTMLElement | null
  textarea.focus()
  textarea.select()
  textarea.setSelectionRange(0, text.length)
  let ok = false
  try {
    ok = document.execCommand('copy')
  } catch {
    ok = false
  }
  document.body.removeChild(textarea)
  activeElement?.focus?.()
  if (!ok) throw new Error('复制失败：当前环境不允许访问剪贴板')
}
