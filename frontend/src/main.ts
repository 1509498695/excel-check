import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'

import App from './App.vue'
import { router } from './router'
import { useWorkbenchStore } from './store/workbench'
import './style.css'
import './fixed-rules.css'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)
app.use(ElementPlus)
app.mount('#app')

const store = useWorkbenchStore()

store.loadCapabilities().catch(() => {
  // 页面级错误提示由 store 托管，这里不再重复抛出。
})
