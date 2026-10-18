import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import '@/styles/theme.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import zhCn from 'element-plus/es/locale/lang/zh-cn'

import App from './App.vue'
import router from './router'
import { useUserStore } from './store/user'

const app = createApp(App)
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}
app.use(createPinia())
app.use(router)
app.use(ElementPlus, { locale: zhCn })

// 桌面 / 网页模式由后端直接注入到 index.html（window.__ZIMU_DESKTOP__），
// 这里同步写入 localStorage 供路由和组件判断。
// 不用异步请求探测：一旦探测失败就会被路由踢回登录页（表现为"白屏/看到登录页"）。
if (window.__ZIMU_DESKTOP__ === true) {
  localStorage.setItem('zimu_desktop', '1')
} else if (window.__ZIMU_DESKTOP__ === false) {
  localStorage.setItem('zimu_desktop', '0')
}
if (window.__ZIMU_TITLE__) document.title = window.__ZIMU_TITLE__

app.mount('#app')
