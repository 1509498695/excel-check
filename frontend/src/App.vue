<template>
  <div class="app-shell">
    <header class="app-shell-header">
      <div class="app-shell-brand">
        <span class="app-shell-brand-mark">EC</span>
        <div>
          <strong>Excel Check</strong>
          <p>配置表校验工作台</p>
        </div>
      </div>

      <nav class="app-shell-nav" aria-label="主导航">
        <RouterLink to="/" class="app-shell-link" active-class="is-active">
          工作台
        </RouterLink>
        <RouterLink to="/fixed-rules" class="app-shell-link" active-class="is-active">
          固定规则检查
        </RouterLink>
      </nav>
    </header>

    <main class="app-shell-page">
      <router-view />
    </main>
  </div>
</template>
