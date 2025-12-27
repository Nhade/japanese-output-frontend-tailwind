<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { watch } from 'vue'
import BaseSelect from './BaseSelect.vue'

const { locale } = useI18n()

watch(locale, (newLocale) => {
  localStorage.setItem('user-locale', newLocale as string)
})

const languageOptions = [
  { value: 'en', label: 'English' },
  { value: 'zh-tw', label: '繁體中文' },
  { value: 'ja', label: '日本語' }
]
</script>

<template>
  <div class="relative flex items-center">
    <BaseSelect v-model="locale" :options="languageOptions" :bordered="false" class="w-28">
      <template #prefix>
        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
          class="size-4 opacity-70">
          <circle cx="12" cy="12" r="10" />
          <line x1="2" x2="22" y1="12" y2="12" />
          <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
        </svg>
      </template>
    </BaseSelect>
  </div>
</template>
