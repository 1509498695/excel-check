import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'

import App from './App.vue'
import { router } from './router'
import './style.css'
import './styles/shared.css'
import './styles/workbench.css'
import './styles/auth.css'
import './styles/admin.css'
import './styles/profile.css'
import './styles/shared-overrides.css'
import './styles/personal-check.css'
import './styles/fixed-rules.css'
import './styles/admin-dashboard.css'
import './styles/profile-settings.css'
import './styles/shared-final.css'
import './styles/user-guide.css'
import './styles/ai-rule.css'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)
app.use(ElementPlus)
app.mount('#app')
