// 一次性公网实测：复现用户报障操作（语步识别·单文本），验证 /dma/sem/ 下在线测试可用
import { chromium } from 'playwright'

const TITLE = '基于深度学习的工业设备故障预警方法研究'
const ABSTRACT = '针对传统工业设备故障预警模型特征提取能力弱、预测精度不足的问题，本文提出一种融合多尺度特征的深度学习故障预警方法。首先采集设备运行时序传感数据，利用多通道卷积模块提取不同周期的运行特征;再结合门控循环单元捕捉时序依赖关系，构建端到端预警模型。在某钢厂电机实测数据集上开展对比实验，结果表明该方法故障识别准确率达到96.3%，相比经典LSTM模型准确率提升7.8%，能够提前预判潜在故障,可为工业设备运维决策提供技术支撑。'
const URL = 'https://edu.itic-sci.com/dma/sem/'

const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1400, height: 900 }, ignoreHTTPSErrors: true })
const apiHits = []
page.on('request', r => { if (r.url().includes('/api/v1/move/')) apiHits.push(r.url()) })
try {
  await page.goto(URL, { waitUntil: 'networkidle', timeout: 60000 })
  await page.waitForSelector('.primary-textarea', { timeout: 20000 })
  await page.locator('.document-title-field input').first().fill(TITLE)
  await page.fill('.primary-textarea', ABSTRACT)
  await page.locator('button.primary-btn:has-text("在线测试")').click()
  await page.waitForFunction(() => {
    const el = document.querySelector('.response-result-body pre.console')
    if (!el) return false
    const t = el.textContent || ''
    return t.includes('move_name') || t.includes('在线测试失败')
  }, { timeout: 180000 })
  const text = (await page.textContent('.response-result-body pre.console')) || ''
  await page.screenshot({ path: '/tmp/e2e-public-final.png' })
  if (text.includes('在线测试失败')) {
    console.log(`❌ 仍失败: ${text.slice(0, 200)}`)
  } else {
    console.log(`✅ 公网在线测试成功 响应长度 ${text.length}`)
    console.log(`   请求地址: ${apiHits[0]}`)
    console.log(`   含 move_name: ${text.includes('move_name')}  含 confidence: ${text.includes('confidence')}`)
  }
} catch (e) {
  console.log(`❌ 异常: ${e.message}`)
  await page.screenshot({ path: '/tmp/e2e-public-error.png' }).catch(() => {})
} finally {
  await browser.close()
}
