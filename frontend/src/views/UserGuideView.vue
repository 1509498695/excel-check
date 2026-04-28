<script setup lang="ts">
import { useRouter } from 'vue-router'

import AppCard from '../components/shell/AppCard.vue'
import PageHeader from '../components/shell/PageHeader.vue'
import SecondaryButton from '../components/shell/SecondaryButton.vue'
import { userGuideSections } from '../content/userGuide'

const router = useRouter()

function closeGuideTab(): void {
  window.close()
  window.setTimeout(() => {
    router.push('/profile')
  }, 120)
}
</script>

<template>
  <div class="user-guide-page flex h-full flex-col bg-canvas font-sans text-ink-700">
    <PageHeader breadcrumb="主页 / 系统使用说明" title="系统使用说明">
      <template #actions>
        <SecondaryButton @click="closeGuideTab">
          <template #icon>
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
              aria-hidden="true"
            >
              <path d="M18 6 6 18" />
              <path d="m6 6 12 12" />
            </svg>
          </template>
          关闭页签
        </SecondaryButton>
      </template>
    </PageHeader>

    <div class="user-guide-content flex flex-1 flex-col overflow-y-auto px-8 py-8">
      <div class="user-guide-layout">
        <AppCard as="aside" padding="none" class="user-guide-toc">
          <div class="user-guide-toc__eyebrow">使用目录</div>
          <nav aria-label="系统使用说明目录">
            <a
              v-for="section in userGuideSections"
              :key="section.id"
              class="user-guide-toc__link"
              :href="`#${section.id}`"
            >
              {{ section.title.replace(/^\d+\.\s*/, '') }}
            </a>
          </nav>
        </AppCard>

        <div class="user-guide-main">
          <AppCard padding="none" class="user-guide-hero">
            <div class="user-guide-hero__mark">
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
                aria-hidden="true"
              >
                <path d="M4 19.5V5a2 2 0 0 1 2-2h10.5L20 6.5V19a2 2 0 0 1-2 2H6a2 2 0 0 1-2-1.5Z" />
                <path d="M15 3v5h5" />
                <path d="M8 12h8" />
                <path d="M8 16h6" />
              </svg>
            </div>
            <div>
              <p class="user-guide-hero__eyebrow">Excel Check</p>
              <h2>系统使用说明</h2>
              <p>
                面向普通用户、项目管理员和超级管理员，说明个人校验、项目校验、管理后台与个人设置的日常使用方法。
              </p>
            </div>
          </AppCard>

          <AppCard
            v-for="section in userGuideSections"
            :id="section.id"
            :key="section.id"
            as="section"
            padding="none"
            class="user-guide-section"
          >
            <div class="user-guide-section__head">
              <span class="user-guide-section__index">
                {{ section.title.split('.')[0].padStart(2, '0') }}
              </span>
              <h2>{{ section.title.replace(/^\d+\.\s*/, '') }}</h2>
            </div>

            <div class="user-guide-section__body">
              <p
                v-for="paragraph in section.paragraphs"
                :key="paragraph"
              >
                {{ paragraph }}
              </p>

              <ul v-if="section.items?.length" class="user-guide-list">
                <li
                  v-for="item in section.items"
                  :key="item"
                >
                  {{ item }}
                </li>
              </ul>

              <div
                v-for="subsection in section.subsections"
                :key="subsection.title"
                class="user-guide-subsection"
              >
                <h3>{{ subsection.title }}</h3>
                <p
                  v-for="paragraph in subsection.paragraphs"
                  :key="paragraph"
                >
                  {{ paragraph }}
                </p>
                <ul v-if="subsection.items?.length" class="user-guide-list">
                  <li
                    v-for="item in subsection.items"
                    :key="item"
                  >
                    {{ item }}
                  </li>
                </ul>
              </div>
            </div>
          </AppCard>
        </div>
      </div>
    </div>
  </div>
</template>
