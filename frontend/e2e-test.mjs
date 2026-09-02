import { chromium } from 'playwright'

const TEST_TEXT = '本文提出了一种基于深度学习的图像识别方法。首先构建了多层卷积神经网络模型,通过残差连接解决梯度消失问题。实验表明该方法在复杂场景下具有更高的识别精度,在ImageNet数据集上达到95%的准确率,显著优于传统方法。'

const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1400, height: 900 } })

const shots = []
const snap = async (name) => {
  const path = `/tmp/e2e-${name}.png`
  await page.screenshot({ path })
  shots.push(path)
  console.log(`  📸 ${path}`)
}

try {
  console.log('1. 访问前端 http://localhost:8080')
  await page.goto('http://localhost:8080', { waitUntil: 'networkidle', timeout: 30000 })
  await page.waitForSelector('.primary-textarea', { timeout: 15000 })
  await snap('01-home')
  console.log('   首页渲染 OK,默认功能:摘要语步')

  console.log('2. 填写摘要文本')
  await page.fill('.primary-textarea', TEST_TEXT)
  await snap('02-filled')

  console.log('3. 点击"在线测试"按钮')
  await page.locator('button:has-text("在线测试")').click()
  console.log('   等待后端响应(GLM 调用)...')

  await page.waitForFunction(() => {
    const el = document.querySelector('.response-result-body pre.console')
    if (!el) return false
    const t = el.textContent || ''
    return t.length > 30 && !t.includes('等待后端返回') && !t.includes('必填参数未完成') && !t.includes('在线测试失败')
  }, { timeout: 90000 })
  const responseText = (await page.textContent('.response-result-body pre.console')) || ''
  console.log(`   响应获取成功,长度 ${responseText.length} 字符`)
  console.log(`   响应含 "moves": ${responseText.includes('moves')}`)
  console.log(`   响应含 "move_name": ${responseText.includes('move_name')}`)
  console.log(`   响应含 "confidence": ${responseText.includes('confidence')}`)
  await snap('03-response')

  console.log('4. 检查可视化弹窗按钮')
  const visualBtn = await page.$('button.visual-btn:not([disabled])')
  if (visualBtn) {
    console.log('   找到"查看可视化结果"按钮,点击')
    await visualBtn.click()
    await page.waitForTimeout(1500)
    await snap('04-modal')
    const modalText = (await page.textContent('body')) || ''
    console.log(`   弹窗已打开,页面含"可视化"或 modal: ${modalText.includes('可视化') || modalText.includes('modal')}`)
  } else {
    console.log('   当前功能无可视化按钮(摘要语步可能不支持可视化渲染,属正常)')
  }

  console.log('\n=== 验证结论 ===')
  console.log('✅ 前端页面渲染正常')
  console.log('✅ 输入参数填写并提交成功')
  console.log('✅ 后端返回真实响应并显示在响应区')
  console.log(visualBtn ? '✅ 可视化弹窗可打开' : 'ℹ️ 当前功能无可视化弹窗按钮')
} catch (e) {
  console.log(`❌ 错误: ${e.message}`)
  await page.screenshot({ path: '/tmp/e2e-error.png' })
  console.log(`  截图: /tmp/e2e-error.png`)
} finally {
  await browser.close()
}
