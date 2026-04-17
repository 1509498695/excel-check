import { createRouter, createWebHistory } from 'vue-router'

import { useAuthStore } from '../store/auth'
import FixedRulesBoard from '../views/FixedRulesBoard.vue'
import MainBoard from '../views/MainBoard.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('../views/LoginView.vue'),
      meta: { guest: true },
    },
    {
      path: '/register',
      name: 'register',
      component: () => import('../views/RegisterView.vue'),
      meta: { guest: true },
    },
    {
      path: '/',
      name: 'main-board',
      component: MainBoard,
      meta: { auth: true },
    },
    {
      path: '/fixed-rules',
      name: 'fixed-rules-board',
      component: FixedRulesBoard,
      meta: { auth: true },
    },
    {
      path: '/admin',
      name: 'admin',
      component: () => import('../views/AdminView.vue'),
      meta: { auth: true, admin: true },
    },
    {
      path: '/profile',
      name: 'profile',
      component: () => import('../views/ProfileView.vue'),
      meta: { auth: true },
    },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()

  if (!auth.isReady) {
    await auth.fetchMe()
  }

  if (to.meta.auth && !auth.isLoggedIn) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }

  if (to.meta.guest && auth.isLoggedIn) {
    return { name: 'main-board' }
  }

  if (to.meta.admin && !auth.isProjectAdmin) {
    return { name: 'main-board' }
  }
})
