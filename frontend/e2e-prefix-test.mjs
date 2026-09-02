// 子路径部署（公网 /dma/sem/）端到端验证：
// 1) 起一个只认 /dma/sem 前缀的模拟网关（复刻 edu.itic-sci.com 行为：根路径 404）
//    + 一个返回语步识别响应的假后端；
// 2) Playwright 在线测试：复现用户报障场景（单文本语步识别），断言请求带前缀；
// 3) 侧边栏所有工具逐个跳转 + 深链刷新，断言 URL/标题渲染正确且无 404。
// 另跑一个根路径模式（对应内网 IP / docker nginx 部署）做回归。
import http from 'node:http'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium } from 'playwright'
import { groups } from './src/data/prototype.generated.js'

const here = path.dirname(fileURLToPath(import.meta.url))
const TITLE = '基于深度学习的工业设备故障预警方法研究'
const ABSTRACT = '针对传统工业设备故障预警模型特征提取能力弱、预测精度不足的问题，本文提出一种融合多尺度特征的深度学习故障预警方法。首先采集设备运行时序传感数据，利用多通道卷积模块提取不同周期的运行特征;再结合门控循环单元捕捉时序依赖关系，构建端到端预警模型。在某钢厂电机实测数据集上开展对比实验，结果表明该方法故障识别准确率达到96.3%，相比经典LSTM模型准确率提升7.8%，能够提前预判潜在故障,可为工业设备运维决策提供技术支撑。'
const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.svg': 'image/svg+xml', '.json': 'application/json', '.png': 'image/png', '.woff2': 'font/woff2' }
const expectedTools = groups.flatMap(g => g.items.map(([id]) => id))

function backendServer() {
  return http.createServer((req, res) => {
    const url = new URL(req.url, 'http://x')
    if (req.method === 'POST' && url.pathname === '/api/v1/move/abstract/zh/text') {
      let body = ''
      req.on('data', c => body += c)
      req.on('end', () => {
        const payload = JSON.parse(body || '{}')
        res.writeHead(200, { 'content-type': 'application/json' })
        res.end(JSON.stringify({
          code: 0, message: 'ok',
          data: {
            input_type: 'text', language: 'zh',
            document_title: payload.document_title || '',
            text_length: (payload.text || '').length,
            moves: [
              { move_id: 1, move_name: '研究背景', text: '针对传统工业设备故障预警模型特征提取能力弱、预测精度不足的问题', confidence: 0.94 },
              { move_id: 2, move_name: '研究方法', text: '本文提出一种融合多尺度特征的深度学习故障预警方法。', confidence: 0.91 },
              { move_id: 3, move_name: '研究结果', text: '故障识别准确率达到96.3%', confidence: 0.96 },
            ],
          },
        }))
      })
      return
    }
    res.writeHead(200, { 'content-type': 'application/json' })
    res.end(JSON.stringify({ code: 0, data: [] }))
  })
}

function staticServer(base, distDir) {
  return http.createServer((req, res) => {
    const url = new URL(req.url, 'http://x')
    const stripped = base ? url.pathname.slice(base.length) || '/' : url.pathname
    if (!base || url.pathname.startsWith(base + '/') || url.pathname === base) {
      if (stripped.startsWith('/api/')) {
        const { backend } = staticServer
        const opts = { hostname: '127.0.0.1', port: backend, path: stripped + (url.search || ''), method: req.method, headers: { ...req.headers, host: '127.0.0.1' } }
        const px = http.request(opts, pr => { res.writeHead(pr.statusCode, pr.headers); pr.pipe(res) })
        px.on('error', () => { res.writeHead(502); res.end('bad gateway') })
        req.pipe(px)
        return
      }
      const rel = stripped === '/' ? '/index.html' : decodeURIComponent(stripped)
      const file = path.join(distDir, rel)
      if (fs.existsSync(file) && fs.statSync(file).isFile()) {
        res.writeHead(200, { 'content-type': MIME[path.extname(file)] || 'application/octet-stream' })
        fs.createReadStream(file).pipe(res)
        return
      }
      res.writeHead(200, { 'content-type': 'text/html' })
      fs.createReadStream(path.join(distDir, 'index.html')).pipe(res)
      return
    }
    res.writeHead(404, { 'content-type': 'text/plain' })
    res.end('not found (gateway)')
  })
}

async function waitToolPage(page) {
  await page.waitForSelector('.test-header-left .section-title', { timeout: 20000 })
}

async function runScenario(name, origin, base, distDir) {
  console.log(`\n========== 场景 ${name}: ${origin}${base || '/'} ==========`)
  const browser = await chromium.launch()
  const page = await browser.newPage({ viewport: { width: 1400, height: 900 } })
  const notFound = []
  const apiUrls = []
  page.on('response', r => { if (r.status() === 404) notFound.push(`${r.request().method()} ${r.url()}`) })
  page.on('request', r => { if (r.url().includes('/api/')) apiUrls.push(r.url()) })
  const failures = []
  try {
    // --- 1. 复现在线测试 ---
    await page.goto(`${origin}${base || ''}/`, { waitUntil: 'networkidle', timeout: 30000 })
    await page.waitForSelector('.primary-textarea', { timeout: 15000 })
    const titleInput = page.locator('.document-title-field input').first()
    if (await titleInput.count()) await titleInput.fill(TITLE)
    await page.fill('.primary-textarea', ABSTRACT)
    await page.locator('button.primary-btn:has-text("在线测试")').click()
    await page.waitForFunction(() => {
      const el = document.querySelector('.response-result-body pre.console')
      if (!el) return false
      const t = el.textContent || ''
      return t.includes('move_name') || t.includes('在线测试失败')
    }, { timeout: 30000 })
    const responseText = (await page.textContent('.response-result-body pre.console')) || ''
    if (responseText.includes('在线测试失败')) {
      failures.push(`在线测试仍失败: ${responseText.slice(0, 160)}`)
    } else {
      console.log(`  ✅ 在线测试成功,响应含 move_name,长度 ${responseText.length}`)
    }
    const expectedApi = `${origin}${base || ''}/api/v1/move/abstract/zh/text`
    if (!apiUrls.includes(expectedApi)) failures.push(`未请求带前缀接口 ${expectedApi};实际: ${apiUrls.join(' | ')}`)
    else console.log(`  ✅ 请求走 ${expectedApi}`)
    // 根路径部署下 API 本就应打到根 /api/，该检查仅对子路径部署有意义
    if (base) {
      const rootLeak = apiUrls.filter(u => u.startsWith(`${origin}/api/`))
      if (rootLeak.length) failures.push(`存在未带前缀的根路径 API 请求: ${rootLeak.join(' | ')}`)
    }

    // --- 2. 侧边栏所有工具跳转 ---
    const visited = new Set()
    const groupTitles = page.locator('#libraryTree .tool-group-title')
    const groupCount = await groupTitles.count()
    let navigations = 0
    for (let gi = 0; gi < groupCount; gi++) {
      // 每轮回到首页态再点分组，避免上一轮 flyout 残留
      await groupTitles.nth(gi).click()
      const flyoutItems = page.locator('.v752-nav-flyout-item')
      const itemCount = await flyoutItems.count()
      if (itemCount === 0) {
        // 单工具分组：点击标题已直接跳转
        await waitToolPage(page)
        visited.add(decodeURIComponent(new URL(page.url()).pathname))
        navigations++
      } else {
        for (let ii = 0; ii < itemCount; ii++) {
          // 每轮重新点分组标题展开 flyout：上一次点击已整页跳转，flyout 不复存在
          await page.locator('#libraryTree .tool-group-title').nth(gi).click()
          const item = page.locator('.v752-nav-flyout-item').nth(ii)
          const label = (await item.textContent() || '').replace(/›/g, '').trim()
          await item.click()
          await waitToolPage(page)
          navigations++
          const pathname = decodeURIComponent(new URL(page.url()).pathname)
          visited.add(pathname)
          const h1 = (await page.locator('.hero h1').textContent() || '').trim()
          if (!h1 || label !== h1) failures.push(`跳转后标题异常: 点击"${label}" → ${pathname} → h1="${h1}"`)
        }
        // 回到默认页继续点下一个分组
        await page.goto(`${origin}${base || ''}/`, { waitUntil: 'networkidle', timeout: 30000 })
        await waitToolPage(page)
      }
    }
    console.log(`  ✅ 侧边栏完成 ${navigations} 次跳转,覆盖 ${visited.size} 个工具 URL`)
    const expectedUrls = new Set(expectedTools.map(id => `${base || ''}/tool/${id}`))
    const missing = [...expectedUrls].filter(u => !visited.has(u))
    if (missing.length) failures.push(`未覆盖的工具页: ${missing.join(' | ')}`)

    // --- 3. 深链刷新（toolIdFromLocation 需识别前缀） ---
    await page.goto(`${origin}${base || ''}/tool/en-abstract-move`, { waitUntil: 'networkidle', timeout: 30000 })
    await waitToolPage(page)
    const deepTitle = (await page.locator('.hero h1').textContent() || '').trim()
    if (deepTitle !== '英文摘要语步识别') failures.push(`深链 /tool/en-abstract-move 渲染异常: h1="${deepTitle}"`)
    else console.log('  ✅ 深链刷新 /tool/en-abstract-move 正常渲染')

    if (notFound.length) failures.push(`出现 404: ${[...new Set(notFound)].slice(0, 5).join(' | ')}`)
  } catch (e) {
    failures.push(`异常: ${e.message}`)
    await page.screenshot({ path: `/tmp/e2e-prefix-${name}.png` }).catch(() => {})
  } finally {
    await browser.close()
  }
  if (failures.length) {
    console.log(`  ❌ ${name} 失败:`)
    failures.forEach(f => console.log(`     - ${f}`))
    return false
  }
  console.log(`  ✅ 场景 ${name} 全部通过`)
  return true
}

const backend = backendServer().listen(9098)
staticServer.backend = 9098
const prefixGw = staticServer('/dma/sem', path.join(here, 'dist')).listen(9099)
const rootSrv = staticServer('', path.join(here, 'dist-root')).listen(9097)
await new Promise(r => setTimeout(r, 300))

const ok1 = await runScenario('公网子路径 /dma/sem', 'http://127.0.0.1:9099', '/dma/sem', path.join(here, 'dist'))
const ok2 = await runScenario('内网根路径 /', 'http://127.0.0.1:9097', '', path.join(here, 'dist-root'))

backend.close(); prefixGw.close(); rootSrv.close()
console.log(`\n========== 总结: ${ok1 && ok2 ? '✅ 全部通过' : '❌ 存在失败'} ==========`)
process.exit(ok1 && ok2 ? 0 : 1)
