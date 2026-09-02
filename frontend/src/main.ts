import { createApp } from 'vue'
import App from './App.vue'
import './styles/prototype.generated.css'
import './styles/app.css'

document.body.classList.add('figma-ui-v717')

// 页面滚轮交给浏览器原生滚动（步长/平滑/滚动链均由浏览器处理）。
// 原型 CSS 给嵌套滚动容器加了 overscroll-behavior: contain 会导致边界卡住滚轮，
// 该问题改由 app.css 的 overscroll-behavior 覆盖统一解决，不再全局拦截 wheel 事件。

createApp(App).mount('#app')
