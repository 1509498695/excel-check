import { createRouter, createWebHistory } from 'vue-router'

import MainBoard from '../views/MainBoard.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'main-board',
      component: MainBoard,
    },
  ],
})
