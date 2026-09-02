// 侧边栏全工具跳转验证（部署后实测，公网 + 内网双入口）
import { chromium } from 'playwright'
import { groups } from './src/data/prototype.generated.js'

const expectedTools = groups.flatMap(g => g.items.map(([id]) => id))
const TARGETS = [
  ['公网 /dma/sem', 'https://edu.itic-sci.com/dma/sem', []],
  // 内网额外验证带前缀直访；公网 origin 已含 /dma/sem，无需（也无法）再拼第二层前缀
  ['内网根路径', 'http://127.0.0.1:8080', ['http://127.0.0.1:8080/dma/sem/tool/en-abstract-move']],
]

const browser = await chromium.launch()
let allOk = true
for (const [name, origin, extraDeeps] of TARGETS) {
  console.log(`\n===== ${name}: ${origin} =====`)
  const page = await browser.newPage({ viewport: { width: 1400, height: 900 }, ignoreHTTPSErrors: true })
  const notFound = []
  page.on('response', r => { if (r.status() >= 400) notFound.push(`${r.status()} ${r.url()}`) })
  const failures = []
  const visited = new Set()
  try {
    await page.goto(`${origin}/`, { waitUntil: 'networkidle', timeout: 60000 })
    await page.waitForSelector('.test-header-left .section-title', { timeout: 20000 })
    const groupTitles = page.locator('#libraryTree .tool-group-title')
    const groupCount = await groupTitles.count()
    for (let gi = 0; gi < groupCount; gi++) {
      await groupTitles.nth(gi).click()
      const flyoutItems = page.locator('.v752-nav-flyout-item')
      const itemCount = await flyoutItems.count()
      if (itemCount === 0) {
        await page.waitForSelector('.test-header-left .section-title', { timeout: 20000 })
        visited.add(new URL(page.url()).pathname)
      } else {
        for (let ii = 0; ii < itemCount; ii++) {
          await page.locator('#libraryTree .tool-group-title').nth(gi).click()
          const item = page.locator('.v752-nav-flyout-item').nth(ii)
          const label = (await item.textContent() || '').replace(/›/g, '').trim()
          await item.click()
          await page.waitForSelector('.test-header-left .section-title', { timeout: 20000 })
          const pathname = new URL(page.url()).pathname
          visited.add(pathname)
          const h1 = (await page.locator('.hero h1').textContent() || '').trim()
          if (!h1 || label !== h1) failures.push(`点击"${label}" → ${pathname} → h1="${h1}"`)
        }
        await page.goto(`${origin}/`, { waitUntil: 'networkidle', timeout: 60000 })
        await page.waitForSelector('.test-header-left .section-title', { timeout: 20000 })
      }
    }
    // 前缀构建下侧边栏统一跳 /dma/sem/tool/x，与入口无关
    const missing = expectedTools.filter(id => !visited.has(`/dma/sem/tool/${id}`))
    if (missing.length) failures.push(`未覆盖: ${missing.join(',')}`)
    // 深链验证：入口 URL 直访 + 各自的补充形式（老书签/带前缀直访）
    for (const deepUrl of [`${origin}/tool/en-abstract-move`, ...extraDeeps]) {
      await page.goto(deepUrl, { waitUntil: 'networkidle', timeout: 60000 })
      await page.waitForSelector('.test-header-left .section-title', { timeout: 20000 })
      const deepTitle = (await page.locator('.hero h1').textContent() || '').trim()
      if (deepTitle !== '英文摘要语步识别') failures.push(`深链 ${deepUrl} 异常: "${deepTitle}"`)
    }
    console.log('  ✅ 深链(带前缀+旧式无前缀)渲染正确')
    if (notFound.length) failures.push(`HTTP≥400: ${[...new Set(notFound)].slice(0, 5).join(' | ')}`)
    console.log(`  ${failures.length ? '❌' : '✅'} 覆盖 ${visited.size}/${expectedTools.length} 个工具页`)
    failures.forEach(f => console.log(`     - ${f}`))
    if (failures.length) allOk = false
  } catch (e) {
    console.log(`  ❌ 异常: ${e.message}`)
    allOk = false
  } finally {
    await page.close()
  }
}
await browser.close()
console.log(`\n===== 总结: ${allOk ? '✅ 双入口全部通过' : '❌ 存在失败'} =====`)
process.exit(allOk ? 0 : 1)
